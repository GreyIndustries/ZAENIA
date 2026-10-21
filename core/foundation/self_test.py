"""One combined security test, always isolated from the owner's live data."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

def run_self_tests() -> bool:
    with tempfile.TemporaryDirectory(prefix="zaenia-module1-check-") as directory:
        environment = os.environ.copy()
        environment["ZAENIA_FOUNDATION_DATA_DIR"] = directory
        environment["ZAENIA_FOUNDATION_TEST_ROOT"] = directory
        environment["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run([sys.executable,"-m","core.foundation.self_test","--worker"],env=environment)
        return result.returncode == 0

def worker(case: str | None = None) -> bool:
    if not os.environ.get("ZAENIA_FOUNDATION_DATA_DIR") or not os.environ.get("ZAENIA_FOUNDATION_TEST_ROOT"):
        raise RuntimeError("Security tests require an isolated data directory.")
    root = Path(os.environ["ZAENIA_FOUNDATION_TEST_ROOT"]).resolve()
    data_directory = Path(os.environ["ZAENIA_FOUNDATION_DATA_DIR"]).resolve()
    if not root.name.startswith("zaenia-module1-check-") or data_directory != (root / case if case else root):
        raise RuntimeError("Security test directory does not match its isolated worker.")
    import base64
    import copy
    from dataclasses import asdict
    from contextlib import closing
    from datetime import datetime,timezone
    import hashlib
    import json
    import sqlite3
    import time
    import types
    from unittest.mock import patch
    from argon2 import PasswordHasher
    from cryptography.fernet import Fernet,InvalidToken
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from core.foundation.auth import passkey as auth
    from core.foundation.auth import session as sessions
    from core.foundation.auth import voice_passkey as voice
    from core.foundation.auth.session import AuthSession,ActionGrant,Confirmation
    from core.foundation.client_gate import ScopedClientGate,CLIENT_CAPABILITIES
    from core.foundation.lifecycle import activation_binding,activate_foundation,backup_binding,export_policy_backup,restore_binding,restore_policy_backup
    from core.foundation.moral_code.engine import MoralCase,evaluate_moral_case
    from core.foundation.moral_code import vault as moral
    from core.foundation.moral_code.scripture_context import Corpus,CONTEXT_FILE,update_context
    from core.foundation.moral_code import scripture_context as scripture
    from core.foundation.rules import vault as rules
    from core.foundation.rules.models import ActionRequest,create_rule
    from core.foundation.rules.engine import RuleEngine,delete_rule,disable_rule,evaluate_operation
    from core.foundation.security.audit import audit
    from core.foundation.security.crypto import encrypt_text,decrypt_text,encrypt_text_scoped,decrypt_text_scoped,get_or_create_salt
    from core.foundation.security.io import atomic_write,protect_storage,file_lock
    from core.foundation.storage.paths import SECURE_DIR,PASSKEY_FILE,VAULT_FILE,MORAL_VAULT_FILE,SALT_FILE,AUDIT_FILE,AUTH_RATE_FILE,PROJECT_ROOT
    from core.api import auth as api
    TEST_PHRASE = "public isolated test fixture phrase 2026"
    CORPUS_PATH = PROJECT_ROOT / "data" / "scripture" / "corpus.sqlite3"

    class SecurityTests(unittest.TestCase):
        def setUp(self):
            # Each test gets a new process and directory. Never delete/reuse an
            # earlier test's credentials or silently ignore a failed cleanup.
            self.assertEqual(SECURE_DIR,root/self._testMethodName/"secure")
            self.assertFalse(SECURE_DIR.exists())
            SECURE_DIR.mkdir(parents=True)
            auth._PROOFS.clear();sessions._SESSIONS.clear();sessions._GRANTS.clear();sessions._CONFIRMATIONS.clear()
            auth.create_passkey(TEST_PHRASE,TEST_PHRASE)
            rules.create_default_vault(self.proof("rules.create"))
            moral.create_policy(self.proof("moral.create",{"charter_sha256":moral.DEFAULT_CHARTER_SHA256}))
            self.calls=[]

        def proof(self,op="session.open",payload=None):
            return auth.authenticate_passphrase(TEST_PHRASE,operation=op,payload=payload)

        def add(self,action,scope):
            rule=create_rule("Test scope","Reviewed test policy","soft",action,operations=(scope,))
            rules.add_rule(rule,self.proof("rules.add",rule.to_dict()))
            return rule

        @staticmethod
        def params(value):
            if set(value)!={"item"} or not isinstance(value["item"],str) or not 1<=len(value["item"])<=100:
                raise ValueError("Invalid resource parameters.")
            return value

        def engine(self,op="weather.read"):
            engine=RuleEngine.open(self.proof())
            engine.register(op,lambda p:self.calls.append(p.copy()) or "done",self.params)
            return engine

        def service(self):
            return ScopedClientGate(self.proof("api.service.open",{"capabilities":sorted(CLIENT_CAPABILITIES)}))

        def test_legacy_cipher_and_hash_compatibility(self):
            salt=SALT_FILE.read_bytes()
            old_key=base64.urlsafe_b64encode(Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(TEST_PHRASE.encode()))
            legacy={"version":1,"rules":rules.DEFAULT_HARD_RULES[:3]}
            atomic_write(VAULT_FILE,Fernet(old_key).encrypt(json.dumps(legacy).encode()))
            old_salt=SALT_FILE.read_bytes();old_hash=PASSKEY_FILE.read_bytes()
            binding=activation_binding()
            activate_foundation(self.proof("foundation.upgrade",binding),binding)
            self.assertEqual(SALT_FILE.read_bytes(),old_salt)
            self.assertEqual(PASSKEY_FILE.read_bytes(),old_hash)
            self.assertEqual(len(rules.load_vault(TEST_PHRASE)["rules"]),5)
            self.assertTrue((SECURE_DIR/"policy_versions").exists())

        def test_scoped_cipher_cannot_cross_domains(self):
            data=encrypt_text_scoped("speaker fixture",TEST_PHRASE,scope="speaker_profile_v1")
            self.assertEqual(decrypt_text_scoped(data,TEST_PHRASE,scope="speaker_profile_v1"),"speaker fixture")
            with self.assertRaises(InvalidToken):decrypt_text_scoped(data,TEST_PHRASE,scope="moral_code_v1")
            with self.assertRaises(InvalidToken):decrypt_text(data,TEST_PHRASE)

        def test_cached_string_is_not_fresh_auth(self):
            with self.assertRaises(PermissionError):auth.consume_fresh_auth(TEST_PHRASE,operation="rules.create")

        def test_password_echo_fallback_is_rejected(self):
            from getpass import GetPassWarning
            with patch.object(auth,"getpass",side_effect=GetPassWarning("would echo")):
                with self.assertRaises(RuntimeError):auth.require_passkey()

        def test_forged_auth_proof_rejected(self):
            proof=self.proof("test",{"a":1})
            forged=auth.AuthenticatedPassphrase(TEST_PHRASE);forged._nonce=proof._nonce
            with self.assertRaises(PermissionError):auth.consume_fresh_auth(forged,operation="test",payload={"a":1})

        def test_auth_exact_payload_and_one_use(self):
            proof=self.proof("test",{"a":1})
            with self.assertRaises(PermissionError):auth.consume_fresh_auth(proof,operation="test",payload={"a":2})
            auth.consume_fresh_auth(proof,operation="test",payload={"a":1})
            with self.assertRaises(PermissionError):auth.consume_fresh_auth(proof,operation="test",payload={"a":1})

        def test_auth_proof_expires(self):
            proof=self.proof("test")
            with patch("core.foundation.auth.passkey.time.monotonic",return_value=time.monotonic()+61):
                with self.assertRaises(PermissionError):auth.consume_fresh_auth(proof,operation="test")

        def test_wrong_credentials_and_persistent_rate_limit(self):
            for _ in range(5):self.assertFalse(auth.verify_passkey("incorrect test phrase"))
            self.assertFalse(auth.verify_passkey(TEST_PHRASE))
            with closing(sqlite3.connect(AUTH_RATE_FILE)) as db:
                failures,deadline=db.execute("SELECT failures,locked_until FROM attempts").fetchone()
            self.assertEqual(failures,5);self.assertGreater(deadline,time.time())

        def test_auth_database_handles_close_on_success_and_rejection(self):
            real_connect=sqlite3.connect;connections=[]
            def track(*args,**kwargs):
                db=real_connect(*args,**kwargs);connections.append(db);return db
            try:
                with patch.object(auth.sqlite3,"connect",side_effect=track):
                    self.assertTrue(auth.verify_passkey(TEST_PHRASE))
                    for _ in range(5):self.assertFalse(auth.verify_passkey("incorrect test phrase"))
                    self.assertFalse(auth.verify_passkey(TEST_PHRASE))
                self.assertEqual(len(connections),7)
                # Retain references deliberately: closure must not rely on GC.
                for db in connections:
                    with self.assertRaises(sqlite3.ProgrammingError):db.execute("SELECT 1")
                AUTH_RATE_FILE.unlink()  # Windows rejects this with an open handle.
                self.assertTrue(auth.verify_passkey(TEST_PHRASE))
            finally:
                for db in connections:db.close()

        def test_auth_database_handles_close_on_exception(self):
            real_connect=sqlite3.connect;connections=[]
            def track(*args,**kwargs):
                db=real_connect(*args,**kwargs);connections.append(db);return db
            try:
                with patch.object(auth.sqlite3,"connect",side_effect=track),patch.object(auth,"audit",side_effect=RuntimeError("isolated failure fixture")):
                    with self.assertRaises(RuntimeError):auth.verify_passkey(TEST_PHRASE)
                self.assertEqual(len(connections),1)
                with self.assertRaises(sqlite3.ProgrammingError):connections[0].execute("SELECT 1")
                self.assertTrue(auth.verify_passkey(TEST_PHRASE))
            finally:
                for db in connections:db.close()

        def test_scripture_database_handles_close_on_reads_and_errors(self):
            corpus=Corpus(CORPUS_PATH);real_connect=sqlite3.connect;connections=[]
            def track(*args,**kwargs):
                db=real_connect(*args,**kwargs);connections.append(db);return db
            class SetupFailure(sqlite3.Connection):
                def execute(self,sql,*args,**kwargs):
                    if sql=="PRAGMA query_only=ON":raise sqlite3.OperationalError("isolated setup failure fixture")
                    return super().execute(sql,*args,**kwargs)
            def failed_setup(*args,**kwargs):
                kwargs["factory"]=SetupFailure
                return track(*args,**kwargs)
            try:
                with patch.object(scripture.sqlite3,"connect",side_effect=track):
                    self.assertTrue(corpus.passage("1Jn.4.8")["words"])
                    self.assertTrue(corpus.search("God is love"))
                    with self.assertRaises(ValueError):corpus.passage("Jhn.21.99")
                with patch.object(scripture.sqlite3,"connect",side_effect=failed_setup):
                    with self.assertRaises(sqlite3.OperationalError):corpus._connect()
                self.assertEqual(len(connections),4)
                for db in connections:
                    with self.assertRaises(sqlite3.ProgrammingError):db.execute("SELECT 1")
            finally:
                for db in connections:db.close()

        def test_malformed_or_expensive_stored_hash_fails_closed(self):
            atomic_write(PASSKEY_FILE,b"$argon2id$v=19$m=999999999,t=999,p=999$bad$bad")
            self.assertFalse(auth.verify_passkey(TEST_PHRASE))

        def test_session_public_timestamp_does_not_authenticate(self):
            session=AuthSession();session.authenticated_at=datetime.now(timezone.utc)
            self.assertFalse(session.is_valid())
            with self.assertRaises(PermissionError):session.mark_authenticated("wrong fixture")
            self.assertFalse(session.is_valid())

        def test_session_expiry_and_owner_generation(self):
            session=AuthSession();session.mark_authenticated(self.proof())
            with patch("core.foundation.auth.session.time.monotonic",return_value=time.monotonic()+601):
                self.assertFalse(session.is_valid())
            session.mark_authenticated(self.proof())
            atomic_write(PASSKEY_FILE,auth.ph.hash(TEST_PHRASE).encode())
            self.assertFalse(session.is_valid())

        def test_grant_exact_action_identity_and_replay(self):
            session=AuthSession();session.mark_authenticated(self.proof())
            grant=session.reauthenticate("files.move",{"item":"A"},TEST_PHRASE)
            self.assertFalse(session.grant_valid(grant,"files.move",{"item":"B"}))
            self.assertFalse(session.grant_valid(ActionGrant(grant.token),"files.move",{"item":"A"}))
            self.assertTrue(session.grant_valid(grant,"files.move",{"item":"A"},consume=True))
            self.assertFalse(session.grant_valid(grant,"files.move",{"item":"A"}))

        def test_logout_revokes_grants_and_other_session_cannot_use(self):
            first=AuthSession();first.mark_authenticated(self.proof())
            second=AuthSession();second.mark_authenticated(self.proof())
            grant=first.reauthenticate("files.move",{"item":"A"},TEST_PHRASE)
            self.assertFalse(second.grant_valid(grant,"files.move",{"item":"A"}))
            first.logout();self.assertFalse(first.grant_valid(grant,"files.move",{"item":"A"}))

        def test_immutable_hard_rules_cannot_be_edited(self):
            draft=rules.load_vault(TEST_PHRASE);draft["rules"][0]["enabled"]=False
            proof=self.proof("rules.save",{"vault_digest":auth.payload_digest(draft)})
            with self.assertRaises(PermissionError):rules.save_vault(draft,proof)
            self.assertTrue(rules.load_vault(TEST_PHRASE)["rules"][0]["enabled"])

        def test_immutable_hard_rules_cannot_be_deleted_or_disabled(self):
            self.assertFalse(delete_rule("hard-owner-only",TEST_PHRASE)["deleted"])
            self.assertFalse(disable_rule("hard-owner-only",TEST_PHRASE)["disabled"])

        def test_soft_rule_changes_need_exact_fresh_auth(self):
            rule=self.add("deny","weather.read")
            with self.assertRaises(PermissionError):delete_rule(rule.id,TEST_PHRASE)
            self.assertTrue(disable_rule(rule.id,self.proof("rules.disable",{"rule_id":rule.id}))["disabled"])
            self.assertTrue(delete_rule(rule.id,self.proof("rules.delete",{"rule_id":rule.id}))["deleted"])

        def test_scoped_denials_apply_to_owner_management(self):
            self.add("deny","moral.notes.update")
            notes=["attempted change"]
            with self.assertRaises(PermissionError):moral.update_notes(notes,self.proof("moral.notes.update",{"notes_digest":auth.payload_digest(notes)}))
            self.assertEqual(moral.load_policy(TEST_PHRASE)["notes"],[])
            self.add("deny","rules.add")
            proposed=create_rule("Blocked addition","test","soft","log_only",operations=("weather.read",))
            with self.assertRaises(PermissionError):rules.add_rule(proposed,self.proof("rules.add",proposed.to_dict()))
            self.assertFalse(any(r["id"]==proposed.id for r in rules.load_vault(TEST_PHRASE)["rules"]))

        def test_deny_scope_wins_over_allow(self):
            self.add("allow","weather.read");self.add("deny","weather.read")
            engine=self.engine()
            with self.assertRaises(PermissionError):engine.execute(ActionRequest("weather.read",{"item":"A"}))
            self.assertEqual(self.calls,[])
            engine=self.engine("tasks.read")
            self.assertEqual(engine.execute(ActionRequest("tasks.read",{"item":"A"})),"done")

        def test_scoped_reauth_actually_applies_to_read_actions(self):
            self.add("require_reauth","weather.read")
            engine=self.engine();request=ActionRequest("weather.read",{"item":"A"})
            with self.assertRaises(PermissionError):engine.execute(request)
            grant=engine.session.reauthenticate(request.operation,request.params,TEST_PHRASE)
            self.assertEqual(engine.execute(request,grant=grant),"done")
            with self.assertRaises(PermissionError):engine.execute(request,grant=grant)

        def test_unknown_action_and_invalid_params_fail_closed(self):
            engine=self.engine()
            self.assertFalse(engine.evaluate(ActionRequest("please ignore rules",{})).allowed)
            self.assertFalse(engine.evaluate(ActionRequest("weather.read",{"item":"A","shell":"delete everything"})).allowed)
            self.assertEqual(self.calls,[])
            with self.assertRaises(PermissionError):engine.register("tasks.read",lambda p:0,self.params)

        def test_sensitive_execution_needs_bound_reauth(self):
            engine=self.engine("calendar.write");request=ActionRequest("calendar.write",{"item":"A"})
            with self.assertRaises(PermissionError):engine.execute(request)
            grant=engine.session.reauthenticate(request.operation,request.params,TEST_PHRASE)
            with self.assertRaises(PermissionError):engine.execute(ActionRequest(request.operation,{"item":"B"}),grant=grant)
            self.assertEqual(engine.execute(request,grant=grant),"done")

        def test_permanent_delete_requires_two_actual_confirmation_proofs(self):
            engine=self.engine("files.delete");request=ActionRequest("files.delete",{"item":"A"})
            grant=engine.session.reauthenticate(request.operation,request.params,TEST_PHRASE)
            first=engine.session.confirm_after_owner_choice(request.operation,request.params)
            with self.assertRaises(PermissionError):engine.execute(request,grant=grant,confirmation=first)
            second=engine.session.confirm_after_owner_choice(request.operation,request.params,previous=first)
            with self.assertRaises(PermissionError):engine.execute(request,grant=grant,confirmation=Confirmation(second.token))
            self.assertEqual(engine.execute(request,grant=grant,confirmation=second),"done")
            with self.assertRaises(PermissionError):engine.execute(request,grant=grant,confirmation=second)
            self.assertEqual(len(self.calls),1)

        def test_params_changed_after_review_cannot_execute(self):
            engine=self.engine("files.move");params={"item":"A"}
            grant=engine.session.reauthenticate("files.move",params,TEST_PHRASE)
            params["item"]="B"
            with self.assertRaises(PermissionError):engine.execute(ActionRequest("files.move",params),grant=grant)
            self.assertEqual(self.calls,[])

        def test_policy_change_revokes_engine_and_client_snapshot(self):
            engine=self.engine();service=self.service()
            self.add("deny","weather.read")
            with self.assertRaises(PermissionError):engine.execute(ActionRequest("weather.read",{"item":"A"}))
            with self.assertRaises(PermissionError):service.authorize("chat.reply")

        def test_legacy_check_is_diagnostic_only(self):
            proof=self.proof("rules.check",{"operation":"list_rules"})
            result=evaluate_operation("list_rules",proof)
            self.assertTrue(result["allowed"]);self.assertFalse(result["execution_authorized"])
            result=evaluate_operation("weather.read;delete",self.proof("rules.check",{"operation":"weather.read;delete"}))
            self.assertFalse(result["allowed"])

        def test_moral_limits_never_become_spiritual_punishment(self):
            for method in ("final_spiritual_condemnation","impose_atonement","vengeance","coerce","force_reconciliation","conceal_abuse"):
                self.assertEqual(evaluate_moral_case(MoralCase(facts_confirmed=True,proposed_methods=(method,))).decision,"BLOCK")
            self.assertEqual(evaluate_moral_case(MoralCase(threats=("evil person",))).decision,"ASK_FOR_CONTEXT")
            self.assertEqual(evaluate_moral_case(MoralCase(protective="yes")).decision,"BLOCK")

        def test_accountability_requires_protection_and_facts(self):
            self.assertEqual(evaluate_moral_case(MoralCase(purpose="accountability",facts_confirmed=True)).decision,"ASK_FOR_CONTEXT")
            case=MoralCase(purpose="accountability",facts_confirmed=True,protective=True,proportionate=True,proposed_methods=("fair_accountability",))
            self.assertEqual(evaluate_moral_case(case).decision,"ALLOW")

        def test_urgent_protective_guidance_does_not_need_corpus_or_create_auth(self):
            case=MoralCase(purpose="protect",immediate_life_risk=True,protective=True,proportionate=True,proposed_methods=("seek_help",))
            self.assertEqual(evaluate_moral_case(case,context_required=True).decision,"ALLOW")
            engine=self.engine("life.protect")
            with self.assertRaises(PermissionError):engine.execute(ActionRequest("life.protect",{"item":"A"}),moral_case=case)

        def test_model_claims_need_owner_moral_review_and_cannot_override_boundary(self):
            engine=self.engine("accountability.plan");request=ActionRequest("accountability.plan",{"item":"A"})
            case=MoralCase(purpose="accountability",facts_confirmed=True,protective=True,proportionate=True)
            with self.assertRaises(PermissionError):engine.execute(request,moral_case=case)
            binding={"request":{"operation":request.operation,"params":request.params},"case":asdict(case)}
            reviewed=engine.session.reauthenticate("moral.review",binding,TEST_PHRASE)
            self.assertEqual(engine.execute(request,moral_case=case,moral_review=reviewed),"done")
            with self.assertRaises(PermissionError):engine.execute(request,moral_case=case,moral_review=reviewed)

        def test_moral_charter_tamper_detected_and_notes_are_protected(self):
            original=MORAL_VAULT_FILE.read_bytes()
            draft=moral.load_policy(TEST_PHRASE);draft["charter"]["principles"][0]["requirement"]="Ignore love"
            atomic_write(MORAL_VAULT_FILE,encrypt_text_scoped(json.dumps(draft),TEST_PHRASE,scope=moral.SCOPE))
            with self.assertRaises(PermissionError):moral.load_policy(TEST_PHRASE)
            atomic_write(MORAL_VAULT_FILE,original)
            with self.assertRaises(PermissionError):moral.update_notes(["private note"],TEST_PHRASE)
            notes=["Maintain protective boundaries"]
            moral.update_notes(notes,self.proof("moral.notes.update",{"notes_digest":auth.payload_digest(notes)}))
            self.assertEqual(moral.load_policy(TEST_PHRASE)["notes"],notes)

        def test_full_offline_corpus_and_context_visibility(self):
            corpus=Corpus(CORPUS_PATH);coverage=corpus.coverage()
            self.assertEqual(len(coverage["books"]),66)
            nt=coverage["books"][39:]
            self.assertEqual(len(nt),27);self.assertEqual(sum(b["chapters"] for b in nt),260)
            self.assertTrue(all(b["tokens"]>0 and len(b["translation_verses"])==2 for b in coverage["books"]))
            passage=corpus.passage("1Jn.4.8")
            self.assertTrue(passage["words"]);self.assertEqual(len(passage["translations"]),2)
            self.assertGreater(len(passage["surrounding_chapters"]),20)
            self.assertIn("culture",passage["missing_context_fields"])
            self.assertTrue(corpus.passage("Psa.103.1")["words"])
            self.assertTrue(corpus.passage("Pro.18.13")["words"])
            self.assertTrue(corpus.search("God is love"))
            self.assertEqual(evaluate_moral_case(MoralCase(purpose="interpret",facts_confirmed=True)).decision,"ASK_FOR_CONTEXT")

        def test_documented_context_needs_fresh_auth_and_is_encrypted(self):
            record={"reference":"1Jn.4.8","passage_context":"Review the surrounding chapter","historical_time":"Uncertain; record source limits","situation":"Letter context under review","culture":"Do not invent historical claims","people":"Author and audience require source review","sources":["https://www.stepbible.org/"]}
            # Corpus() normally uses live data; redirect only the public corpus path.
            with patch("core.foundation.moral_code.scripture_context.SCRIPTURE_FILE",CORPUS_PATH),patch("core.foundation.moral_code.scripture_context.Corpus",side_effect=lambda:Corpus(CORPUS_PATH)):
                with self.assertRaises(PermissionError):update_context(record,TEST_PHRASE)
                update_context(record,self.proof("scripture.context.update",{"record_digest":auth.payload_digest(record)}))
            self.assertNotIn(b"Do not invent",CONTEXT_FILE.read_bytes())
            self.assertEqual(Corpus(CORPUS_PATH).passage("1Jn.4.8",passphrase=TEST_PHRASE)["reviewed_context"],record)

        def test_token_create_rotate_revoke_and_fresh_saver(self):
            token=api.generate_api_token()
            with self.assertRaises(PermissionError):api.save_api_token_hash(token)
            binding={"new_digest":api.hash_api_token(token),"previous_digest":""}
            api.save_api_token_hash(token,passphrase=self.proof("auth.token.create",binding))
            self.assertTrue(api.verify_api_token(token));self.assertFalse(api.verify_api_token(""));self.assertFalse(api.verify_api_token("wrong"))
            replacement=api.generate_api_token();previous=api.hash_api_token(token)
            binding={"new_digest":api.hash_api_token(replacement),"previous_digest":previous}
            api.save_api_token_hash(replacement,overwrite=True,passphrase=self.proof("auth.token.rotate",binding))
            self.assertFalse(api.verify_api_token(token));self.assertTrue(api.verify_api_token(replacement))
            api.revoke_api_token(self.proof("auth.token.revoke",{"previous_digest":api.hash_api_token(replacement)}))
            self.assertFalse(api.verify_api_token(replacement))
            self.assertNotIn(token.encode(),AUDIT_FILE.read_bytes())

        def test_scoped_clients_never_get_admin_or_sensitive_capabilities(self):
            service=self.service()
            self.assertTrue(service.authorize("chat.reply"))
            for operation in ("rules.delete","files.delete","auth.token.rotate","calendar.write","moral.notes.update","unknown"):
                self.assertFalse(service.authorize(operation))
            self.add("require_reauth","chat.reply")
            service=self.service();self.assertFalse(service.authorize("chat.reply"))

        def test_http_token_and_policy_guards(self):
            from fastapi.testclient import TestClient
            from core.api.server import create_app
            received=[]
            def handler(message,**kwargs):received.append(message);return {"reply":"protected reply"}
            token=api.generate_api_token()
            app=create_app(token_verifier=api.build_memory_token_verifier(token),chat_handler=handler,client_gate=self.service(),include_carplay=False)
            with TestClient(app) as client:
                self.assertEqual(client.get("/health").status_code,200)
                self.assertEqual(client.post("/api/chat",json={"message":"Hello"}).status_code,401)
                self.assertEqual(client.post("/api/chat",json={"message":"Hello"},headers={api.API_TOKEN_HEADER:"wrong"}).status_code,401)
                response=client.post("/api/chat",json={"message":"Hello"},headers={api.API_TOKEN_HEADER:token})
                self.assertEqual(response.status_code,200);self.assertFalse(response.json()["execution_authorized"])
                self.assertIn("God's love",received[0])
                self.add("deny","chat.reply")
                self.assertEqual(client.post("/api/chat",json={"message":"Hello"},headers={api.API_TOKEN_HEADER:token}).status_code,503)
            app=create_app(token_verifier=api.build_memory_token_verifier(token),chat_handler=handler,client_gate=self.service(),include_carplay=False)
            with TestClient(app) as client:
                self.assertEqual(client.post("/api/chat",json={"message":"Hello"},headers={api.API_TOKEN_HEADER:token}).status_code,403)

        def test_http_carplay_handlers_are_not_called_without_auth(self):
            from fastapi.testclient import TestClient
            fake_audio=types.ModuleType("core.carplay_audio.carplay_audio");fake_audio.get_default_audio_path=lambda:Path("unused.wav")
            fake_sessions=types.ModuleType("core.carplay_trigger.briefing_session")
            calls=[]
            class FakeSessions:
                def __init__(self):calls.append("initialized");raise RuntimeError("No live CarPlay service in this isolated test")
            fake_sessions.BriefingSessions=FakeSessions;fake_sessions.SessionConflict=type("SessionConflict",(Exception,),{});fake_sessions.SessionNotFound=type("SessionNotFound",(Exception,),{})
            with patch.dict(sys.modules,{"core.carplay_audio.carplay_audio":fake_audio,"core.carplay_trigger.briefing_session":fake_sessions}):
                from core.api.server import create_app
                token=api.generate_api_token()
                app=create_app(token_verifier=api.build_memory_token_verifier(token),chat_handler=lambda *a,**k:{"reply":"test"},client_gate=self.service())
                with TestClient(app) as client:
                    for method,path in (("POST","/api/carplay/briefing"),("POST","/api/carplay/answer"),("POST","/api/carplay/played"),("GET","/api/carplay/audio")):
                        self.assertEqual(client.request(method,path,json={}).status_code,401)
                self.assertEqual(calls,[])

        def test_policy_backup_restore_is_encrypted_and_tamper_fails(self):
            destination=SECURE_DIR.parent/"isolated-backup.zaebackup"
            destination.unlink(missing_ok=True)
            binding=backup_binding(destination)
            export_policy_backup(destination,self.proof("security.backup",binding),binding)
            self.assertNotIn(TEST_PHRASE.encode(),destination.read_bytes())
            self.assertNotIn(b"Protected Moral Compass",destination.read_bytes())
            added=self.add("deny","weather.read")
            binding=restore_binding(destination)
            restore_policy_backup(destination,self.proof("security.restore",binding),binding)
            self.assertFalse(any(r["id"]==added.id for r in rules.load_vault(TEST_PHRASE)["rules"]))
            before=VAULT_FILE.read_bytes();raw=destination.read_bytes()
            atomic_write(destination,raw[:-2]+b"XX")
            binding=restore_binding(destination)
            with self.assertRaises((InvalidToken,ValueError)):restore_policy_backup(destination,self.proof("security.restore",binding),binding)
            self.assertEqual(VAULT_FILE.read_bytes(),before)

        def test_missing_master_salt_never_generates_incompatible_replacement(self):
            SALT_FILE.unlink()
            with self.assertRaises(RuntimeError):get_or_create_salt()
            self.assertFalse(SALT_FILE.exists())

        def test_audit_never_stores_raw_message_or_passphrase(self):
            message="private confidential note fixture"
            audit("owner.note",message)
            data=AUDIT_FILE.read_bytes()
            self.assertNotIn(message.encode(),data);self.assertNotIn(TEST_PHRASE.encode(),data)
            self.assertIn(hashlib.sha256(message.encode()).hexdigest().encode(),data)

        def test_atomic_write_no_clobber_and_private_storage(self):
            target=SECURE_DIR/"atomic-test.bin";atomic_write(target,b"original",overwrite=False)
            with self.assertRaises(FileExistsError):atomic_write(target,b"replacement",overwrite=False)
            self.assertEqual(target.read_bytes(),b"original")
            self.assertTrue(protect_storage(SECURE_DIR))
            with file_lock(SECURE_DIR/"atomic-test.lock"):
                atomic_write(target,b"complete replacement")
            self.assertEqual(target.read_bytes(),b"complete replacement")

        def test_protected_paths_reject_symlinks(self):
            link=SECURE_DIR/"symlink.bin";target=SECURE_DIR/"target.bin";target.write_bytes(b"untouched")
            try:link.symlink_to(target)
            except OSError:self.skipTest("Creating symlinks is unavailable for this OS account")
            with self.assertRaises(PermissionError):atomic_write(link,b"changed")
            self.assertEqual(target.read_bytes(),b"untouched")

        def test_voice_phrase_never_authenticates_session_or_uses_missing_mic(self):
            self.assertFalse(AuthSession().is_valid())
            config={"allowed_device_name":"Approved fixture mic","allowed_hostapi":0,"last_known_index":1,"fallback_allowed":False}
            atomic_write(voice.VOICE_DEVICE_FILE,json.dumps(config).encode())
            with patch.object(voice,"list_input_devices",return_value=[]):
                with self.assertRaises(RuntimeError):voice.get_allowed_mic_index()
            with patch.object(voice,"list_input_devices",return_value=[{"index":2,"name":config["allowed_device_name"],"hostapi":0},{"index":3,"name":config["allowed_device_name"],"hostapi":0}]):
                with self.assertRaises(RuntimeError):voice.get_allowed_mic_index()

    names=unittest.defaultTestLoader.getTestCaseNames(SecurityTests)
    if case is not None:
        if case not in names:
            raise ValueError("Unknown isolated security check.")
        result=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite([SecurityTests(case)]))
        return result.testsRun==1 and result.wasSuccessful()

    # Exit of each child releases all OS handles before the parent cleans up.
    # A failed test cannot contaminate the credentials or policies of the next.
    started=time.monotonic();failures=[]
    print(f"Running {len(names)} security checks in separate temporary directories...",flush=True)
    for name in names:
        environment=os.environ.copy()
        environment["ZAENIA_FOUNDATION_DATA_DIR"]=str(root/name)
        completed=subprocess.run(
            [sys.executable,"-m","core.foundation.self_test","--worker","--case",name],
            env=environment,capture_output=True,text=True,encoding="utf-8",errors="replace",
        )
        print("." if completed.returncode==0 else "F",end="",flush=True)
        if completed.returncode:
            failures.append((name,completed.stdout,completed.stderr))
    print(f"\nRan {len(names)} isolated security checks in {time.monotonic()-started:.1f}s",flush=True)
    for name,stdout,stderr in failures:
        print(f"\nFAILED CHECK: {name}\n{stdout}{stderr}",flush=True)
    print(f"FAILED ({len(failures)} checks)" if failures else "OK",flush=True)
    return not failures

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker",action="store_true")
    parser.add_argument("--case")
    args=parser.parse_args()
    if args.case and not args.worker:parser.error("--case requires --worker")
    raise SystemExit(0 if (worker(args.case) if args.worker else run_self_tests()) else 1)
