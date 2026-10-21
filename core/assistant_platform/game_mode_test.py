import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from core.assistant_platform import game_mode


class GameModeTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.file = self.dir / "game_mode.json"
        self.patch = mock.patch.object(game_mode, "STATE_FILE", self.file)
        self.patch.start()
        self.now = 0.0
        self.app = None
        self.unloads = 0
        self.records = []
        self.monitor = game_mode.GameModeMonitor(detect=lambda: self.app, unload=self._unload,
                                                 write=self.records.append, clock=lambda: self.now)

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _unload(self):
        self.unloads += 1
        return ["llama3.1:8b"]

    def tick(self, seconds=5):
        self.now += seconds
        self.monitor.step()

    def test_enters_after_twenty_seconds_and_unloads_once(self):
        self.app = "eldenring.exe"
        for _ in range(4):
            self.tick()
        self.assertFalse(self.monitor.active)
        self.tick()
        self.assertTrue(self.monitor.active)
        self.tick(); self.tick()
        self.assertEqual(self.unloads, 1)
        self.assertEqual(self.records[-1]["app"], "eldenring.exe")

    def test_alt_tab_briefly_keeps_game_mode_then_leaves(self):
        self.app = "valorant.exe"
        for _ in range(6):
            self.tick()
        self.app = None
        self.tick()
        self.assertTrue(self.monitor.active)  # a quick alt-tab doesn't end it
        self.tick(); self.tick()
        self.assertFalse(self.monitor.active)

    def test_short_fullscreen_moments_do_not_count(self):
        self.app = "vlc.exe"
        self.tick(); self.tick()
        self.app = None
        self.tick()
        self.app = "vlc.exe"
        self.tick(); self.tick()
        self.assertFalse(self.monitor.active)
        self.assertEqual(self.unloads, 0)

    def test_active_reads_fresh_state_only(self):
        now = datetime.now(timezone.utc)
        self.file.write_text(json.dumps({"active": True, "updatedAt": now.isoformat()}), encoding="utf-8")
        self.assertTrue(game_mode.active())
        self.assertEqual(game_mode.keep_alive("10m"), "1m")
        self.file.write_text(json.dumps({"active": True, "updatedAt": (now - timedelta(minutes=5)).isoformat()}), encoding="utf-8")
        self.assertFalse(game_mode.active())  # server stopped updating: not stuck in game mode
        self.assertEqual(game_mode.keep_alive("10m"), "10m")

    def test_overheard_speech_needs_her_name_during_games(self):
        from core.voice_listener import ambient
        self.file.write_text(json.dumps({"active": True, "updatedAt": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
        self.assertTrue(ambient._game_mode_without_name("push B, they're rotating"))
        self.assertFalse(ambient._game_mode_without_name("zae what time is it"))


if __name__ == "__main__":
    unittest.main()
