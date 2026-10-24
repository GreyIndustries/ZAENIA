"""Isolated tests: no owner files, captured pixels, daily browser, or app launches."""
from contextlib import ExitStack
from datetime import datetime,timedelta,timezone
import hashlib
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch
import zipfile

from core.assistant_platform.store import PlatformStore,Conflict
from core.assistant_platform.jobs import JobManager
from core.assistant_platform.service import PlatformService
from core.assistant_operator.service import Operator,clean_steps,plan_hash
from core.assistant_operator.tools import Tools,validate,file_path,zip_check
from core.assistant_operator.web import public_url,fetch_bytes,read_page,research

class Context:
    def check(self,**kwargs): pass
    def progress(self,*args,**kwargs): pass

class Fixture(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack(); self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='zae-operator-',dir=Path(__file__).resolve().parents[2])))
        self.stack.enter_context(patch('core.assistant_platform.store.protect_storage'))
        self.store=PlatformStore(self.root/'private/store.sqlite3'); self.platform=PlatformService(self.store,JobManager())
        self.operator=self.platform.operator; self.tools=self.operator.tools
        self.work=self.root/'work'; self.work.mkdir()
        self.grant=self.store.put('operator_root',{'name':'Fixture work','path':str(self.work)})

    def fileargs(self,path,**kw): return {'rootId':self.grant['id'],'path':path,**kw}
    def mission(self,steps): return self.operator.create('Isolated task',steps)
    def start(self,row): return self.operator.start(row['id'],row['revision'],row['planHash'],lambda op:True)
    def wait(self,identifier):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            row=self.store.get('job',identifier)
            if row and row['status'] not in {'queued','running'}:
                self.assertTrue(self.platform.jobs.settled[identifier].wait(2))
                return row
            time.sleep(.025)
        self.fail('Job did not finish within eight seconds.')

class PlanTests(Fixture):
    def test_explicit_priority_survives_model_draft_without_execution(self):
        with patch('core.assistant_operator.planner.plan_json',return_value={'steps':[{'tool':'web.read','args':{'url':'https://example.com'}}]}):
            job=self.operator.draft('Priority research','Read the public example page.',lambda op:True,priority=True)
            self.wait(job['id'])
        self.assertTrue(job['priority']);self.assertTrue(self.store.list('mission')[0]['priority']);self.assertEqual(self.store.list('mission')[0]['status'],'draft')
    def test_queue_cancelled_before_callback_does_not_leave_mission_stuck(self):
        import os,psutil
        row=self.mission([{'tool':'document.create','args':self.fileargs('never.txt',content='never')}])
        job=self.store.put('job',{'status':'cancelled'})
        self.store.patch('mission',row['id'],{'status':'queued','ownerPid':os.getpid(),'ownerBirth':psutil.Process().create_time(),'jobId':job['id']})
        result=self.operator.reconcile()[0]
        self.assertEqual(result['status'],'cancelled');self.assertFalse((self.work/'never.txt').exists())

    def test_compact_poll_omits_large_evidence_but_detail_keeps_it(self):
        row=self.mission([{'tool':'web.read','args':{'url':'https://example.com'}}])
        self.store.patch('mission',row['id'],{'status':'completed','steps':[{'status':'completed','result':{'text':'evidence '*50000,'verified':True}}]})
        compact=self.operator.reconcile(compact=True)[0]
        self.assertNotIn('result',compact['steps'][0]);self.assertLess(len(json.dumps(compact)),2000)
        self.assertEqual(len(self.store.get('mission',row['id'])['steps'][0]['result']['text']),450000)

    def test_unknown_tools_extra_arguments_and_future_references_rejected(self):
        for steps in [[],[{'tool':'shell.run','args':{}}],[{'tool':'web.read','args':{'url':'https://example.com','shell':'x'}}],
            [{'tool':'evidence.summarize','args':{'sourceStep':0}}]]:
            with self.assertRaises(ValueError): clean_steps(steps)

    def test_review_hash_and_revision_bind_execution(self):
        row=self.mission([{'tool':'document.create','args':self.fileargs('one.txt',content='hello')}])
        with self.assertRaises(Conflict): self.operator.start(row['id'],row['revision'],'0'*64,lambda op:True)
        with self.assertRaises(Conflict): self.operator.start(row['id'],999,row['planHash'],lambda op:True)
        self.assertFalse((self.work/'one.txt').exists())

    def test_permission_denial_does_not_claim_or_execute(self):
        row=self.mission([{'tool':'document.create','args':self.fileargs('one.txt',content='hello')}])
        with self.assertRaises(PermissionError): self.operator.start(row['id'],row['revision'],row['planHash'],lambda op:op!='files.desktop.apply')
        self.assertEqual(self.store.get('mission',row['id'])['status'],'draft')

    def test_real_multi_step_document_task_has_durable_receipts(self):
        row=self.mission([{'tool':'document.create','args':self.fileargs('one.docx',content='A real document.\nSecond paragraph.')},
            {'tool':'document.read','args':self.fileargs('one.docx')},
            {'tool':'document.create','args':self.fileargs('copy.md',sourceStep=1)}])
        result=self.wait(self.start(row)['job']['id'])
        self.assertEqual(result['status'],'completed')
        saved=self.store.get('mission',row['id']); self.assertEqual(saved['status'],'completed')
        self.assertTrue(all(s['result']['verified'] for s in saved['steps']))
        self.assertEqual((self.work/'copy.md').read_text(),'A real document.\nSecond paragraph.')
        rebuilt=Operator(PlatformService(PlatformStore(self.store.path),JobManager()))
        self.assertEqual(rebuilt.reconcile()[0]['steps'][2]['result']['sha256'],hashlib.sha256((self.work/'copy.md').read_bytes()).hexdigest())

    def test_dead_read_is_resumable_but_dead_write_needs_review(self):
        for tool,args,expected in [('web.read',{'url':'https://example.com'},'interrupted'),('document.create',self.fileargs('x.txt',content='x'),'needs_review')]:
            row=self.mission([{'tool':tool,'args':args}]); self.store.patch('mission',row['id'],{'status':'running','ownerPid':0,'steps':[{'status':'running'}]})
            found=next(x for x in self.operator.reconcile() if x['id']==row['id']); self.assertEqual(found['status'],expected)

    def test_reused_pid_is_not_mistaken_for_original_owner(self):
        import os
        row=self.mission([{'tool':'web.read','args':{'url':'https://example.com'}}])
        self.store.patch('mission',row['id'],{'status':'queued','ownerPid':os.getpid(),'ownerBirth':0})
        self.assertEqual(self.operator.reconcile()[0]['status'],'interrupted')

    def test_unknown_side_effect_never_automatically_replayed(self):
        row=self.mission([{'tool':'document.create','args':self.fileargs('x.txt',content='hello')}])
        def effect(*args):
            (self.work/'x.txt').write_text('hello'); raise OSError('simulated loss before receipt')
        with patch.object(self.tools,'execute',side_effect=effect): self.wait(self.start(row)['job']['id'])
        saved=self.store.get('mission',row['id']); self.assertEqual(saved['status'],'needs_review')
        with self.assertRaises(Conflict): self.start(saved)
        saved=self.operator.resolve(saved['id'],saved['revision'],0,'accept')
        self.wait(self.start(saved)['job']['id'])
        final=self.store.get('mission',row['id']); self.assertEqual(final['status'],'completed_with_limits')
        self.assertFalse(final['steps'][0]['result']['verified'])

    def test_revoked_folder_stops_later_steps(self):
        row=self.mission([{'tool':'document.create','args':self.fileargs('first.txt',content='first')},
            {'tool':'document.create','args':self.fileargs('second.txt',content='second')}])
        execute=self.tools.execute
        def revoke(tool,args,ctx,previous):
            result=execute(tool,args,ctx,previous); self.store.delete('operator_root',self.grant['id']); return result
        with patch.object(self.tools,'execute',side_effect=revoke): self.wait(self.start(row)['job']['id'])
        self.assertTrue((self.work/'first.txt').exists()); self.assertFalse((self.work/'second.txt').exists())

    def test_cancel_waits_for_current_change_and_preserves_receipt(self):
        row=self.mission([{'tool':'document.create','args':self.fileargs('first.txt',content='first')},
            {'tool':'document.create','args':self.fileargs('second.txt',content='second')}])
        execute=self.tools.execute
        def stop(tool,args,ctx,previous):
            result=execute(tool,args,ctx,previous); self.operator.cancel(row['id']); return result
        with patch.object(self.tools,'execute',side_effect=stop): self.wait(self.start(row)['job']['id'])
        saved=self.store.get('mission',row['id']); self.assertEqual(saved['status'],'cancelled')
        self.assertEqual(saved['steps'][0]['status'],'completed'); self.assertFalse((self.work/'second.txt').exists())

    def test_completed_file_change_blocks_stale_resume(self):
        (self.work/'one.txt').write_text('before')
        row=self.mission([{'tool':'document.read','args':self.fileargs('one.txt')}])
        self.store.patch('mission',row['id'],{'status':'interrupted','steps':[{'status':'completed','result':{'sha256':hashlib.sha256(b'before').hexdigest()}}]})
        (self.work/'one.txt').write_text('after'); row=self.store.get('mission',row['id'])
        with self.assertRaises(Conflict): self.start(row)

class FileTests(Fixture):
    def test_summary_citations_are_kept_in_document_even_if_model_omits_them(self):
        with patch('core.brain.local_llm.chat_local',return_value='Result 42. See https://invented.invalid/fake'):
            result=self.tools.execute('evidence.summarize',{'sourceStep':0},Context(),[{'url':'https://example.com/actual','title':'Actual source','checkedAt':'2026-10-18','text':'42'}])
        self.assertIn('https://example.com/actual',result['text']);self.assertNotIn('https://invented.invalid',result['text'])
        self.tools.execute('document.create',self.fileargs('cited.docx',sourceStep=0),Context(),[result])
        content=self.tools.execute('document.read',self.fileargs('cited.docx'),Context(),[])
        self.assertIn('https://example.com/actual',content['text']);self.assertIn('2026-10-18',content['text'])
    def test_source_restore_round_trip_keeps_a_recovery_snapshot(self):
        from core.assistant_platform.releases import capture_release,restore_release
        project=self.root/'source-fixture';(project/'core').mkdir(parents=True)
        source=project/'core/example.py';source.write_text('before')
        with patch('core.assistant_platform.releases.protect_storage'):
            saved=capture_release(self.store,root=project);source.write_text('after')
            result=restore_release(self.store,saved['id'],root=project)
        self.assertEqual(source.read_text(),'before');self.assertTrue(self.store.get('release',result['recoverySnapshot']))

    def test_paths_protected_names_network_and_overwrite_blocked(self):
        for path in ['../escape.txt','C:\\outside.txt','a:stream.txt','.env','secret.txt','data/file.txt','\\\\server\\x.txt']:
            with self.assertRaises((ValueError,PermissionError)): file_path(self.store,self.grant['id'],path,exists=False)
        (self.work/'one.txt').write_text('keep')
        with self.assertRaises(ValueError): self.tools.execute('document.create',self.fileargs('one.txt',content='replace'),Context(),[])
        self.assertEqual((self.work/'one.txt').read_text(),'keep')

    def test_office_archive_limits_and_external_links(self):
        path=self.work/'links.xlsx'
        with zipfile.ZipFile(path,'w') as z:z.writestr('xl/externalLinks/externalLink1.xml','data')
        with self.assertRaises(ValueError): zip_check(path)

    def test_spreadsheets_create_and_edit_copy_round_trip(self):
        receipt=self.tools.execute('spreadsheet.create',self.fileargs('table.xlsx',rows=[['Task','Count'],['=DANGEROUS()',3]]),Context(),[])
        self.assertTrue(receipt['verified'])
        result=self.tools.execute('spreadsheet.copy_edit',self.fileargs('table.xlsx',output='changed.xlsx',cells={'B2':4,'A3':'@formula'}),Context(),[])
        self.assertTrue(result['verified']); self.assertFalse(result['formulasCalculated'])
        rows=self.tools.execute('spreadsheet.read',self.fileargs('changed.xlsx'),Context(),[])['rows']
        self.assertEqual(rows[1],["'=DANGEROUS()",4]); self.assertEqual(rows[2][0],"'@formula")
        self.assertEqual(self.tools.execute('spreadsheet.read',self.fileargs('table.xlsx'),Context(),[])['rows'][1][1],3)

    def test_vscode_uses_fixed_argument_list_and_is_honest_about_verification(self):
        (self.work/'sample.py').write_text('print(1)')
        with patch('core.assistant_operator.tools.subprocess.Popen') as launch,patch.object(Path,'is_file',return_value=True):
            result=self.tools.execute('vscode.open',self.fileargs('sample.py',line=7),Context(),[])
        self.assertFalse(result['verified']); self.assertFalse(launch.call_args.kwargs['shell'])
        self.assertEqual(launch.call_args.args[0][-1],str(self.work/'sample.py')+':7')

class ContinuityTests(Fixture):
    def record(self,**kw): return self.operator.continuity({'kind':'goal','title':'Finish science class','detail':'Complete the lab report.','status':'active',**kw})
    def test_linked_records_persist_and_corrected_status_excludes_old_context(self):
        goal=self.record(); decision=self.record(kind='decision',title='Science lab plan',detail='Use the revised procedure.',links=[goal['id']])
        self.assertEqual(next(r for r in self.operator.context('science lab')['records'] if r['id']==decision['id'])['links'],[goal['id']])
        self.operator.continuity({k:v for k,v in {**decision,'status':'superseded'}.items() if k in {'kind','title','detail','status','links','source'}},decision['id'],decision['revision'])
        self.assertEqual(len(self.operator.context('science lab')['records']),1)
        self.assertEqual(Operator(self.platform).context('science lab')['records'][0]['id'],goal['id'])

    def test_secret_unknown_links_and_stale_edit_rejected(self):
        with self.assertRaises(ValueError):self.record(detail='password: not-for-memory')
        with self.assertRaises(ValueError):self.record(links=['missing'])
        row=self.record()
        with self.assertRaises(Conflict):self.operator.continuity({'kind':'goal','title':'new','detail':'new'},row['id'],999)

    def test_handoff_revision_and_progress_without_execution_authority(self):
        row=self.operator.handoff({'device':'phone','summary':'Lab research','nextStep':'Read the sources'},0)
        self.assertEqual(row['executionLocation'],'pc')
        self.assertEqual(self.operator.context('continue')['activeSession']['nextStep'],'Read the sources')
        with self.assertRaises(Conflict): self.operator.handoff({'device':'car','summary':'stale','nextStep':'stale'},0)

    def test_factual_suggestions_deduplicate_and_can_be_dismissed(self):
        now=datetime(2026,10,18,15,tzinfo=timezone.utc)
        events=[{'id':'a','title':'Class','start':(now+timedelta(minutes=30)).isoformat(),'end':(now+timedelta(hours=2)).isoformat()},
            {'id':'b','title':'Meeting','start':(now+timedelta(hours=1)).isoformat(),'end':(now+timedelta(hours=3)).isoformat()}]
        tasks=[{'id':'t','title':'Report','deadline':(now-timedelta(hours=1)).isoformat(),'status':'Pending'}]
        found=self.operator.suggestions(events=events,tasks=tasks,now=now)
        self.assertTrue(any(x['title']=='Calendar overlap' for x in found)); self.assertTrue(any('overdue' in x['title'] for x in found))
        key=found[0]['key']; self.operator.dismiss(key)
        self.assertNotIn(key,[x['key'] for x in self.operator.suggestions(events=events,tasks=tasks,now=now)])

    def test_encrypted_portable_continuity_round_trip_excludes_machine_grants(self):
        from core.assistant_platform.profiles import capture_profile,encode_profile,decode_profile,restore_profile
        from core.personal_memory.store import MemoryStore
        from core.personal_memory.insights import InsightStore
        record=self.record(); memory=MemoryStore(self.root/'memory.sqlite3'); insights=InsightStore(self.root/'insights.json')
        payload=capture_profile(self.store,memory_store=memory,insights=insights)
        self.assertEqual(payload['version'],4);self.assertNotIn('operator_root',payload);self.assertNotIn('missions',payload)
        raw=encode_profile(payload,'isolated portable passphrase');self.assertNotIn(b'Complete the lab report',raw)
        decoded=decode_profile(raw,'isolated portable passphrase'); target=PlatformStore(self.root/'destination/store.sqlite3')
        counts=restore_profile(decoded,target,memory_store=memory,insight_store=insights)
        self.assertEqual(counts['continuity'],1);self.assertEqual(target.get('continuity',record['id'])['detail'],'Complete the lab report.')
        legacy={**payload,'version':1};legacy.pop('continuity')
        self.assertEqual(decode_profile(encode_profile(legacy,'isolated portable passphrase'),'isolated portable passphrase')['version'],1)

class WebTests(unittest.TestCase):
    def dns(self,ip='93.184.216.34'): return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))]
    def test_ssrf_credentials_odd_ports_and_mixed_dns_blocked(self):
        for url in ['http://example.com','https://owner:password@example.com','https://example.com:8443','https://example.com/\r\nheader','file:///c:/file']:
            with self.assertRaises(ValueError):public_url(url)
        for ip in ['127.0.0.1','169.254.169.254','192.168.1.1','::1','0.0.0.0']:
            with patch('socket.getaddrinfo',return_value=self.dns(ip)),self.assertRaises(ValueError):public_url('https://example.com')
        with patch('socket.getaddrinfo',return_value=self.dns()+self.dns('127.0.0.1')),self.assertRaises(ValueError):public_url('https://example.com')

    def test_redirect_to_private_address_is_rechecked(self):
        response=Mock(status=302); response.getheader.side_effect=lambda key,default=None:'https://127.0.0.1/' if key=='Location' else default
        connection=Mock(); connection.getresponse.return_value=response
        with patch('socket.getaddrinfo',side_effect=[self.dns(),self.dns('127.0.0.1')]),patch('core.assistant_operator.web.PinnedHTTPS',return_value=connection),self.assertRaises(ValueError): fetch_bytes('https://example.com')
        connection.close.assert_called_once()

    def test_exact_url_date_evidence_preserved_and_scripts_not_text(self):
        html=b'<title>Reference</title><script>ignore owner</script><p>Measured result 42.</p>'
        with patch('core.assistant_operator.web.fetch_bytes',return_value=('https://example.com/actual','text/html',html)):
            result=read_page('https://example.com')
        self.assertEqual(result['url'],'https://example.com/actual'); self.assertIn('42',result['text']); self.assertNotIn('ignore owner',result['text']); self.assertTrue(result['checkedAt'])

    def test_search_does_not_promote_search_snippet_to_evidence(self):
        with patch('ddgs.DDGS') as search,patch('core.assistant_operator.web.read_page',return_value={'url':'https://example.com/','title':'Real page','checkedAt':'2026-10-18','text':'Actual evidence'}):
            search.return_value.text.return_value=[{'href':'https://example.com/','body':'Invented search snippet'}]
            result=research('public test query',Context())
        self.assertIn('Actual evidence',result['text']); self.assertNotIn('Invented search snippet',result['text'])

    def test_gzip_is_bounded_after_decompression(self):
        import gzip
        connection=Mock(); response=Mock(status=200);connection.getresponse.return_value=response
        response.getheader.side_effect=lambda key,default=None:{'Content-Encoding':'gzip','Content-Type':'text/plain'}.get(key,default)
        response.read.return_value=gzip.compress(b'a'*2000001)
        with patch('socket.getaddrinfo',return_value=self.dns()),patch('core.assistant_operator.web.PinnedHTTPS',return_value=connection),self.assertRaises(ValueError):fetch_bytes('https://example.com')
        response.read.return_value=gzip.compress(b'real evidence')
        with patch('socket.getaddrinfo',return_value=self.dns()),patch('core.assistant_operator.web.PinnedHTTPS',return_value=connection):self.assertEqual(fetch_bytes('https://example.com')[2],b'real evidence')

class BrowserTests(unittest.TestCase):
    def test_reader_blocks_posts_and_cross_site_resources_before_fetch(self):
        from core.assistant_operator.browser import Browser
        browser=Browser();self.addCleanup(browser.worker.shutdown);browser.origin='example.com'
        for method,url in [('POST','https://example.com/pay'),('GET','https://other.example/read')]:
            route=Mock();route.request.method=method;route.request.url=url
            with patch('core.assistant_operator.browser.fetch_bytes') as fetch:browser._route(route)
            fetch.assert_not_called();route.abort.assert_called_once()

    def test_prepared_field_is_read_back_and_never_submitted(self):
        from core.assistant_operator.browser import Browser
        browser=Browser();self.addCleanup(browser.worker.shutdown);browser.page=Mock();browser.page.is_closed.return_value=False
        element=Mock();element.count.return_value=1;element.get_attribute.side_effect=lambda name:'text' if name=='type' else None;element.input_value.return_value='public test'
        browser.page.get_by_label.return_value=element
        result=browser._run('browser.fill',{'label':'Search','value':'public test'})
        self.assertTrue(result['verified']);element.fill.assert_called_once_with('public test');element.click.assert_not_called();browser.page.keyboard.press.assert_not_called()
        with self.assertRaises(PermissionError):browser._run('browser.fill',{'label':'Password','value':'blocked'})

class PlannerTests(unittest.TestCase):
    def test_planner_rejects_nonlocal_endpoints_and_transport_redirects(self):
        from core.assistant_operator.planner import plan_json
        from core.assistant_operator.local_http import NoRedirect
        with patch('core.brain.local_llm.get_brain_settings',return_value={'endpoint':'https://external.example/api/chat'}),self.assertRaises(PermissionError):plan_json('synthetic task')
        with self.assertRaises(PermissionError):NoRedirect().redirect_request(None,None,302,'redirect',{},'https://external.example/')

    def test_structured_request_uses_zero_temperature_and_tool_schemas(self):
        from core.assistant_operator.planner import plan_json
        response=Mock();response.read.return_value=json.dumps({'message':{'content':'{"steps":[{"tool":"web.read","args":{"url":"https://example.com"}}]}'}}).encode()
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        transport=Mock();transport.open.return_value=response
        with patch('core.brain.local_llm.get_brain_settings',return_value={'endpoint':'http://127.0.0.1:11434/api/chat','keep_alive':'2m'}),patch('core.brain.local_llm.active_model',return_value='fixture-model'),patch('core.assistant_operator.local_http.opener',return_value=transport):result=plan_json('synthetic task')
        self.assertEqual(result['steps'][0]['tool'],'web.read')
        body=json.loads(transport.open.call_args.args[0].data);self.assertEqual(body['options']['temperature'],0)
        choices=body['format']['properties']['steps']['items']['anyOf']
        self.assertTrue(all(x['additionalProperties'] is False and x['properties']['args']['additionalProperties'] is False for x in choices))


class ScreenTests(unittest.TestCase):
    def test_synthetic_frame_goes_only_to_loopback_and_grant_is_consumed(self):
        from PIL import Image
        from core.assistant_operator.screen import Screen
        service=Screen();window={'handle':1,'pid':2,'created':3,'title':'Synthetic','process':'sample.exe'}
        frame=Image.new('RGB',(64,64),'white')
        response=Mock();response.read.return_value=json.dumps({'message':{'content':'A white synthetic frame.'}}).encode()
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        with patch('core.assistant_operator.screen.windows',return_value=[window]),patch('PIL.ImageGrab.grab',return_value=frame),patch('urllib.request.build_opener',return_value=opener):
            grant=service.grant(1);result=service.inspect(grant['id'],'Describe the test frame.')
        self.assertEqual(result['text'],'A white synthetic frame.');self.assertFalse(result['imageSaved']);self.assertEqual(service.grants,{})
        request=opener.open.call_args.args[0];self.assertEqual(request.full_url,'http://127.0.0.1:11434/api/chat')
        self.assertTrue(json.loads(request.data)['messages'][1]['images'])

    def test_expired_and_reused_window_grants_cannot_capture(self):
        from core.assistant_operator.screen import Screen
        service=Screen(); window={'handle':123,'pid':2,'created':1,'title':'Sample','process':'sample.exe'}
        with patch('core.assistant_operator.screen.windows',return_value=[window]): grant=service.grant(123)
        with patch('core.assistant_operator.screen.windows',return_value=[{**window,'created':2}]),patch('PIL.ImageGrab.grab') as capture,self.assertRaises(PermissionError):service.inspect(grant['id'],'What is visible?')
        capture.assert_not_called()
        with self.assertRaises(PermissionError):service.inspect(grant['id'],'again')

    def test_revoke_and_one_use_grant_do_not_leave_screen_enabled(self):
        from core.assistant_operator.screen import Screen
        service=Screen()
        with patch('core.assistant_operator.screen.windows',return_value=[{'handle':1,'title':'Sample'}]): service.grant(1)
        service.revoke(); self.assertEqual(service.grants,{})

class CarHandoffTests(Fixture):
    def test_car_briefing_speaks_changed_handoff_once_after_playback(self):
        from core.carplay_trigger.briefing_session import BriefingSessions
        when=datetime(2026,10,18,9,tzinfo=__import__('zoneinfo').ZoneInfo('America/Los_Angeles'))
        handoff={'device':'car','revision':1,'summary':'The lab notes are saved.','nextStep':'Review the sources when parked.'}
        service=BriefingSessions(self.root/'car',clock=lambda:when,handoff_loader=lambda:handoff)
        def audio(text,path):path.write_bytes(b'synthetic audio fixture')
        with patch('core.carplay_trigger.briefing_session.build_fresh_briefing',return_value=({'success':True},{})),patch('core.carplay_trigger.briefing_session.generate_piper_audio',side_effect=audio):
            first=service.start('first');self.assertIn('The lab notes are saved.',first['briefing_text']);service.played(first['session_id'])
            second=service.start('second');self.assertNotIn('The lab notes are saved.',second['briefing_text']);service.played(second['session_id'])
            handoff['revision']=2;handoff['nextStep']='Read the corrected notes when parked.'
            third=service.start('third');self.assertIn('corrected notes',third['briefing_text'])

    def test_optional_handoff_failure_does_not_break_briefing(self):
        from core.carplay_trigger.briefing_session import BriefingSessions
        service=BriefingSessions(self.root/'car',clock=lambda:datetime(2026,10,18,18,tzinfo=timezone.utc),handoff_loader=Mock(side_effect=OSError()))
        with patch('core.carplay_trigger.briefing_session.build_fresh_briefing',return_value=({'success':True},{})),patch('core.carplay_trigger.briefing_session.generate_piper_audio',side_effect=lambda text,path:path.write_bytes(b'fixture')):
            self.assertTrue(service.start('first')['success'])

class ApiTests(Fixture):
    def test_unavailable_suggestion_source_does_not_disable_missions(self):
        client=self.client()
        with patch('core.assistant_followthrough.service.local_calendar_snapshot',side_effect=OSError('unavailable')):
            result=client.get('/api/platform/operator/summary')
        self.assertEqual(result.status_code,200);self.assertTrue(result.json()['suggestionNotices'])

    def client(self,denied=None):
        from fastapi.testclient import TestClient
        from core.api.server import create_app
        class Gate:
            def authorize(self,operation): return operation is not None and operation!=denied
        self.stack.enter_context(patch('core.api.desktop_key.verify',side_effect=lambda key:key=='fixture-desktop'))
        self.stack.enter_context(patch('core.assistant_followthrough.service.local_task_snapshot',return_value=[]))
        self.stack.enter_context(patch('core.assistant_followthrough.service.local_calendar_snapshot',return_value=[]))
        self.stack.enter_context(patch('core.calendar_context.duty_status.read_overrides',return_value={'days':{},'revision':0}))
        client=self.stack.enter_context(TestClient(create_app(token_verifier=lambda t:t=='fixture-token',client_gate=Gate(),include_carplay=False,include_phone_app=False,platform_provider=lambda:self.platform)))
        client.headers['X-ZAENIA-API-TOKEN']='fixture-token'; return client

    def test_all_new_routes_are_classified_and_require_auth(self):
        from core.api.platform_routes import operation_for
        paths=[('GET','summary'),('GET','missions/id'),('POST','missions'),('POST','draft'),('POST','missions/id/start'),('POST','missions/id/resolve'),('POST','missions/id/cancel'),('POST','roots'),('DELETE','roots/id'),('POST','continuity'),('PATCH','continuity/id'),('DELETE','continuity/id'),('GET','handoff'),('PUT','handoff'),('GET','screen/windows'),('POST','screen/grant'),('DELETE','screen/grant'),('POST','screen/inspect'),('POST','suggestions/dismiss')]
        for method,path in paths:self.assertIsNotNone(operation_for(method,'/api/platform/operator/'+path),path)
        client=self.client();client.headers.clear()
        self.assertEqual(client.get('/api/platform/operator/summary').status_code,401)

    def test_phone_can_draft_but_cannot_execute_or_grant_screen(self):
        client=self.client(); path='/api/platform/operator'
        draft=client.post(path+'/missions',json={'title':'Example','steps':[{'tool':'web.read','args':{'url':'https://example.com'}}]}).json()
        for endpoint,body in [('/missions/'+draft['id']+'/start',{'revision':draft['revision'],'planHash':draft['planHash']}),('/screen/grant',{'handle':1}),('/roots',{'name':'work','path':str(self.work)})]:
            self.assertEqual(client.post(path+endpoint,json=body).status_code,403)
        self.assertEqual(client.get(path+'/screen/windows').status_code,403)
        self.assertEqual(client.get(path+'/summary').status_code,200)

    def test_denied_memory_scope_blocks_continuity_leak(self):
        client=self.client('memory.read')
        self.assertEqual(client.get('/api/platform/operator/summary').status_code,403)

    def test_desktop_executes_real_document_mission_via_existing_api(self):
        client=self.client(); path='/api/platform/operator'
        draft=client.post(path+'/missions',json={'title':'API document','steps':[{'tool':'document.create','args':self.fileargs('api.docx',content='Verified API output')}]}).json()
        response=client.post(path+'/missions/'+draft['id']+'/start',json={'revision':draft['revision'],'planHash':draft['planHash']},headers={'X-ZAENIA-DESKTOP-KEY':'fixture-desktop'})
        self.assertEqual(response.status_code,200,response.text);self.wait(response.json()['job']['id'])
        result=client.get(path+'/missions/'+draft['id']).json()
        self.assertEqual(result['status'],'completed');self.assertTrue(result['steps'][0]['result']['verified'])

    def test_natural_voice_and_text_use_shared_mission_ledger(self):
        from core.assistant_platform.conversation import read_or_start
        with patch('core.assistant_platform.service.platform',return_value=self.platform):
            answer=read_or_start('Research Python pathlib documentation',lambda op:True)
            self.assertIn('Review',answer);self.assertEqual(self.store.list('mission')[0]['status'],'draft')
            progress=read_or_start('Show my mission progress',lambda op:True)
            self.assertIn('0 of 2 steps',progress)
        self.assertEqual(self.store.list('job'),[])

if __name__=='__main__':unittest.main()
