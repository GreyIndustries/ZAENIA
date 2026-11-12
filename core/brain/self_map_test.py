"""ZAE's self-map: pages and tabs read from the app's source, what isn't built, and when it reaches the prompt."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.brain import local_llm, self_map

APP = '''import { PlanStudio } from "./components/plan/PlanStudio";
const MusicStudio = lazy(() => import('./components/music/MusicStudio').then(m => ({ default: m.MusicStudio })));
const nav = ([
  { id: "overview", label: "Overview", short: "Core", icon: "home" },
  { id: "tasks", label: "Tasks & Calendar", short: "Plan", icon: "calendar" },
  { id: 'music', label: 'Music', short: 'Music', icon: 'music' },
  { id: "assistant", label: "Assistant", short: "Assistant", icon: "bolt" },
] as { id: Section }[]);
const sections: Record<Section, { title: string; label: string; description: string }> = {
  overview: { title: "The Core", label: "CORE", description: "The living core." },
  tasks: { title: "Tasks", label: "PLAN", description: "Your schedule and tasks." },
  music: { title: 'Music', label: 'MUSIC', description: 'Plays and songs.' },
  assistant: { title: "Assistant", label: "MEMORY", description: "What ZAE remembers." },
};
  function sectionBody(id: Section): ReactNode {
    switch (id) {
      case 'music': return <MusicStudio/>;
      case "tasks":
      // Tasks and Calendar share one page.
      case "calendar": return <PlanStudio/>;
      case "assistant": return <PageTabs id="assistant" tabs={[
        { id: "front", label: "Today's edition", render: () => <Front/> },
        { id: "memory", label: "Memory & rules", render: () => <Rules/> },
      ]}/>;
      default: return null;
    }
  }
'''
PLAN = '''export function PlanStudio() {
  const tabs: [Tab, string][] = [["week", "Week"], ["day", "Day"]];
  const ranges = [["7", "7 days"]];
}'''
MUSIC = '''const TABS = [{ id: "dashboard", label: "Dashboard" }, { id: "song", label: "Song" }];'''


class SelfMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        src = Path(self.folder.name) / "src"
        (src / "components" / "plan").mkdir(parents=True)
        (src / "components" / "music").mkdir(parents=True)
        (src / "components" / "plan" / "PlanStudio.tsx").write_text(PLAN, encoding="utf-8")
        (src / "components" / "music" / "MusicStudio.tsx").write_text(MUSIC, encoding="utf-8")
        self.app = src / "App.tsx"
        self.app.write_text(APP, encoding="utf-8")
        self_map._cache.update(key=None, map=None)

    def tearDown(self) -> None:
        self_map._cache.update(key=None, map=None)
        self.folder.cleanup()

    def test_pages_tabs_and_descriptions_come_from_the_source(self) -> None:
        pages = {page["label"]: page for page in self_map.ui_pages(self.app)}
        self.assertEqual(list(pages), ["Overview", "Tasks & Calendar", "Music", "Assistant"])
        self.assertEqual(pages["Overview"]["tabs"], [])
        self.assertEqual(pages["Tasks & Calendar"]["tabs"], ["Week", "Day"])  # fall-through case, tuple list
        self.assertEqual(pages["Music"]["tabs"], ["Dashboard", "Song"])        # lazy import, object list
        self.assertEqual(pages["Assistant"]["tabs"], ["Today's edition", "Memory & rules"])
        self.assertEqual(pages["Tasks & Calendar"]["description"], "Your schedule and tasks.")

    def test_map_is_rebuilt_when_the_app_changes(self) -> None:
        self.assertNotIn("Fitness", self_map.summary(self.app))
        self.app.write_text(APP.replace('{ id: "assistant"', '{ id: "fitness", label: "Fitness", short: "F", icon: "x" },\n  { id: "assistant"'), encoding="utf-8")
        stamp = self.app.stat().st_mtime + 5
        os.utime(self.app, (stamp, stamp))  # a newer file, as after an edit
        self.assertIn("- Fitness page", self_map.summary(self.app))

    def test_summary_lists_pages_and_forbids_inventing(self) -> None:
        text = self_map.summary(self.app)
        self.assertIn("- Assistant page, sub-tabs: Today's edition, Memory & rules", text)
        self.assertIn("- Overview page\n", text)
        self.assertIn("Never invent", text)

    def test_full_text_says_what_is_not_built(self) -> None:
        text = self_map.full_text(self.app)
        self.assertIn("NOT BUILT YET", text)
        self.assertIn("Stream Studio (PLANNED)", text)
        self.assertIn("Plant growing systems (IDEA)", text)
        self.assertIn("Page \"Tasks & Calendar\" has the sub-tabs Week, Day.", text)
        self.assertLessEqual(len(self_map.full_text(self.app, limit=500)), 520)

    def test_questions_about_herself_are_recognised(self) -> None:
        for question in ("Do you have a hydroponics tab?", "where is the calendar setting", "which tab has my reminders",
                         "what's inside your app", "what can you do", "Can you track my plants?", "is there a page for finance",
                         "does the app have a music dashboard", "what features are planned"):
            self.assertTrue(self_map.about_self(question), question)
        with mock.patch.object(self_map, "APP", self.app):
            self.assertTrue(self_map.about_self("What's in Music?"))
            self.assertTrue(self_map.about_self("how do I use tasks"))
            self.assertFalse(self_map.about_self("play some music"))
        for question in ("what's the weather", "remind me to call mom at 5", "good morning", "how do plants grow", "can you remind me to do the dishes", ""):
            self.assertFalse(self_map.about_self(question), question)

    def test_full_map_reaches_the_prompt_only_for_questions_about_herself(self) -> None:
        with mock.patch.object(local_llm, "get_system_prompt", return_value="fixture system"), \
                mock.patch.object(self_map, "APP", self.app), \
                mock.patch("core.foundation.moral_code.vault.default_charter"), \
                mock.patch("core.foundation.moral_code.engine.guidance_for_generation", return_value="fixture charter"):
            asked = local_llm.build_messages("Do you have a hydroponics tab?")
            self.assertEqual(asked[2]["role"], "user")
            self.assertTrue(asked[2]["content"].startswith("Reference context only"))
            self.assertIn("ZAE SELF-MAP", asked[2]["content"])
            self.assertEqual(asked[-1], {"role": "user", "content": "Do you have a hydroponics tab?"})
            plain = local_llm.build_messages("remind me to call mom at 5")
            self.assertFalse(any("ZAE SELF-MAP" in message["content"] for message in plain))

    def test_real_app_map_covers_every_sidebar_page(self) -> None:
        pages = {page["label"]: page["tabs"] for page in self_map.ui_pages()}
        self.assertIn("Code Doctor & Files", pages)
        self.assertIn("ENTHON", pages["Code Doctor & Files"])
        self.assertIn("Playground", pages["Code Doctor & Files"])
        self.assertIn("Plan", pages["LIFE"])
        self.assertIn("Security", pages["Settings"])
        self.assertIn(self_map.summary().splitlines()[1].lstrip("- ").split(" page")[0], pages)
        self.assertIn("WHAT'S INSIDE YOU", local_llm.get_system_prompt())
        self.assertTrue(self_map.planned())


if __name__ == "__main__":
    unittest.main()
