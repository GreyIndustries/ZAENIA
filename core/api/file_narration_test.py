"""Reading a shared file out loud: sections with locations, narration order, and answers that point into the file."""
import json
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from core.api import file_narration as fn

STORM = ("Thunderstorms form when warm, moist air rises quickly.\n\n" * 4 +
         "Key numbers: a typical storm cell lasts 30 minutes and reaches 12 km high.\n\n" * 3 +
         "Storms affect weather and ecosystems by bringing rain and fixing nitrogen in soil.")


def fake_ask(model, prompt, **kwargs):
    if "JSON only" in prompt and "gist" in prompt:
        return json.dumps({"gist": "How thunderstorms form", "facts": ["a storm cell lasts 30 minutes"]})
    if "part numbers" in prompt:
        return json.dumps({"parts": [2]})
    if "This looks like" in prompt:
        return "This looks like it explains the cause of thunderstorms."
    return "ok"


class SectionTest(unittest.TestCase):
    def test_pages_and_lines_are_labelled(self):
        pdf = "[page 1]\nFirst page text here.\n\n[page 2]\nSecond page text here."
        self.assertEqual([s.location for s in fn.sectionize("a.pdf", pdf)], ["page 1", "page 2"])
        long = "\n".join(f"line {i} with some text to fill it up" for i in range(300))
        parts = fn.sectionize("log.txt", long, limit=1000)
        self.assertGreater(len(parts), 3)
        self.assertEqual(parts[0].location.split("–")[0], "lines 1")
        self.assertEqual([s.n for s in parts], list(range(1, len(parts) + 1)))
        self.assertLessEqual(len(parts), fn.MAX_SECTIONS)


class CitationTest(unittest.TestCase):
    def test_extracted_facts_reject_changed_numbers_signs_and_percentages(self):
        text = "The annual revenue total was 100 dollars. The margin was -2.5%. Version 2.1 shipped."
        for fact in ("The annual revenue total was 999 dollars.", "The annual revenue total was 10 dollars.",
                     "The margin was 2.5%.", "The margin was -2.5.", "Version 2.2 shipped."):
            with self.subTest(fact=fact):
                self.assertFalse(fn._supported(fact, text))
        self.assertTrue(fn._supported("The annual revenue total was 100 dollars.", text))
        self.assertTrue(fn._supported("The margin was -2.5%.", text))

    def test_a_cited_part_points_to_the_line_it_came_from(self):
        sections = fn.sectionize("storms.txt", STORM, limit=200)
        target = next(s for s in sections if "30 minutes" in s.text)
        target.gist = "Typical storm numbers"
        sources = fn.cited_sources(f"A cell lasts 30 minutes [{target.n}]. Nothing else.", sections)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["id"], str(target.n))
        self.assertIn("30 minutes", sources[0]["excerpt"])
        self.assertTrue(sources[0]["title"].startswith("storms.txt · "))
        self.assertEqual(fn.cited_sources("Nothing cited [99].", sections), [])


class TurnTest(unittest.TestCase):
    def brain(self):
        b = mock.Mock()
        b.prepare_turn.return_value = SimpleNamespace(messages=[])
        b.load_behavior_context.return_value = None
        b.model_context.return_value = None
        return b

    def setUp(self):
        patcher = mock.patch.object(fn, "SECTION_CHARS", 200)   # small parts, so a short file has several
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_turn(self, message, files=(), document=None):
        def stream(question, **kwargs):
            self.context = kwargs["conversation_context"]
            self.model = kwargs["model"]
            yield "It explains thunderstorms. A cell lasts 30 minutes [2]."
        with mock.patch("core.brain.local_llm.stream_chat_local", stream):
            return list(fn.narrate_and_answer(self.brain(), message, list(files), threading.Event(), document=document, ask=fake_ask,
                                              save=False, extract=lambda name, raw: ("text", raw.decode())))

    def test_summary_narrates_then_answers_with_talk(self):
        fn.forget_all()
        events = self.run_turn("what is this file?", [("storms.txt", STORM.encode())])
        kinds = [(e["type"], e.get("stage")) for e in events]
        self.assertEqual(kinds[0], ("narrate", "start"))
        self.assertEqual(events[0]["text"], "I'm looking at storms.txt now.")
        self.assertIn(("narrate", "impression"), kinds)
        self.assertLess(kinds.index(("narrate", "impression")), kinds.index(("text", None)))
        self.assertEqual(self.model, "qwen3.5:4b")                      # Talk writes the answer
        self.assertEqual(events[-1]["type"], "final")
        self.assertEqual(events[-1]["sources"], [])                      # a summary doesn't need to point anywhere

    def test_a_follow_up_uses_the_remembered_file_and_points_into_it(self):
        fn.forget_all()
        self.run_turn("summarize this", [("storms.txt", STORM.encode())])
        document = fn.recent_document("what are the key stats in the file?")
        self.assertIsNotNone(document)
        events = self.run_turn("what are the key stats in the file?", document=document)
        self.assertEqual(events[0]["text"], "I'm checking storms.txt for that.")
        self.assertFalse([e for e in events if e.get("stage") == "impression"])
        final = events[-1]
        self.assertTrue(final["sources"] and final["sources"][0]["source_type"] == "file")

    def test_unrelated_messages_never_pull_in_the_file(self):
        fn.forget_all()
        self.run_turn("summarize", [("storms.txt", STORM.encode())])
        self.assertIsNone(fn.recent_document("what's the weather like tomorrow?"))
        self.assertIsNone(fn.recent_document("remind me to call mom"))
        self.assertIsNotNone(fn.recent_document("where in the pdf does it say that?"))

    def test_page_section_cap_marks_document_and_answer_context_as_clipped(self):
        for count in (fn.MAX_SECTIONS, fn.MAX_SECTIONS + 1):
            with self.subTest(pages=count):
                fn.forget_all()
                text = "\n\n".join(f"[page {n}]\nSynthetic page {n} contains this short sentence."
                                   for n in range(1, count + 1))
                self.run_turn("what are the key stats in the file?", [("pages.pdf", text.encode())])
                document = fn.recent_document("where in the file?")
                self.assertEqual(len(document.sections), fn.MAX_SECTIONS)
                self.assertEqual(document.clipped, count > fn.MAX_SECTIONS)
                self.assertEqual("The file is longer than what was read" in self.context, count > fn.MAX_SECTIONS)

    def test_cancel_during_impression_does_not_wait_or_prepare_an_answer(self):
        brain = self.brain()
        stop = threading.Event()
        started = threading.Event()
        release = threading.Event()
        document = fn.Document("synthetic", ["short.txt"], fn.sectionize("short.txt", "A short synthetic document."))

        def ask(model, prompt, **kwargs):
            if "This looks like" in prompt:
                started.set()
                release.wait(timeout=2)
                return "This looks like a short document."
            return json.dumps({"gist": "A short synthetic document", "facts": []})

        def cancel():
            if started.wait(timeout=1):
                stop.set()
        canceller = threading.Thread(target=cancel)
        canceller.start()
        began = time.monotonic()
        try:
            events = list(fn.narrate_and_answer(brain, "summarize this", [], stop, document=document, ask=ask, save=False))
            self.assertLess(time.monotonic() - began, 0.5)
            self.assertTrue(stop.is_set())
            self.assertFalse(any(event["type"] in {"text", "final"} for event in events))
            brain.prepare_turn.assert_not_called()
        finally:
            release.set()
            canceller.join(timeout=1)


class BigFileTest(unittest.TestCase):
    def sections(self, count):
        return [fn.Section(n, "big.txt", f"lines {n}", f"Part {n} says the value is {n * 7} units and mentions topic{n}.") for n in range(1, count + 1)]

    def test_reading_order_starts_with_the_first_and_last_and_spreads_the_rest(self):
        order = [s.n for s in fn.reading_order(self.sections(16))]
        self.assertEqual(order[:2], [1, 16])
        self.assertEqual(sorted(order), list(range(1, 17)))
        self.assertEqual(order[2], 9)            # then the middle, so an early stop still saw the whole file
        self.assertEqual([s.n for s in fn.reading_order(self.sections(3))], [1, 2, 3])

    def test_every_brain_helps_and_everything_is_covered(self):
        sections = self.sections(14)
        used = []
        lock = threading.Lock()

        def ask(model, prompt, **kwargs):
            import time
            time.sleep(0.05)                      # real brains take a moment, so the others get their turns
            with lock:
                used.append((model, bool(kwargs.get("cpu"))))
            return json.dumps({"gist": "a part", "facts": ["the value is 7 units", "made up 999 gigawatts"]})
        skimmed = fn.read_all(sections, ask, threading.Event(), budget=20)
        self.assertEqual(skimmed, 0)
        self.assertTrue(all(s.gist == "a part" for s in sections))
        self.assertEqual({m for m, _ in used}, {"qwen3.5:9b", "qwen3.5:4b", "qwen3:1.7b"})   # Seek, Talk and Keep
        self.assertIn(("qwen3:1.7b", True), used)                                              # Keep works on the processor
        self.assertEqual(sections[0].facts, ["the value is 7 units"])                          # the invented fact is dropped

    def test_when_time_runs_out_the_rest_is_skimmed_not_waited_for(self):
        sections = self.sections(10)
        release = threading.Event()
        finished = threading.Event()
        timeouts = []
        called_back = []

        def slow(model, prompt, **kwargs):
            timeouts.append(kwargs["timeout"])
            release.wait(timeout=2)                # deliberately ignore the request timeout
            finished.set()
            return json.dumps({"gist": "read closely", "facts": []})
        started = time.monotonic()
        try:
            skimmed = fn.read_all(sections, slow, threading.Event(), budget=0.1,
                                  on_done=lambda section, count: called_back.append(section.n))
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertTrue(timeouts)
            self.assertTrue(all(0 < timeout <= 0.1 for timeout in timeouts))
            self.assertEqual(skimmed, len(sections))
            frozen = [(s.gist, list(s.facts)) for s in sections]
        finally:
            release.set()
        self.assertTrue(finished.wait(timeout=1))
        time.sleep(0.05)                           # give late results a chance to publish
        self.assertEqual([(s.gist, s.facts) for s in sections], frozen)
        self.assertEqual(called_back, [])
        self.assertTrue(all(s.gist for s in sections))

    def test_cancellation_returns_promptly_and_freezes_late_results(self):
        sections = self.sections(10)
        stop = threading.Event()
        started = threading.Event()
        release = threading.Event()
        called_back = []

        def blocked(model, prompt, **kwargs):
            started.set()
            release.wait(timeout=2)
            return json.dumps({"gist": "too late", "facts": []})

        def cancel():
            if started.wait(timeout=1):
                stop.set()
        canceller = threading.Thread(target=cancel)
        canceller.start()
        began = time.monotonic()
        try:
            skimmed = fn.read_all(sections, blocked, stop, budget=5,
                                  on_done=lambda section, count: called_back.append(section.n))
            self.assertLess(time.monotonic() - began, 0.5)
            self.assertTrue(stop.is_set())
            self.assertEqual(skimmed, len(sections))
            frozen = [(s.gist, list(s.facts)) for s in sections]
        finally:
            release.set()
            canceller.join(timeout=1)
        time.sleep(0.05)
        self.assertEqual([(s.gist, s.facts) for s in sections], frozen)
        self.assertEqual(called_back, [])

    def test_failed_model_reads_are_counted_as_skimmed(self):
        sections = self.sections(4)
        def unavailable(*args, **kwargs):
            raise TimeoutError("synthetic model unavailable")
        self.assertEqual(fn.read_all(sections, unavailable, threading.Event(), budget=1), len(sections))
        self.assertTrue(all(section.gist and not section.facts for section in sections))

    def test_questions_find_parts_by_their_words_even_when_seek_misses(self):
        sections = self.sections(12)
        picked = fn.find_sections("what does topic9 say?", sections, lambda *a, **k: json.dumps({"parts": []}))
        self.assertIn(9, [s.n for s in picked])
        self.assertLessEqual(len(picked), 4)


if __name__ == "__main__":
    unittest.main()
