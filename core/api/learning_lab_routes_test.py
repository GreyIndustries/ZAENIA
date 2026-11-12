from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from core.api.learning_lab_routes import create_learning_lab_router
from core.api.research_workshop_routes import create_research_workshop_router
from core.api.ui_routes import operation_for
from core.assistant_platform.store import PlatformStore


class LearningRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=PlatformStore(Path(self.temp.name)/"records.sqlite3")
        self.allowed={"memory.read","memory.write","status.read","chat.reply"}
        def authorize(operation):
            if operation not in self.allowed:raise HTTPException(403,"Denied")
        def auth(request:Request):
            if request.headers.get("X-Test-Auth")!="synthetic":raise HTTPException(401,"Unauthorized")
            authorize(operation_for(request.method,request.url.path))
        app=FastAPI();app.include_router(create_learning_lab_router(auth,authorize,lambda:self.store));app.include_router(create_research_workshop_router(auth,authorize))
        self.client=TestClient(app);self.addCleanup(self.client.close);self.client.headers["X-Test-Auth"]="synthetic"

    def test_unauthenticated_requests_are_denied(self):
        self.client.headers.clear()
        self.assertEqual(self.client.get("/api/learning-lab/records/lessons").status_code,401)

    def test_memory_write_scope_is_required(self):
        self.allowed.remove("memory.write")
        self.assertEqual(self.client.post("/api/learning-lab/records/plans",json={"record":{"title":"Test","sections":{}}}).status_code,403)
        self.assertEqual(self.store.list("learning_lab_plans"),[])

    def test_records_persist_and_stale_changes_fail(self):
        base="/api/learning-lab/records/plans"
        row=self.client.post(base,json={"record":{"title":"Test","sections":{}}}).json()
        path=base+"/"+row["id"]
        self.assertEqual(self.client.put(path,json={"record":{"title":"Changed","sections":{}},"revision":1}).status_code,200)
        self.assertEqual(self.client.put(path,json={"record":{"title":"Old","sections":{}},"revision":1}).status_code,409)
        self.assertEqual(self.client.delete(path+"?revision=1").status_code,409)
        self.assertEqual(self.client.delete(path+"?revision=2").status_code,200)

    def test_evaluation_requires_read_scope_before_loading_lesson(self):
        self.allowed.remove("memory.read")
        self.assertEqual(self.client.post("/api/learning-lab/evaluate/"+"a"*32,json={"models":["test:1"]}).status_code,403)

    def test_saved_research_requires_read_scope(self):
        self.allowed.remove("memory.read")
        response=self.client.post("/api/research/workshop/analyze",json={"mode":"deep_dive","question":"Test","topicId":"a"*32})
        self.assertEqual(response.status_code,403)

    def test_unknown_collection_not_granted(self):
        self.assertEqual(self.client.get("/api/learning-lab/records/permissions").status_code,403)

    def test_real_core_registration_and_gate(self):
        from core.api.server import create_app
        class Gate:
            def authorize(self,operation):return operation in {'memory.read','memory.write'}
        with patch('core.assistant_platform.learning_lab.records',return_value=self.store):
            app=create_app(token_verifier=lambda token:token=='synthetic',client_gate=Gate(),include_carplay=False,include_phone_app=False)
        with TestClient(app) as client:
            client.headers['X-ZAENIA-API-TOKEN']='synthetic'
            result=client.post('/api/learning-lab/records/plans',json={'record':{'title':'Synthetic plan','sections':{}}})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(client.get('/api/learning-lab/records/plans').json()['items'][0]['title'],'Synthetic plan')


if __name__ == "__main__":unittest.main()
