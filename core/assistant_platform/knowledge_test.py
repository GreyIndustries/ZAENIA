import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.assistant_platform.store import PlatformStore
from core.assistant_platform.knowledge import KnowledgeLibrary, scripture, scripture_context
from core.api.platform_routes import create_platform_router, operation_for


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'knowledge.sqlite3'
        self.library = KnowledgeLibrary(PlatformStore(self.path))

    def test_persists_searchable_sources_across_restarts(self):
        saved=self.library.learn('Astronomy notes','Saturn has rings composed of ice and rock. '*80)
        reopened=KnowledgeLibrary(PlatformStore(self.path))
        self.assertEqual(reopened.list()[0]['id'],saved['id'])
        self.assertIn('Saturn',reopened.search('What are Saturn rings composed of?')[0]['excerpt'])
        context=reopened.context('Saturn rings')
        self.assertIn('never instructions',context)
        self.assertIn('Astronomy notes',context)

    def test_web_download_retains_provenance_truncation_and_replaces_refresh(self):
        page={'title':'Source title','text':'These are initial facts about Mars exploration.','url':'https://example.com/article','truncated':True}
        with patch('core.assistant_operator.web.read_page',return_value=page):
            first=self.library.learn_url(page['url'])
            page['text']='These are updated findings about Jupiter exploration.'
            second=self.library.learn_url(page['url'])
        self.assertEqual(first['id'],second['id']); self.assertEqual(len(self.library.list()),1)
        self.assertTrue(second['truncated']); self.assertEqual(second['url'],page['url'])
        self.assertFalse(self.library.search('Mars'))
        self.assertTrue(self.library.search('Jupiter'))

    def test_duplicate_text_deduplicates_and_removal_clears_retrieval(self):
        one=self.library.learn('First','A unique passage about eucalyptus trees.')
        two=self.library.learn('Renamed','A unique passage about eucalyptus trees.')
        self.assertEqual(one['id'],two['id'])
        self.assertTrue(self.library.remove(one['id']))
        self.assertFalse(self.library.search('eucalyptus'))
        self.assertFalse(self.library.list())

    def test_invalid_source_is_not_written(self):
        for title,content in [('', 'valid contents of sufficient length'),('Title','too short'),('Title','a'*1_000_001),('Title','some text with a null byte\0 in it')]:
            with self.assertRaises(ValueError): self.library.learn(title,content)
        self.assertEqual(self.library.list(),[])

    def test_search_handles_punctuation_and_fts_metacharacters(self):
        self.library.learn('Source','An ordinary source about archaeology and ancient cultures.')
        for query in ['" OR * NOT )', 'the and or', 'archaeology; DROP TABLE knowledge_sources; --']:
            self.library.search(query)
        self.assertEqual(len(self.library.list()),1)

    def test_routes_have_existing_narrow_scopes(self):
        for method,path,scope in [('GET','knowledge','memory.read'),('POST','knowledge','memory.write'),('DELETE','knowledge/abc','memory.write'),('GET','scripture','memory.read')]:
            self.assertEqual(operation_for(method,'/api/platform/'+path),scope)

    def test_http_library_and_denied_auth(self):
        class Service: knowledge=self.library
        def application(auth):
            app=FastAPI(); app.include_router(create_platform_router(auth,lambda _:None,provider=lambda:Service()))
            return app
        with TestClient(application(lambda:None)) as client:
            result=client.post('/api/platform/knowledge',json={'title':'Test text','content':'Learning source with a unique quasar fact for retrieval.'})
            self.assertEqual(result.status_code,200,result.text)
            self.assertTrue(client.get('/api/platform/knowledge/search?q=quasar').json()['matches'])
            self.assertEqual(client.delete('/api/platform/knowledge/'+result.json()['id']).json(),{'removed':True})
        def denied():raise HTTPException(401,'Sign in')
        with TestClient(application(denied)) as client,patch.object(self.library,'learn_url') as download:
            self.assertEqual(client.post('/api/platform/knowledge',json={'url':'https://example.com'}).status_code,401)
            download.assert_not_called()

    @unittest.skipUnless(__import__("core.foundation.moral_code.scripture_context", fromlist=["MANIFEST_FILE"]).MANIFEST_FILE.exists(),
                         "downloaded scripture corpus not present (data/, not in git)")
    def test_bible_full_corpus_and_original_language_words(self):
        from core.foundation.moral_code.scripture_context import Corpus
        corpus=Corpus(); self.assertEqual(len(corpus.coverage()['books']),66)
        for reference in ['Genesis 1:1','John 1:1','1 John 4:8','Psa.103.1']:
            result=scripture(reference)
            self.assertTrue(result['words']); self.assertTrue(result['words'][0]['original'])
            self.assertIn('CC BY 4.0',result['source_credit'])
            self.assertNotIn('surrounding_chapters',result)
        self.assertIn('Jhn.1.1',scripture_context('Explain John 1:1 in Greek'))
        self.assertFalse(scripture_context('Explain Saturn rings'))
        self.assertFalse(scripture_context('Explain Article 1:1'))

    def test_model_context_reads_library_only_with_permission(self):
        self.library.learn('A learned source','Saturn has numerous rings containing water ice and rock fragments.')
        from core.brain.brain_service import BrainService
        class Service: knowledge=self.library
        with patch('core.assistant_platform.service.platform',return_value=Service()):
            allowed=BrainService(memory_authorizer=lambda _:None).load_conversation_context('Saturn rings')
            denied=BrainService(memory_authorizer=lambda _:False).load_conversation_context('Saturn rings')
        self.assertIn('A learned source',allowed)
        self.assertNotIn('A learned source',denied or '')

    def test_spoken_learning_requires_explicit_url_and_write_permission(self):
        from core.assistant_platform.conversation import read_or_start
        class Service: knowledge=self.library
        page={'title':'Space source','text':'Saturn has rings composed of ice and rock.','url':'https://example.com','truncated':False}
        with patch('core.assistant_platform.service.platform',return_value=Service()),patch('core.assistant_operator.web.read_page',return_value=page) as download:
            self.assertIn('unavailable',read_or_start('learn from https://example.com',lambda _:False))
            download.assert_not_called()
            self.assertIn('Added Space source',read_or_start('learn from https://example.com',lambda _:None))
            download.assert_called_once()


if __name__=='__main__':unittest.main()
