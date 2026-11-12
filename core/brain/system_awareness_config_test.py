import unittest
from pathlib import Path

import yaml

from core.brain.system_index import directory_is_ignored, matches_any_glob

CONFIG = Path(__file__).with_name("system_awareness_config.yaml")


class RetrievalExclusionTest(unittest.TestCase):
    """Build Plan P1: backups, snapshots and build output must not be indexed as live source."""

    def setUp(self):
        self.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["system_awareness"]

    def test_historical_and_generated_folders_are_excluded(self):
        ignored = self.config["ignore_directories"]
        for path in ("backups", "data/backups", "desktop/ui-backups", "desktop/ui-backup-20261012-203731", "module1_backups",
                     "desktop/src-tauri/target", "desktop/dist", "desktop/dist-web", "data/assistant_platform/releases", "restore_check"):
            self.assertTrue(directory_is_ignored(path, ignored), path)

    def test_live_source_is_still_indexed(self):
        ignored = self.config["ignore_directories"]
        for path in ("core", "core/brain", "desktop/src", "desktop/src-tauri/src", "scripts", "docs", "data/scripture"):
            self.assertFalse(directory_is_ignored(path, ignored), path)

    def test_lock_files_are_skipped(self):
        globs = self.config["ignore_globs"]
        self.assertTrue(matches_any_glob("desktop/package-lock.json", globs))
        self.assertTrue(matches_any_glob("desktop/src-tauri/Cargo.lock", globs))
        self.assertFalse(matches_any_glob("desktop/package.json", globs))


if __name__ == "__main__":
    unittest.main()
