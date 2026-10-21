"""Authenticated review workflow with disposable learning records."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from core.api.server import create_app
from core.personal_memory.insights import InsightStore


class LearningReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(dir=Path(__file__).resolve().parents[2]);self.addCleanup(self.temp.cleanup)
        self.store=InsightStore(Path(self.temp.name)/'insights.json')
        self.row=self.store.merge([{'text':'Sample user prefers detailed answers','kind':'working_style','evidence':'I prefer detailed answers'}])[0]
        self.patch=patch('core.personal_memory.insights.InsightStore',return_value=self.store);self.patch.start();self.addCleanup(self.patch.stop)

    def client(self,allowed):
        class Gate:
            def authorize(self,operation): return operation in allowed
        app=create_app(token_verifier=lambda token:token=='isolated-learning-token',client_gate=Gate(),include_carplay=False,include_phone_app=False)
        client=TestClient(app);self.addCleanup(client.close)
        client.headers['X-ZAENIA-API-TOKEN']='isolated-learning-token'
        return client

    def test_confirm_correct_and_reject(self):
        client=self.client({'memory.read','memory.write'})
        path='/api/assistant/insights/'+self.row['id']
        confirmed=client.patch(path,json={'revision':1})
        self.assertEqual(confirmed.status_code,200,confirmed.text)
        self.assertEqual(confirmed.json()['insight']['source'],'user_confirmed')
        self.assertEqual(client.patch(path,json={'revision':1,'text':'Sample user prefers concise answers'}).status_code,409)
        corrected=client.patch(path,json={'revision':2,'text':'Sample user prefers concise answers'})
        self.assertEqual(corrected.status_code,200,corrected.text)
        self.assertEqual(corrected.json()['insight']['text'],'Sample user prefers concise answers')
        self.assertEqual(client.delete(path).status_code,200)
        self.assertEqual(client.get('/api/assistant/insights').json()['insights'],[])

    def test_read_only_client_cannot_confirm_or_correct(self):
        client=self.client({'memory.read'})
        result=client.patch('/api/assistant/insights/'+self.row['id'],json={'revision':1})
        self.assertEqual(result.status_code,403)
        self.assertEqual(self.store.list()[0]['source'],'inferred')

    def test_credentials_and_sensitive_edits_are_rejected(self):
        client=self.client({'memory.write'})
        path='/api/assistant/insights/'+self.row['id']
        for text in ['My password is a secret','Sample user has depression']:
            self.assertEqual(client.patch(path,json={'revision':1,'text':text}).status_code,422)
        self.assertEqual(self.store.list()[0]['revision'],1)


if __name__=='__main__':unittest.main()
