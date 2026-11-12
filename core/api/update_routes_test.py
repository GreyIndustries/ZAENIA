import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.api import update_routes


class UpdateRoutesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(update_routes, "PENDING_DIR", self.tmp / "pending"),
                        mock.patch.object(update_routes, "INSTALL_LOG", self.tmp / "installed.json"),
                        mock.patch.object(update_routes, "VERSIONS_FILE", self.tmp / "versions.json")]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def test_pending_needs_manifest_and_flags_ready(self):
        good = self.tmp / "pending" / "ui-0.16.0-20261109"
        good.mkdir(parents=True)
        (good / "manifest.json").write_text(json.dumps({"title": "Settings hub", "part":"ui", "version":"0.16.0"}), encoding="utf-8")
        (self.tmp / "pending" / "no-manifest").mkdir()
        (self.tmp / "pending" / "bad name!").mkdir()
        found = update_routes.pending_updates()
        self.assertEqual([item["id"] for item in found], ["ui-0.16.0-20261109"])
        self.assertFalse(found[0]["ready"])
        (good / "ZAENIA.exe").write_bytes(b"x")
        (good / "dist-web").mkdir()
        (good / "dist-web" / "index.html").write_text("<html>", encoding="utf-8")
        self.assertTrue(update_routes.pending_updates()[0]["ready"])

    def test_history_newest_first_and_ignores_junk(self):
        (self.tmp / "installed.json").write_text(json.dumps([{"id": "a"}, "junk", {"id": "b"}]), encoding="utf-8")
        self.assertEqual([item["id"] for item in update_routes.install_history()], ["b", "a"])

    def test_versions_missing_or_broken_is_empty(self):
        self.assertEqual(update_routes.running_versions(), {})
        (self.tmp / "versions.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(update_routes.running_versions(), {})

    def test_brain_models_added_to_nodes(self):
        (self.tmp / "versions.json").write_text(json.dumps({"nodes": {"talk": {"name": "Talk", "version": "0.11.0"}}}), encoding="utf-8")
        with mock.patch.object(update_routes, "_brain_models", return_value={"talk": "qwen3.5:4b"}):
            self.assertEqual(update_routes.running_versions()["nodes"]["talk"]["model"], "qwen3.5:4b")

    def test_real_version_file_is_valid(self):
        real = Path(__file__).resolve().parents[2] / "desktop" / "src" / "config" / "versions.json"
        data = json.loads(real.read_text(encoding="utf-8"))
        for key in ("system", "ui"):
            self.assertRegex(data[key]["version"], r"^0\.\d+\.\d+$")
        for group in ("tabs", "modules", "nodes"):
            for item in data[group].values():
                self.assertRegex(item["version"], r"^0\.\d+\.\d+$")

    def test_semver_is_numeric_not_lexical(self):
        self.assertGreater(update_routes.semver('0.10.0'),update_routes.semver('0.9.9'))
        self.assertIsNone(update_routes.semver('bad'))

    def test_stale_receipt_blocks_downgrade_but_source_bump_does_not(self):
        (self.tmp/'installed.json').write_text(json.dumps([{'part':'ui','version':'0.26.0','versions':{'ui':'0.26.0','system':'0.31.1'}}]))
        (self.tmp/'versions.json').write_text(json.dumps({'ui':{'version':'0.27.0'}}))
        for version in ['0.25.0','0.26.0','0.27.0']:
            folder=self.tmp/'pending'/('ui-'+version);folder.mkdir(parents=True);(folder/'dist-web').mkdir();(folder/'dist-web/index.html').write_text('test');(folder/'ZAENIA.exe').write_bytes(b'test');(folder/'manifest.json').write_text(json.dumps({'part':'ui','version':version}))
        rows={r['version']:r for r in update_routes.pending_updates()}
        self.assertFalse(rows['0.25.0']['ready']);self.assertTrue(rows['0.26.0']['stale']);self.assertTrue(rows['0.27.0']['ready'])


if __name__ == "__main__":
    unittest.main()
