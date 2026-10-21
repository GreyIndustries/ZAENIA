"""PC activity tracker tests: a fake window probe, no real desktop access."""
from __future__ import annotations

import unittest

from core.voice_listener.activity import ActivitySettings, ActivityTracker, foreground_window
from core.voice_listener.ambient import AmbientContext


class ActivityTest(unittest.TestCase):
    def tracker(self, windows, **settings):
        state = {"now": 1000.0, "window": windows[0]}
        tracker = ActivityTracker(settings=ActivitySettings(**settings), probe=lambda: state["window"],
                                  clock=lambda: state["now"])
        return tracker, state

    def test_tracks_current_window_and_time_per_app(self):
        tracker, state = self.tracker([("Code.exe", "brain_service.py - ZAENIA")])
        tracker.sample(0)
        state["now"] += 600; tracker.sample(10)
        state["window"] = ("chrome.exe", "Ollama docs - Google Chrome")
        state["now"] += 120; tracker.sample(20)
        text = tracker.describe()
        self.assertIn('Now: Chrome — "Ollama docs - Google Chrome"', text)
        self.assertIn("VS Code 10 min", text)
        self.assertIn("brain_service.py - ZAENIA", text)

    def test_private_titles_and_listed_apps_keep_only_the_app_name(self):
        for window in [("msedge.exe", "New InPrivate tab - Microsoft Edge"), ("chrome.exe", "Bank of X - Sign in"),
                       ("1Password.exe", "1Password"), ("Signal.exe", "Chat with Alex")]:
            with self.subTest(window=window):
                tracker, _ = self.tracker([window], hide_titles_for=("signal.exe",))
                tracker.sample(0)
                self.assertNotIn(' — "', tracker.describe())

    def test_sampling_is_throttled_and_history_expires(self):
        tracker, state = self.tracker([("Code.exe", "a.py")], sample_seconds=5, history_minutes=5)
        tracker.sample(0)
        state["window"] = ("chrome.exe", "b")
        tracker.sample(2)  # too soon: ignored
        self.assertEqual(len(tracker.spans), 1)
        state["now"] += 400; tracker.sample(10)
        self.assertNotIn("a.py", tracker.describe())

    def test_error_titles_are_flagged_and_disabled_records_nothing(self):
        tracker, _ = self.tracker([("WindowsTerminal.exe", "npm run build - failed")])
        tracker.sample(0)
        self.assertIn("error or failure", tracker.describe())
        tracker, _ = self.tracker([("Code.exe", "x")], enabled=False)
        tracker.sample(0)
        self.assertIsNone(tracker.describe())

    def test_activity_reaches_the_brain_context(self):
        tracker, _ = self.tracker([("Code.exe", "runtime.py")])
        tracker.sample(0)
        context = AmbientContext(activity=tracker.describe)
        self.assertIn("PC ACTIVITY", context.describe())
        broken = AmbientContext(activity=lambda: 1 / 0)
        self.assertIsNone(broken.describe())

    def test_real_probe_never_raises(self):
        result = foreground_window()
        self.assertTrue(result is None or (isinstance(result, tuple) and len(result) == 2))


if __name__ == "__main__":
    unittest.main()
