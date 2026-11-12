import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.foundation.security import audit as audit_module


class AuditRotationTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.file = self.dir / "audit.log"
        self.patches = [mock.patch.object(audit_module, "AUDIT_FILE", self.file),
                        mock.patch.object(audit_module, "ensure_storage", lambda: None),
                        mock.patch.object(audit_module, "ROTATE_BYTES", 400)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_large_log_moves_to_archive_and_nothing_is_lost(self):
        for index in range(12):
            audit_module.audit("api.capability_checked", operation="status.read", reason_code="scoped_client_allowed")
        archived = sorted((self.dir / "audit_archive").glob("audit-*.log"))
        self.assertTrue(archived)
        lines = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in archived + [self.file])
        self.assertEqual(lines, 12)
        self.assertLess(self.file.stat().st_size, 400 + 200)
        self.assertEqual(json.loads(self.file.read_text(encoding="utf-8").splitlines()[-1])["event"], "api.capability_checked")

    def test_small_log_is_not_rotated(self):
        audit_module.audit("auth.verified", reason_code="owner_passkey_verified")
        self.assertFalse((self.dir / "audit_archive").exists())


if __name__ == "__main__":
    unittest.main()
