"""Isolated note persistence, privacy, conflict and portability checks."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from core.assistant_platform.notes import Notes,validate_note
from core.assistant_platform.store import PlatformStore,Conflict


class NotesTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(TemporaryDirectory(prefix='zae-notes-',dir=Path(__file__).resolve().parents[2])))
        self.stack.enter_context(patch('core.assistant_platform.store.protect_storage'))
        self.store=PlatformStore(self.root/'private/store.sqlite3');self.notes=Notes(self.store)

    def note(self,**kw):return self.notes.save({'title':'Inspection ideas','body':'Check the spare tire.\nBring the service records.',**kw})

    def client(self,allowed=None):
        from fastapi.testclient import TestClient
        from core.api.server import create_app
        from core.assistant_platform.service import PlatformService
        from core.assistant_platform.jobs import JobManager
        service=PlatformService(self.store,JobManager())
        class Gate:
            def authorize(self,op):return op is not None and (allowed is None or op in allowed)
        client=self.stack.enter_context(TestClient(create_app(token_verifier=lambda t:t=='notes-fixture-token',client_gate=Gate(),include_carplay=False,include_phone_app=False,platform_provider=lambda:service)))
        client.headers['X-ZAENIA-API-TOKEN']='notes-fixture-token';return client

    def test_create_edit_and_reopen_preserve_multiline_text(self):
        row=self.note();created=row['createdAt']
        updated=self.notes.save({**row,'body':'First line\nSecond line\twith a tab.'},row['id'],row['revision'])
        reopened=Notes(PlatformStore(self.store.path)).get(row['id'])
        self.assertEqual(reopened['body'],updated['body']);self.assertEqual(reopened['createdAt'],created)
        with self.assertRaises(Conflict):self.notes.save(row,row['id'],row['revision'])

    def test_unicode_search_pinning_pagination_and_sql_stay_data(self):
        self.note(title='Café plans',body='Résumé details');pinned=self.note(title='Pinned',pinned=True)
        self.assertEqual(self.notes.list()['notes'][0]['id'],pinned['id'])
        self.assertEqual(self.notes.list('CAFÉ')['total'],1);self.assertEqual(self.notes.list('RÉSUMÉ')['total'],1)
        self.assertEqual(self.notes.list("'; DROP TABLE records; --")['total'],0)
        first=self.notes.list(limit=1);self.assertEqual(first['nextOffset'],1)
        self.assertEqual(len(self.notes.list(offset=1,limit=1)['notes']),1)

    def test_archive_restore_and_reference_consent(self):
        private=self.note();shared=self.note(title='Spare tire note',reference=True)
        result=self.notes.context('spare tire')
        self.assertEqual([x['id'] for x in result],[shared['id']]);self.assertNotIn(private['id'],str(result))
        archived=self.notes.save({**shared,'archived':True},shared['id'],shared['revision'])
        self.assertEqual(self.notes.list(archived=True)['notes'][0]['id'],shared['id']);self.assertEqual(self.notes.context('spare tire'),[])
        restored=self.notes.save({**archived,'archived':False},archived['id'],archived['revision'])
        self.assertEqual(self.notes.context('spare tire')[0]['id'],restored['id'])

    def test_bad_content_and_unknown_fields_rejected(self):
        for value in [{'title':'','body':'x'},{'title':'x','body':'x'*30001},{'title':'x','body':'bad\x00data'},{'title':'x','pinned':'true'},{'title':'x','execute':'shell'}]:
            with self.assertRaises(ValueError):validate_note(value)

    def test_api_requires_token_and_read_write_scopes(self):
        client=self.client({'memory.read'});row=self.note()
        self.assertEqual(client.get('/api/platform/notes').status_code,200)
        self.assertEqual(client.get('/api/platform/notes/'+row['id']).status_code,200)
        self.assertEqual(client.post('/api/platform/notes',json={'title':'Denied'}).status_code,403)
        self.assertEqual(client.get('/api/platform/notes',headers={'X-ZAENIA-API-TOKEN':'bad'}).status_code,401)

    def test_api_stale_revision_cannot_overwrite_phone_or_desktop_changes(self):
        client=self.client();path='/api/platform/notes'
        row=client.post(path,json={'title':'Shared note','body':'original'}).json()
        changed=client.put(path+'/'+row['id'],json={'title':'Shared note','body':'phone edit','revision':row['revision']})
        self.assertEqual(changed.status_code,200)
        self.assertEqual(client.put(path+'/'+row['id'],json={'title':'Shared note','body':'stale desktop edit','revision':row['revision']}).status_code,409)
        self.assertEqual(client.get(path+'/'+row['id']).json()['body'],'phone edit')
        self.assertEqual(client.put(path+'/'+row['id'],json={'title':'Missing revision'}).status_code,409)

    def test_encrypted_profile_includes_notes_and_old_versions_still_restore(self):
        from core.assistant_platform.profiles import capture_profile,encode_profile,decode_profile,restore_profile
        from core.personal_memory.store import MemoryStore
        from core.personal_memory.insights import InsightStore
        memory=MemoryStore(self.root/'memory.sqlite3');insights=InsightStore(self.root/'insights.json');row=self.note(reference=True)
        payload=capture_profile(self.store,memory_store=memory,insights=insights)
        encrypted=encode_profile(payload,'isolated notes passphrase');self.assertNotIn(b'spare tire',encrypted)
        decoded=decode_profile(encrypted,'isolated notes passphrase');target=PlatformStore(self.root/'restore/state.sqlite3')
        result=restore_profile(decoded,target,memory_store=memory,insight_store=insights)
        self.assertEqual(result['notes'],1);self.assertEqual(target.get('note',row['id'])['body'],row['body'])
        for version in [1,2]:
            old={**payload,'version':version};old.pop('notes')
            self.assertEqual(decode_profile(encode_profile(old,'isolated notes passphrase'),'isolated notes passphrase')['version'],version)

    def test_explicit_conversation_lookup_uses_saved_notes_not_document_index(self):
        from core.assistant_platform.conversation import read_or_start
        from types import SimpleNamespace
        self.note()
        with patch('core.assistant_platform.service.platform',return_value=SimpleNamespace(store=self.store)):
            reply=read_or_start('Search my notes for spare tire',lambda op:True)
            self.assertIn('Check the spare tire.',reply);self.assertIn('Inspection ideas',reply)
            denied=read_or_start('Search my notes for spare tire',lambda op:False)
            self.assertNotIn('Check the spare tire.',denied)

if __name__=='__main__':unittest.main()
