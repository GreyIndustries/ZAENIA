"""Installer dry-run uses disposable files and never stops or starts ZAE."""
import hashlib,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
@unittest.skipUnless(shutil.which('powershell.exe'),'Windows installer checks')
class InstallerTests(unittest.TestCase):
    def test_valid_and_tampered_package_check_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'scripts').mkdir();(root/'core/api').mkdir(parents=True);(root/'desktop').mkdir();(root/'core/api/update_routes.py').write_text('# test')
            for name in ['install_update.ps1','update_helpers.ps1']:shutil.copy2(ROOT/'scripts'/name,root/'scripts'/name)
            package=root/'updates/pending/system-0.32.0-test';(package/'dist-web').mkdir(parents=True);(package/'dist-web/index.html').write_text('synthetic');(package/'ZAENIA.exe').write_bytes(b'synthetic-not-an-exe')
            (package/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(b'synthetic-not-an-exe').hexdigest(),'deploymentRoot':str(root)}))
            args=['powershell.exe','-NoProfile','-File',str(root/'scripts/install_update.ps1'),'-Id',package.name,'-Root',str(root),'-CheckOnly']
            result=subprocess.run(args,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr);self.assertFalse((root/'data').exists())
            (package/'ZAENIA.exe').write_bytes(b'tampered');result=subprocess.run(args,capture_output=True,text=True);self.assertNotEqual(result.returncode,0);self.assertFalse((root/'data').exists())
    def test_process_selection_does_not_include_server_or_other_apps(self):
        script=". '"+str(ROOT/'scripts/update_helpers.ps1')+"'; $p=@([pscustomobject]@{Name='python';Path='C:\\Projects\\ZAENIA\\python.exe'},[pscustomobject]@{Name='desktop';Path='C:\\Other\\desktop.exe'},[pscustomobject]@{Name='ZAENIA';Path='C:\\Apps\\ZAENIA.exe'}); @(Get-ZaeInstallProcesses $p 'C:\\Apps\\ZAENIA.exe' 'C:\\Projects\\ZAENIA').Count"
        result=subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'1')
