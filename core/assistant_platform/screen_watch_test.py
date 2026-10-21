import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.assistant_platform import screen_watch
from core.assistant_platform.screen_watch import ScreenWatcher, screen_context

MONITORS = [{"number": 1, "left": 0, "top": 0, "width": 2560, "height": 1440, "primary": 1},
            {"number": 2, "left": 2560, "top": 0, "width": 1920, "height": 1080, "primary": 0}]


class ScreenWatchTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.file = self.dir / "screen.json"
        self.colour = (10, 10, 10)
        self.private = False
        self.gaming = False
        self.now = 0.0
        self.described = []
        self.watcher = ScreenWatcher(capture=lambda m: Image.new("RGB", (320, 180), self.colour),
                                     list_monitors=lambda: MONITORS,
                                     describe=lambda jpeg, previous: self.described.append(previous) or f"note {len(self.described)}",
                                     private=lambda m: self.private, game_mode=lambda: self.gaming,
                                     clock=lambda: self.now, state_file=self.file)

    def tearDown(self):
        self.watcher.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def step(self, seconds=3):
        self.now += seconds
        self.watcher.step()

    def test_default_is_the_non_primary_monitor_and_bad_numbers_fail(self):
        self.assertEqual(self.watcher.start()["monitor"]["number"], 2)
        with self.assertRaises(ValueError):
            self.watcher.start(5)

    def test_notes_only_on_change_and_paced(self):
        self.watcher.start(2)
        self.step()
        self.assertEqual(len(self.watcher.notes), 1)
        self.step(); self.step()
        self.assertEqual(len(self.watcher.notes), 1)  # nothing changed
        self.colour = (240, 240, 240)
        self.step()
        self.assertEqual(len(self.watcher.notes), 1)  # changed, but within 20 s
        self.step(20)
        self.assertEqual(len(self.watcher.notes), 2)
        self.assertEqual(self.described[-1], "note 1")
        self.assertIn("note 2", screen_context(self.file))

    def test_private_window_pauses_and_drops_the_frame(self):
        self.watcher.start(2)
        self.step()
        self.private = True
        self.step()
        self.assertIsNone(self.watcher.latest_frame_b64())
        self.assertIn("paused", screen_context(self.file))

    def test_game_mode_slows_notes(self):
        self.watcher.start(2)
        self.step()
        self.gaming = True
        self.colour = (200, 0, 0)
        self.step(25)
        self.assertEqual(len(self.watcher.notes), 1)
        self.step(40)
        self.assertEqual(len(self.watcher.notes), 2)

    def test_stop_clears_notes_and_shared_file(self):
        self.watcher.start(2)
        self.step()
        self.watcher.stop()
        self.assertFalse(self.file.exists())
        self.assertIsNone(screen_context(self.file))

    def test_commands_and_questions(self):
        original = screen_watch.monitors
        screen_watch.monitors = lambda: MONITORS
        try:
            self.assertEqual(screen_watch.screen_command("watch my second monitor"), 2)
            self.assertEqual(screen_watch.screen_command("Zae, monitor my main screen"), 1)
            self.assertEqual(screen_watch.screen_command("keep an eye on my screen"), 2)
            self.assertEqual(screen_watch.screen_command("stop watching my screen"), 0)
            self.assertIsNone(screen_watch.screen_command("look at my screen, what's this error?"))
            self.assertIsNone(screen_watch.screen_command("I need a new monitor"))
        finally:
            screen_watch.monitors = original
        self.assertTrue(screen_watch.SCREEN_QUESTION.search("what's on my second monitor?"))
        self.assertFalse(screen_watch.SCREEN_QUESTION.search("should I buy a 4k monitor"))


if __name__ == "__main__":
    unittest.main()
