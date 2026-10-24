import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.assistant_platform.game_coach import GameCoach, coach_command
from core.assistant_platform.web_lookup import WebLookup, safe_term, split_lookup


class CoachCommandTest(unittest.TestCase):
    def test_commands(self):
        for text in ("watch me play", "Zae, coach me", "analyze my gameplay", "turn on the game coach"):
            self.assertIs(coach_command(text), True, text)
        for text in ("stop watching me play", "turn off the coach", "stop coaching me"):
            self.assertIs(coach_command(text), False, text)
        self.assertIsNone(coach_command("what's on my screen"))


class GameCoachTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.now = 0.0
        self.state = {"active": True, "app": "cs2.exe"}
        self.lookups: list[str] = []
        self.reviewed = []

        def review(game, moments, profile):
            self.reviewed.append((game, len(moments), profile))
            return {"style": "Aggressive entry player.", "decisions": ["Pushed B early"], "strengths": ["aim"],
                    "mistakes": ["overpeeks"], "tips": ["Hold angles longer"], "profile": f"Aggressive (was {profile})"}

        def look_up(term, hint=""):
            self.lookups.append(f"{term} {hint}".strip())
            return {"title": term.title(), "summary": "A tactical shooter.", "source": "Wikipedia"}

        self.coach = GameCoach(folder=Path(self.folder.name), game_state=lambda: self.state,
                               capture=lambda monitor: Image.new("RGB", (64, 36)), monitor=lambda: {"number": 1},
                               title=lambda app: "Counter-Strike 2",
                               describe=lambda jpeg, previous, prompt: "Grey pushes B site with the AWP.\nLOOKUP: AWP",
                               look_up=look_up, review=review, clock=lambda: self.now)

    def tearDown(self):
        self.folder.cleanup()

    def play(self, looks):
        for _ in range(looks):
            self.now += 21
            self.coach.step()

    def test_watches_a_game_then_reviews_it_and_learns_the_style(self):
        self.coach.step()
        self.play(4)
        self.assertEqual(self.lookups[0], "Counter-Strike 2 video game")
        self.assertIn("AWP Counter-Strike 2", self.lookups)
        context = self.coach.context("")
        self.assertIn("playing Counter-Strike 2", context)
        self.assertIn("pushes B site", context)
        self.state = {}
        self.coach.step()
        self.assertEqual(self.reviewed[0][:2], ("Counter-Strike 2", 4))
        profile = json.loads((Path(self.folder.name) / "profile.json").read_text(encoding="utf-8"))
        self.assertEqual(profile["counter-strike-2"]["sessions"], 1)
        self.assertEqual(len(list((Path(self.folder.name) / "sessions").glob("*.json"))), 1)
        self.assertFalse((Path(self.folder.name) / "live.json").exists())
        # A second session builds on the first profile.
        self.state = {"active": True, "app": "cs2.exe"}
        self.coach.step(); self.play(3); self.state = {}; self.coach.step()
        self.assertEqual(self.reviewed[1][2], "Aggressive (was None)")
        self.assertIn("Hold angles longer", self.coach.context("how did i play last game?"))

    def test_off_means_no_watching(self):
        self.coach.set_enabled(False)
        self.play(3)
        self.assertEqual(self.coach.status()["session"], None)
        self.assertIsNone(self.coach.context(""))

    def test_short_session_is_not_reviewed(self):
        self.coach.step(); self.play(1); self.state = {}; self.coach.step()
        self.assertEqual(self.reviewed, [])

    def test_private_window_pauses_looking(self):
        self.coach.private = lambda monitor: True
        self.coach.step(); self.play(3)
        self.assertEqual(self.coach.status()["session"]["moments"], 0)

    def test_quiet_when_not_gaming_and_not_asked(self):
        self.state = {}
        self.assertIsNone(self.coach.context("what's the weather"))


class WebLookupTest(unittest.TestCase):
    def test_private_words_never_leave(self):
        for term in ("grey@example.com", "https://bank.example", "C:/Users/zacka", "card 4111111111111111", "my password"):
            self.assertIsNone(safe_term(term), term)
        self.assertEqual(safe_term("Elden Ring"), "Elden Ring")

    def test_wikipedia_then_cache_and_rate_limit(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "duckduckgo" in url:
                return {}
            if "list=search" in url:
                return {"query": {"search": [{"title": "Elden Ring"}]}}
            if "rest_v1" in url:
                return {"title": "Elden Ring", "extract": "Elden Ring is a 2022 action role-playing game.", "type": "standard"}
            return {}
        now = [1000.0]
        with tempfile.TemporaryDirectory() as folder:
            lookup = WebLookup(fetch=fetch, cache_file=Path(folder) / "cache.json", clock=lambda: now[0])
            self.assertIn("action role-playing", lookup.lookup("Elden Ring")["summary"])
            self.assertEqual(lookup.lookup("elden ring")["title"], "Elden Ring")  # cached
            self.assertEqual(len(calls), 3)
            self.assertIsNone(lookup.lookup("Malenia"))  # too soon after the last request
            now[0] += 30
            lookup.lookup("Malenia")
            self.assertEqual(len(calls), 6)

    def test_split_lookup(self):
        self.assertEqual(split_lookup("Error 0x80070005 in installer.\nLOOKUP: 0x80070005"), ("Error 0x80070005 in installer.", "0x80070005"))
        self.assertEqual(split_lookup("A code editor.\nLOOKUP: none"), ("A code editor.", None))
        self.assertEqual(split_lookup("Just a desktop."), ("Just a desktop.", None))


if __name__ == "__main__":
    unittest.main()
