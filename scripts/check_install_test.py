import tempfile
import unittest
from pathlib import Path

from scripts import check_install


class CheckInstallTest(unittest.TestCase):
    def test_reads_requirement_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "requirements.txt").write_text("# note\npyyaml\npypdf==6.21.1\n--index-url x\nuvicorn[standard]==0.54.0 ; os_name=='nt'\n", encoding="utf-8")
            self.assertEqual(check_install.requirements(Path(folder)), [("pyyaml", ""), ("pypdf", "6.21.1"), ("uvicorn", "0.54.0")])

    def test_reports_missing_packages_and_models(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "requirements.txt").write_text("surely-not-a-real-package-zae\n", encoding="utf-8")
            self.assertEqual(check_install.check_packages(Path(folder)), ["missing package surely-not-a-real-package-zae"])
            self.assertEqual(len(check_install.check_models(Path(folder))), len(check_install.MODELS))

    def test_every_live_requirement_is_installed(self):
        self.assertEqual(check_install.check_packages(), [])


if __name__ == "__main__":
    unittest.main()
