import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.api import security_check as sc


def passing(argv, **_):
    return subprocess.CompletedProcess(argv, 0, "Ran 45 isolated security checks in 20.0s\nOK\n" if argv[-1].endswith("self_test")
                                       else "PASS: 12 closure checks\n", "")


class SecurityCheckTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        secure = root / "secure"
        self.patches = [
            patch.object(sc, "REPORT_DIR", root / "security_checks"),
            patch.object(sc, "SECURE_DIR", secure),
            patch.object(sc, "PASSKEY_FILE", secure / "passkey.hash"),
            patch.object(sc, "SALT_FILE", secure / "master.salt"),
            patch.object(sc, "VAULT_FILE", secure / "rules.vault"),
            patch.object(sc, "MORAL_VAULT_FILE", secure / "moral_code.vault"),
            patch.object(sc, "AUDIT_FILE", secure / "audit.log"),
            patch("core.api.auth.API_TOKEN_HASH_FILE", secure / "api_access.sha256"),
            patch("core.foundation.security.audit.audit", lambda *a, **k: None),
            patch("core.api.security_activity.recent_activity", lambda **_: {"events": []}),
        ]
        for item in self.patches:
            item.start()
        self.secure = secure

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.folder.cleanup()

    def set_up_secure(self):
        self.secure.mkdir()
        for name in ("passkey.hash", "master.salt", "rules.vault", "moral_code.vault", "api_access.sha256", "audit.log"):
            (self.secure / name).write_text("x", encoding="utf-8")

    def by_id(self, report):
        return {check["id"]: check for check in report["checks"]}

    def test_full_pass_is_saved_without_secret_contents(self):
        self.set_up_secure()
        (self.secure / "passkey.hash").write_text("SECRET-HASH-VALUE", encoding="utf-8")
        report = sc.run_security_check("manual", suite_runner=passing)
        checks = self.by_id(report)
        self.assertEqual(checks["self_test"]["status"], "pass")
        self.assertIn("45 checks passed", checks["self_test"]["detail"])
        self.assertEqual(checks["passkey"]["status"], "pass")
        saved = (sc.REPORT_DIR / f"{report['id']}.json").read_text(encoding="utf-8")
        self.assertNotIn("SECRET-HASH-VALUE", saved)
        self.assertEqual(json.loads(saved)["status"], report["status"])

    def test_missing_setup_and_failing_suite_are_reported(self):
        def failing(argv, **_):
            return subprocess.CompletedProcess(argv, 1, "FAILED CHECK: test_rules_vault\nFAILED (1 checks)\n", "")
        report = sc.run_security_check("manual", suite_runner=failing)
        checks = self.by_id(report)
        self.assertEqual(report["status"], "fail")
        self.assertIn("test_rules_vault", checks["self_test"]["detail"])
        self.assertEqual(checks["secure_dir"]["status"], "fail")
        self.assertEqual(checks["api_token"]["status"], "warn")  # token missing is a warning, passkey missing a failure
        self.assertEqual(checks["passkey"]["status"], "fail")

    def test_missing_test_file_is_named(self):
        def missing(argv, **_):
            return subprocess.CompletedProcess(argv, 1, "", "FileNotFoundError: [Errno 2] No such file or directory: 'C:\\\\x\\\\charter.json'")
        report = sc.run_security_check("manual", suite_runner=missing)
        self.assertIn("charter.json", self.by_id(report)["self_test"]["detail"])

    def test_suite_timeout_fails_that_suite_only(self):
        def slow(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        self.set_up_secure()
        checks = self.by_id(sc.run_security_check("manual", suite_runner=slow))
        self.assertEqual(checks["self_test"]["status"], "fail")
        self.assertEqual(checks["passkey"]["status"], "pass")

    def test_reports_are_pruned_and_listed_newest_first(self):
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with patch.object(sc, "KEEP", 3):
            for minute in range(5):
                sc.run_security_check("daily", now=start + timedelta(minutes=minute), suite_runner=passing)
        reports = sc.list_reports()
        self.assertEqual(len(reports), 3)
        self.assertEqual(reports[0]["id"], "20261001T000400Z")
        self.assertNotIn("checks", reports[0])

    def test_report_ids_cannot_reach_other_files(self):
        self.assertIsNone(sc.load_report("../secure/passkey"))
        self.assertIsNone(sc.load_report("20261001T000000Z"))

    def test_manual_runs_are_rate_limited_but_daily_is_not(self):
        runs = []
        def runner(trigger, mode=""):
            runs.append(trigger)
            sc._save({"id": "20261001T000000Z", "at": datetime.fromtimestamp(clock[0], timezone.utc).isoformat(),
                      "trigger": trigger, "status": "pass", "counts": {}, "headline": "ok", "seconds": 1, "checks": []})
        clock = [datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()]
        service = sc.SecurityCheckService(clock=lambda: clock[0], runner=runner)
        self.assertTrue(service.start_check("manual", wait=True)["started"])
        clock[0] += 60
        blocked = service.start_check("manual", wait=True)
        self.assertFalse(blocked["started"])
        self.assertGreater(blocked["retryAfter"], 0)
        self.assertTrue(service.start_check("daily", wait=True)["started"])
        clock[0] += sc.MIN_GAP_SECONDS
        self.assertTrue(service.start_check("manual", wait=True)["started"])
        self.assertEqual(runs, ["manual", "daily", "manual"])
        self.assertFalse(service.state()["running"])

    def test_one_check_at_a_time(self):
        service = sc.SecurityCheckService(runner=lambda *a, **k: None)
        service.running = True
        self.assertFalse(service.start_check("daily")["started"])

    def test_brain_context_only_for_security_questions(self):
        self.assertIsNone(sc.security_check_context("what's the weather"))
        self.assertIn("no check has run", sc.security_check_context("did your security check pass?"))
        def failing(argv, **_):
            return subprocess.CompletedProcess(argv, 1, "FAILED CHECK: test_x\n", "")
        sc.run_security_check("manual", suite_runner=failing)
        context = sc.security_check_context("Run me through the security report")
        self.assertIn("FAIL", context)
        self.assertIn("Security self-test", context)

    def test_routes_use_status_read(self):
        from core.api.ui_routes import operation_for
        self.assertEqual(operation_for("GET", "/api/security/checks"), "status.read")
        self.assertEqual(operation_for("POST", "/api/security/checks"), "status.read")
        self.assertEqual(operation_for("GET", "/api/security/checks/20261001T000000Z"), "status.read")
        self.assertIsNone(operation_for("GET", "/api/security/checks/..%2Fsecure"))


if __name__ == "__main__":
    unittest.main()
