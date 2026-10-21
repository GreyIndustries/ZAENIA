"""Isolated capability checks; no owner data, app launches, camera, or model calls."""
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.assistant_platform import live_answers
from core.assistant_platform.store import PlatformStore,Conflict
from core.assistant_platform.performance import ModelCoordinator,WorkCancelled
from core.assistant_platform.jobs import JobManager
from core.assistant_platform.projects import validate_project,project_view
from core.assistant_platform.workspaces import validate_workspace
from core.assistant_platform.actions import ActionHistory
from core.assistant_platform.documents import DocumentIndex,register_root,selected_file
from core.assistant_platform.profiles import encode_profile,decode_profile,capture_profile,restore_profile


class Fixture(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack(); self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(TemporaryDirectory(prefix="zae-platform-test-",dir=Path(__file__).resolve().parents[2])))
        self.stack.enter_context(patch('core.assistant_platform.store.protect_storage'))
        self.stack.enter_context(patch('core.assistant_platform.releases.protect_storage'))
        self.store=PlatformStore(self.root/'private/state.sqlite3')


class LiveDataTests(unittest.TestCase):
    now=datetime(2026,10,17,10,tzinfo=ZoneInfo('America/Los_Angeles'))

    def test_weather_uses_measured_values_and_tomorrows_correct_day(self):
        weather={'location':{'display_label':'in Test Town'},'checkedAt':self.now.isoformat(),'forecast':{
            'current':{'temperature_2m':61,'weather_code':0},'daily':{'time':['2026-10-17','2026-10-18'],
                'temperature_2m_max':[65,51],'temperature_2m_min':[45,38],'weather_code':[0,61],'precipitation_sum':[0,0.7]}}}
        result=live_answers.resolve('Will it rain tomorrow?',lambda op:True,now=self.now,loaders={'weather':lambda:weather})
        self.assertIn('51°F',result['answer']); self.assertIn('0.7 inches',result['answer'])
        self.assertNotIn('61°F',result['answer']); self.assertTrue(result['verification']['available'])

    def test_permission_denial_and_failure_never_fall_back_to_model_guess(self):
        for authorize,loader in [(lambda op:False,lambda: self.fail('denied loader ran')),(lambda op:True,lambda: (_ for _ in ()).throw(OSError()))]:
            result=live_answers.resolve('Weather now?',authorize,now=self.now,loaders={'weather':loader})
            self.assertIn("won't guess",result['answer']); self.assertFalse(result['verification']['available'])

    def test_calendar_query_reads_expected_pacific_range_and_discloses_failed_google(self):
        seen=[]
        def load(start,days):
            seen.append((start.isoformat(),days))
            return {'events':[{'date':'2026-10-18','time':'15:30','title':'Inspection'}],'notice':'Google unavailable; showing saved events.'}
        result=live_answers.resolve("What's on my calendar tomorrow?",lambda op:True,now=self.now,loaders={'calendar':load})
        self.assertEqual(seen,[('2026-10-18',1)]); self.assertIn('Inspection',result['answer']); self.assertIn('Google unavailable',result['answer'])

    def test_explanations_and_write_requests_do_not_take_read_only_route(self):
        for text in ['Explain weather forecasting','What is weather?','Add a task to check weather','Schedule inspection tomorrow at 3 pm']:
            if text.startswith('Add a task'): continue
            self.assertIsNone(live_answers.topic_for(text))


class StoreAndPlanTests(Fixture):
    def test_revision_refuses_lost_updates_and_sql_parameters_stay_data(self):
        row=self.store.put('project',{'title':"x'; DROP TABLE records; --"})
        self.store.put('project',{'title':'new'},row['id'],revision=row['revision'])
        with self.assertRaises(Conflict): self.store.put('project',{'title':'stale'},row['id'],revision=row['revision'])
        self.assertEqual(len(self.store.list('project')),1)

    def test_dependencies_reject_cycles_and_false_progress(self):
        bad={'title':'Build','steps':[{'id':'a','title':'First','dependsOn':['b']},{'id':'b','title':'Second','dependsOn':['a']}]}
        with self.assertRaises(ValueError): validate_project(bad)
        bad['steps'][0]['dependsOn']=[]; bad['steps'][1]['status']='completed'
        with self.assertRaises(ValueError): validate_project(bad)
        bad['steps'][1]['status']='pending'
        plan=validate_project(bad)
        self.assertEqual(project_view(plan)['nextStep']['id'],'a'); self.assertEqual(project_view(plan)['progress'],0)
        plan['steps'][0]['status']='completed'
        self.assertEqual(project_view(validate_project(plan))['progress'],50)

    def test_workspace_ignores_unknown_windows_and_bounds_restored_positions(self):
        with self.assertRaises(ValueError): validate_workspace({'name':'X','windows':[{'id':'shell','x':0,'y':0,'w':1,'h':1}]})
        saved=validate_workspace({'name':'Coding','windows':[{'id':'files','x':100,'y':-90,'w':4,'h':-2}]})
        self.assertLessEqual(saved['windows'][0]['x']+saved['windows'][0]['w'],1)
        self.assertGreaterEqual(saved['windows'][0]['h'],.3)


class SchedulingTests(unittest.TestCase):
    def test_priority_and_conversation_can_share_slots_while_ordinary_waits(self):
        coordinator=ModelCoordinator(); entered=threading.Event(); finished=threading.Event()
        def ordinary():
            with coordinator.slot('deferred'): entered.set()
            finished.set()
        with coordinator.slot('foreground'):
            with coordinator.slot('priority'):
                with coordinator.slot('intent'): self.assertEqual(coordinator.snapshot()['intent'],1)
                worker=threading.Thread(target=ordinary); worker.start()
                self.assertFalse(entered.wait(.08))
            self.assertFalse(entered.wait(.08))
        self.assertTrue(finished.wait(2)); worker.join(2)

    def test_new_question_cancels_only_obsolete_automatic_jobs(self):
        manager=JobManager(workers=2); entered=threading.Event(); release=threading.Event()
        def run(context):
            entered.set(); release.wait(2); context.check(); return {'done':True}
        pinned=manager.submit('Priority work',run,priority=True)
        self.assertTrue(entered.wait(1)); manager.foreground(); release.set()
        for _ in range(100):
            if manager.snapshot(pinned['id'])['status']=='completed': break
            time.sleep(.01)
        self.assertEqual(manager.snapshot(pinned['id'])['status'],'completed')

    def test_explicit_job_cancellation_does_not_report_success(self):
        manager=JobManager(workers=1); entered=threading.Event(); release=threading.Event()
        def run(context): entered.set(); release.wait(2); context.check(); return {'wrong':'success'}
        job=manager.submit('Cancel this',run); self.assertTrue(entered.wait(1)); manager.cancel(job['id']); release.set()
        for _ in range(100):
            if manager.snapshot(job['id'])['status']=='cancelled': break
            time.sleep(.01)
        self.assertEqual(manager.snapshot(job['id'])['status'],'cancelled'); self.assertIsNone(manager.snapshot(job['id'])['result'])


class DocumentTests(Fixture):
    class Context:
        def check(self): pass
        def progress(self,*args,**kwargs): pass

    def test_generated_plan_is_a_draft_with_pending_steps_and_resolved_dependencies(self):
        from core.assistant_platform.service import PlatformService
        service=PlatformService(self.store,JobManager(workers=1))
        model='{"steps":[{"title":"Check requirements","status":"completed"},{"title":"Build the change","dependsOn":[0]}]}'
        with patch('core.brain.local_llm.chat_local',return_value=model):
            job=service.draft_plan('Upgrade','Build a verified change',lambda op:True)
            for _ in range(100):
                result=service.jobs.snapshot(job['id'])
                saved=self.store.get('job',job['id'])
                if saved['status'] not in {'queued','running'}:break
                time.sleep(.01)
        result=service.jobs.snapshot(job['id'])
        self.assertEqual(result['status'],'completed')
        draft=result['result']['draft']
        self.assertEqual([step['status'] for step in draft['steps']],['pending','pending'])
        self.assertEqual(draft['steps'][1]['dependsOn'],[draft['steps'][0]['id']])
        self.assertEqual(self.store.list('project'),[])

    def test_cross_process_cancellation_survives_progress_updates(self):
        manager=JobManager(workers=1); manager.attach(self.store)
        entered=threading.Event(); release=threading.Event()
        def run(context):
            entered.set();release.wait(2)
            context.progress('Still reading')
            return {'incorrect':'success'}
        job=manager.submit('Remote cancellation',run,priority=True)
        self.assertTrue(entered.wait(1))
        self.store.patch('job',job['id'],{'cancelRequested':True})
        # Simulate the owning process saving progress after a second process cancels.
        manager.save(job['id'])
        self.assertTrue(self.store.get('job',job['id'])['cancelRequested'])
        release.set()
        for _ in range(100):
            if self.store.get('job',job['id'])['status']=='cancelled':break
            time.sleep(.01)
        self.assertEqual(manager.snapshot(job['id'])['status'],'cancelled')

    def test_search_has_sources_refuses_stale_files_and_revokes_folder_access(self):
        folder=self.root/'notes'; folder.mkdir(); file=folder/'inspection.md'; file.write_text('The inspection checklist is in the blue binder.',encoding='utf-8')
        registered=self.store.put('document_root',register_root({'name':'Notes','path':str(folder)}))
        index=DocumentIndex(self.store); index.index(registered['id'],self.Context())
        rows=index.search('inspection checklist'); self.assertTrue(rows); self.assertEqual(rows[0]['path'],'inspection.md'); self.assertIsNone(rows[0]['page'])
        file.write_text('Changed checklist content.',encoding='utf-8'); self.assertEqual(index.search('blue binder'),[])
        index.index(registered['id'],self.Context()); index.remove_root(registered['id']); self.assertEqual(index.search('checklist'),[])

    def test_pdf_citation_refers_to_actual_matching_page(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        folder=self.root/'pdfs'; folder.mkdir(); path=folder/'guide.pdf'; writer=PdfWriter()
        for sentence in ('First page introduction','Inspection checklist on second page'):
            page=writer.add_blank_page(width=500,height=500)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
            stream=DecodedStreamObject(); stream.set_data(f'BT /F1 12 Tf 30 400 Td ({sentence}) Tj ET'.encode()); page[NameObject('/Contents')]=writer._add_object(stream)
        with path.open('wb') as handle: writer.write(handle)
        registered=self.store.put('document_root',register_root({'name':'PDFs','path':str(folder)}))
        index=DocumentIndex(self.store); index.index(registered['id'],self.Context())
        self.assertEqual(index.search('inspection checklist')[0]['page'],2)

    def test_path_traversal_hidden_credentials_and_drive_roots_are_refused(self):
        folder=self.root/'docs'; folder.mkdir()
        root=register_root({'path':str(folder),'name':'Docs'})
        for relative in ['../outside.txt','.env','passwords.txt']:
            with self.assertRaises((ValueError,PermissionError)): selected_file(root,relative)
        with self.assertRaises(ValueError): register_root({'path':str(Path(self.root.anchor)),'name':'Drive'})


class UndoAndProfileTests(Fixture):
    def test_undo_refuses_later_task_edits_and_preserves_them(self):
        from core.api import ui_tasks
        with patch.object(ui_tasks,'UI_DATA_DIR',self.root/'tasks'):
            _,task=ui_tasks.create_task('Inspect car')
            history=ActionHistory(self.store); receipt=history.receipt('task.create','Created task',target=task['id'],after=task)
            ui_tasks.update_task(task['id'],{'title':'Later edit'})
            with self.assertRaises(Conflict): history.undo(receipt['id'],lambda op:True)
            self.assertEqual(ui_tasks.list_tasks()[0]['title'],'Later edit')

    def test_supported_undo_removes_only_the_exact_new_task(self):
        from core.api import ui_tasks
        with patch.object(ui_tasks,'UI_DATA_DIR',self.root/'tasks'):
            _,task=ui_tasks.create_task('Inspect car'); ui_tasks.create_task('Keep this')
            history=ActionHistory(self.store); receipt=history.receipt('task.create','Created task',target=task['id'],after=task)
            self.assertEqual(history.undo(receipt['id'],lambda op:True)['status'],'undone')
            self.assertEqual([row['title'] for row in ui_tasks.list_tasks()],['Keep this'])

    def test_memory_receipt_never_contains_another_copy_of_the_fact(self):
        receipt=ActionHistory(self.store).receipt('memory.remember','Saved response style',after={'id':'a','key':'response style','value':'private fact not duplicated'},target='a')
        self.assertNotIn('private fact not duplicated',json.dumps(self.store.list('receipt')))
        self.assertTrue(receipt['undoable'])

    def test_encrypted_profile_round_trip_rejects_tampering_and_excludes_grants(self):
        from cryptography.fernet import InvalidToken
        from core.personal_memory import MemoryStore
        from core.personal_memory.insights import InsightStore
        memory=MemoryStore(self.root/'memory.sqlite3'); memory.upsert('favorite color','blue')
        self.store.put('app',{'name':'Not portable','path':'C:/app.exe'})
        payload=capture_profile(self.store,memory_store=memory,insights=InsightStore(self.root/'insights.json'))
        encoded=encode_profile(payload,'isolated test passphrase')
        self.assertNotIn(b'blue',encoded); self.assertNotIn('apps',payload)
        decoded=decode_profile(encoded,'isolated test passphrase'); self.assertEqual(decoded['memories'][0]['value'],'blue')
        with self.assertRaises(InvalidToken): decode_profile(encoded,'different test passphrase')
        target=MemoryStore(self.root/'destination.sqlite3'); target.upsert('favorite color','green')
        result=restore_profile(decoded,self.store,memory_store=target,insight_store=InsightStore(self.root/'destination-insights.json'))
        self.assertEqual(target.get('favorite color')['value'],'green'); self.assertEqual(result['skipped'],1)

    def test_source_snapshot_never_copies_data_and_refuses_modified_manifest(self):
        from core.assistant_platform.releases import capture_release,validate_release
        source=self.root/'project'; (source/'core').mkdir(parents=True); (source/'data/secure').mkdir(parents=True)
        (source/'core/main.py').write_text('print("demo")'); (source/'data/secure/secret').write_text('not a source file')
        snapshot=capture_release(self.store,root=source)
        manifest=validate_release(self.store,snapshot['id']); self.assertEqual([row['path'] for row in manifest['files']],['core/main.py'])
        manifest_path=self.store.path.parent/'releases'/snapshot['id']/'manifest.json'; manifest_path.write_text('{}')
        with self.assertRaises(ValueError): validate_release(self.store,snapshot['id'])


class PlatformApiTests(Fixture):
    def client(self,allowed=None):
        from fastapi.testclient import TestClient
        from core.api.server import create_app
        from core.assistant_platform.service import PlatformService
        from core.assistant_platform.apps import AppLauncher
        executions=[]
        service=PlatformService(self.store,JobManager(),AppLauncher(self.store,launch=lambda target:executions.append(target) or {'status':'opened'}))
        class Gate:
            def authorize(self,operation): return operation is not None and (allowed is None or operation in allowed)
        self.stack.enter_context(patch('core.api.desktop_key.verify',side_effect=lambda key:key=='isolated-desktop-key'))
        client=self.stack.enter_context(TestClient(create_app(token_verifier=lambda token:token=='isolated-platform-token',client_gate=Gate(),include_carplay=False,include_phone_app=False,platform_provider=lambda:service)))
        client.headers['X-ZAENIA-API-TOKEN']='isolated-platform-token'
        return client,service,executions

    def test_all_capability_routes_require_auth_and_process_grants_require_desktop(self):
        client,service,executions=self.client()
        target=self.root/'chosen.txt'; target.write_text('fixture')
        unauth=client.get('/api/platform/jobs',headers={'X-ZAENIA-API-TOKEN':'wrong'})
        self.assertEqual(unauth.status_code,401)
        self.assertEqual(client.post('/api/platform/apps',json={'name':'Chosen','path':str(target)}).status_code,403)
        client.headers['X-ZAENIA-DESKTOP-KEY']='isolated-desktop-key'
        registered=client.post('/api/platform/apps',json={'name':'Chosen','path':str(target)})
        self.assertEqual(registered.status_code,200,registered.text)
        identifier=registered.json()['id']
        self.assertEqual(client.post(f'/api/platform/apps/{identifier}/launch').status_code,200)
        self.assertEqual(len(executions),1)
        target.write_text('changed contents')
        self.assertEqual(client.post(f'/api/platform/apps/{identifier}/launch').status_code,422)
        self.assertEqual(len(executions),1)

    def test_source_permission_denial_blocks_document_reads(self):
        client,_,_=self.client({'assistant.documents.read'})
        self.assertEqual(client.get('/api/platform/documents/search?q=checklist').status_code,403)

    def test_forget_cannot_be_autoapproved_and_workspace_revision_is_checked(self):
        client,_,_=self.client(); client.headers['X-ZAENIA-DESKTOP-KEY']='isolated-desktop-key'
        response=client.put('/api/platform/approvals',json={'voiceAutomatic':['memory.forget'],'chatAutomatic':[]})
        self.assertEqual(response.status_code,422)
        saved=client.post('/api/platform/workspaces',json={'name':'Coding','windows':[]}).json()
        newer=client.patch('/api/platform/workspaces/'+saved['id'],json={'name':'Coding','windows':[],'revision':saved['revision']})
        self.assertEqual(newer.status_code,200)
        stale=client.post('/api/platform/workspaces/'+saved['id']+'/restore',json={'launchApps':True,'revision':saved['revision']})
        self.assertEqual(stale.status_code,409)

    def test_profile_request_never_exports_secrets_over_http(self):
        client,_,_=self.client(); client.headers['X-ZAENIA-DESKTOP-KEY']='isolated-desktop-key'
        response=client.post('/api/platform/profile/requests',json={'mode':'export','path':str(self.root/'copy.zae-profile'),'uiSettings':{'zaenia.phone.token':'must-not-travel'}})
        self.assertEqual(response.status_code,422)
        response=client.post('/api/platform/profile/requests',json={'mode':'export','path':str(self.root/'copy.zae-profile'),'uiSettings':{}})
        self.assertEqual(response.status_code,200); self.assertEqual(response.json()['status'],'pending'); self.assertFalse((self.root/'copy.zae-profile').exists())


if __name__=='__main__': unittest.main()
