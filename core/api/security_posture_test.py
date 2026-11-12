import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core.api import security_posture as sp

QUIET = {"failedSignins": 0, "denied": 0, "voiceRejected": 0, "unlockFailed": 0}


class PostureTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.secure = root / "secure"
        self.secure.mkdir()
        for name in ("passkey.hash", "master.salt", "rules.vault", "moral_code.vault", "speaker_profile.vault", "audit.log"):
            (self.secure / name).write_text("x")
        self.calibration({"genuine_min": .72, "impostor_max": .31}, .5)
        for name in ("SECURE_DIR", "PASSKEY_FILE", "SALT_FILE", "VAULT_FILE", "MORAL_VAULT_FILE", "SPEAKER_PROFILE_FILE", "AUDIT_FILE", "AUTH_RATE_FILE"):
            target = self.secure if name == "SECURE_DIR" else self.secure / {"PASSKEY_FILE": "passkey.hash", "SALT_FILE": "master.salt",
                "VAULT_FILE": "rules.vault", "MORAL_VAULT_FILE": "moral_code.vault", "SPEAKER_PROFILE_FILE": "speaker_profile.vault",
                "AUDIT_FILE": "audit.log", "AUTH_RATE_FILE": "auth_attempts.sqlite3"}[name]
            self.stack.enter_context(patch.object(sp, name, target))
        self.stack.enter_context(patch.object(sp, "_CACHE", {}))
        self.stack.enter_context(patch.object(sp, "api_listeners", lambda port: ["127.0.0.1"]))
        self.stack.enter_context(patch.object(sp, "tailscale_state", lambda: {"installed": True, "readable": True, "serving": True, "funnel": False}))
        self.stack.enter_context(patch.object(sp, "firewall_state", lambda: {"domain": True, "private": True, "public": True}))
        self.stack.enter_context(patch.object(sp, "day_signals", lambda: dict(QUIET)))
        self.stack.enter_context(patch("core.api.auth.API_TOKEN_HASH_FILE", self.secure / "api_access.sha256"))
        self.stack.enter_context(patch("core.api.desktop_key.is_paired", lambda: False))
        self.stack.enter_context(patch("core.api.mobile_voice_profile.configured", lambda: True))

    def tearDown(self):
        self.stack.close()

    def calibration(self, observed, threshold):
        (self.secure / "speaker_auth_calibration.yaml").write_text(json.dumps({"observed": observed, "threshold": threshold}))

    def report(self, failing=False):
        return {"at": "2099-01-01T00:00:00+00:00", "checks": [
            {"group": "tests", "id": "self_test", "title": "Security self-test", "status": "fail" if failing else "pass", "detail": "", "fix": "Run it."},
            {"group": "setup", "id": "gitignore", "title": "Private data is gitignored", "status": "pass", "detail": "Ignored.", "fix": ""},
            {"group": "setup", "id": "tracked_secrets", "title": "No secret files in git", "status": "pass", "detail": "Clean.", "fix": ""}]}

    def levels(self, posture):
        return {area["id"]: area["level"] for area in posture["areas"]}

    def test_healthy_setup_is_strong_and_unknowns_are_not_scored(self):
        posture = sp.assess("unattended", mobile_sessions=1, report=self.report())
        levels = self.levels(posture)
        self.assertEqual(levels["packages"], "unknown")
        self.assertTrue(all(level == "strong" for key, level in levels.items() if key != "packages"), levels)
        self.assertEqual((posture["score"], posture["level"]), (100, "strong"))

    def test_network_exposure_and_funnel_are_weak(self):
        with patch.object(sp, "api_listeners", lambda port: ["0.0.0.0"]):
            self.assertEqual(self.levels(sp.assess("unattended", report=self.report()))["network"], "weak")
        with patch.object(sp, "tailscale_state", lambda: {"installed": True, "readable": True, "serving": True, "funnel": True}):
            posture = sp.assess("unattended", report=self.report())
        self.assertEqual(self.levels(posture)["network"], "weak")
        self.assertEqual(posture["level"], "weak")  # any weak area makes the whole level weak
        with patch.object(sp, "firewall_state", lambda: {"domain": True, "private": True, "public": False}):
            self.assertEqual(self.levels(sp.assess("unattended", report=self.report()))["network"], "fair")

    def test_voice_margin_failed_tests_and_attack_signs(self):
        self.calibration({"genuine_min": .52, "impostor_max": .45}, .5)
        busy = {**QUIET, "failedSignins": 25, "denied": 60}
        with patch.object(sp, "day_signals", lambda: busy):
            posture = sp.assess("full", report=self.report(failing=True))
        levels = self.levels(posture)
        self.assertEqual((levels["voice"], levels["tests"], levels["signin"], levels["signals"], levels["mode"]),
                         ("fair", "weak", "weak", "weak", "fair"))
        recs = sp.recommendations(posture, self.report(failing=True))
        self.assertEqual(recs[0]["priority"], "high")
        self.assertEqual(len({item["fix"] for item in recs}), len(recs))  # no duplicates
        self.calibration({"genuine_min": .3, "impostor_max": .6}, .5)
        self.assertEqual(self.levels(sp.assess("unattended", report=self.report()))["voice"], "weak")

    def test_no_secret_contents_are_read(self):
        (self.secure / "passkey.hash").write_text("$argon2id$secret-hash")
        text = json.dumps(sp.assess("unattended", report=self.report()))
        self.assertNotIn("secret-hash", text)

    def test_improvements_compare_the_last_two_checks(self):
        older = {"id": "20990101T000000Z", "at": "2099-01-01T00:00:00+00:00", "status": "warn", "counts": {"pass": 1, "warn": 1, "fail": 0},
                 "checks": [{"id": "audit_log", "title": "Audit log", "status": "warn"}, {"id": "localhost", "title": "Server stays on this PC", "status": "pass"}],
                 "posture": {"score": 70, "areas": [{"id": "voice", "title": "Voice impersonation", "level": "fair"}]}}
        newer = {"id": "20990102T000000Z", "at": "2099-01-02T00:00:00+00:00", "status": "warn", "counts": {"pass": 1, "warn": 1, "fail": 0},
                 "checks": [{"id": "audit_log", "title": "Audit log", "status": "pass"}, {"id": "localhost", "title": "Server stays on this PC", "status": "warn"}],
                 "posture": {"score": 85, "areas": [{"id": "voice", "title": "Voice impersonation", "level": "strong"}]}}
        reports = {r["id"]: r for r in (older, newer)}
        with patch("core.api.security_check.list_reports", lambda limit=50: [newer, older][:limit]), \
             patch("core.api.security_check.load_report", lambda rid: reports.get(rid)):
            result = sp.improvements()
        self.assertEqual([point["score"] for point in result["trend"]], [70, 85])
        self.assertEqual((result["fixed"], result["broke"], result["stronger"]), (["Audit log"], ["Server stays on this PC"], ["Voice impersonation"]))


if __name__ == "__main__":
    unittest.main()
