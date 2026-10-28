import unittest

from core.assistant_platform import code_doctor
from core.assistant_platform.code_doctor import PROJECT_ROOT, protected


class ProtectedCodeTest(unittest.TestCase):
    """Build Plan P0: Code Doctor fixes and Playground 'Implement' can't touch auth or permission-mapping code."""

    def test_permission_mapping_modules_are_protected(self):
        for rel in ("core/api/ui_routes.py", "core/api/platform_routes.py", "core/api/server.py", "core/api/ui_files.py",
                    "core/assistant_platform/capabilities.py", "core/foundation/auth/passkey.py",
                    "core/assistant_platform/code_doctor.py", "core/assistant_platform/playground.py", "data/secure/x.json"):
            self.assertTrue(protected(PROJECT_ROOT / rel), rel)

    def test_case_changes_do_not_bypass(self):
        self.assertTrue(protected(PROJECT_ROOT / "Core/API/UI_Routes.py"))
        self.assertTrue(protected(PROJECT_ROOT / "CORE/Foundation/new_file.py"))

    def test_ordinary_code_is_not_protected(self):
        for rel in ("core/assistant_platform/training.py", "desktop/src/App.tsx", "scripts/check_install.py"):
            self.assertFalse(protected(PROJECT_ROOT / rel), rel)

    def test_other_projects_are_not_protected(self):
        self.assertFalse(protected(PROJECT_ROOT.parent / "SomeOtherProject" / "core" / "api" / "ui_routes.py"))


if __name__ == "__main__":
    unittest.main()
