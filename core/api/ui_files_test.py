import unittest

from core.api import ui_files


class ProtectedPathTest(unittest.TestCase):
    def test_security_code_stays_read_only_whatever_the_letter_case(self):
        for rel in ("core/foundation/rules/engine.py", "core/Foundation/rules/engine.py",
                    "core/voice_Security/gate.py", "core/api/Auth.py", "core/api/UI_ROUTES.py",
                    "core/assistant_platform/Capabilities.py"):
            with self.subTest(rel=rel):
                self.assertTrue(ui_files.is_protected(rel))

    def test_edit_of_mixed_case_security_path_is_refused(self):
        with self.assertRaises(ui_files.FileToolError):
            ui_files._check_edit("core/Foundation/rules/engine.py", "0" * 64, "x")

    def test_ordinary_code_is_not_protected(self):
        self.assertFalse(ui_files.is_protected("core/brain/brain_service.py"))
        self.assertFalse(ui_files.is_protected("core/api/chat_files.py"))


if __name__ == "__main__":
    unittest.main()
