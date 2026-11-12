"""Nightly improvement ideas: signals from the last day, evidence-only ideas, "never", and when it runs."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.assistant_platform import build_ideas
from core.assistant_platform.suggestions import Suggestions

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)


def turn(minutes, role, content, route=None):
    row = {"timestamp": (NOW - timedelta(minutes=minutes)).isoformat(), "role": role, "content": content}
    if route is not None or role == "assistant":
        row["route"] = route
    return json.dumps(row)


class SignalsTest(unittest.TestCase):
    def test_repeats_cant_false_claims_corrections_and_outages(self):
        with tempfile.TemporaryDirectory() as folder:
            log, uptime = Path(folder) / "c.jsonl", Path(folder) / "u.json"
            log.write_text("\n".join([
                turn(3000, "user", "log my water"),                                   # older than a day: ignored
                turn(50, "user", "log my water"), turn(49, "assistant", "I couldn't find a water tracker.", "normal"),
                turn(48, "user", "log my water"), turn(47, "assistant", "Done, sir. Logged 500 ml.", "normal"),
                turn(30, "user", "no, that's wrong"), turn(29, "assistant", "Sorry.", "normal"),
                turn(20, "user", "add 42 g protein"), turn(19, "assistant", "Logged 42 g protein.", "tab_action"),
            ]), encoding="utf-8")
            uptime.write_text(json.dumps({"events": [{"at": "2026-11-02T03:00", "part": "voice", "kind": "down"},
                                                     {"at": "2026-11-02T03:00", "part": "desktop", "kind": "down"}]}), encoding="utf-8")
            lines = build_ideas.gather_signals(NOW, conversation=log, uptime=uptime)
        text = "\n".join(lines)
        self.assertIn("repeated a request (2 times in a row): \"log my water\"", text)
        self.assertIn("She couldn't do it", text)
        self.assertIn("said it was done but no action ran", text)
        self.assertNotIn("42 g protein", text)                       # a real action isn't a false claim
        self.assertIn("corrected her", text)
        self.assertIn("voice part went down 1", text)
        self.assertNotIn("desktop", text)                            # the app being closed isn't a fault


class NightlyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Suggestions(Path(self.temp.name) / "s.json")
        self.prompts, self.notices = [], []

    def tearDown(self):
        self.temp.cleanup()

    def nightly(self, signals, reply):
        return build_ideas.NightlyIdeas(state=Path(self.temp.name) / "state.json", store=self.store,
                                        ask=lambda p: (self.prompts.append(p), reply)[1], signals=lambda: signals,
                                        busy=lambda: False, notify=self.notices.append, done=lambda: None)

    def test_ideas_become_fix_suggestions_and_never_is_respected(self):
        reply = json.dumps({"ideas": [{"title": "Add a water tracker", "why": "You asked twice and I couldn't.", "how": "Add water to Fitness.", "effort": "medium"}]})
        made = self.nightly(["Grey repeated a request: log my water"], reply).run(force=True)
        self.assertEqual([(i["for"], i["title"], i["status"]) for i in made], [("fix", "Add a water tracker", "new")])
        self.assertEqual(self.notices, [1])
        self.store.mark(made[0]["id"], "never", "No.")
        self.nightly(["Grey repeated a request: log my water"], reply).run(force=True)
        self.assertIn("NEVER to these kinds of change", self.prompts[-1])
        self.assertIn("Add a water tracker", self.prompts[-1])
        self.assertEqual(len(self.store.list()), 1)                  # the same title isn't added again

    def test_no_signals_no_ideas_and_no_brain_call(self):
        self.assertEqual(self.nightly([], "{}").run(force=True), [])
        self.assertEqual(self.prompts, [])

    def test_runs_only_at_night_once_a_day(self):
        nightly = self.nightly(["x"], "{}")
        self.assertTrue(nightly.due(datetime(2026, 11, 2, 3, 0).astimezone()))
        self.assertFalse(nightly.due(datetime(2026, 11, 2, 14, 0).astimezone()))
        nightly.run(force=True)
        self.assertFalse(nightly.due(datetime.now().astimezone().replace(hour=3)))


if __name__ == "__main__":
    unittest.main()
