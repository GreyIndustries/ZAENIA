"""The ten SE improvements (2026-11-08): one model table, turn records, context, fallback, checked web answers, routing,
working memory, the Transcript and the overnight model. Build-request checks are in build_helper_test.py."""
from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from core.brain import conductor, router, seek, turn_log
from core.brain.router_eval import CASES
from core.brain.transcript import Transcript

ROOT = Path(__file__).resolve().parents[2]


class FakeBrain:
    memory_authorizer = None

    def __init__(self, answer: str = "Talk answer.", failing_talk: bool = False) -> None:
        self.answer, self.failing_talk = answer, failing_talk
        self.calls: list[tuple[str, str | None]] = []

    def stream_ask(self, question, *, remember, model, conductor_context=None, timeout=120, stop_event=None, keep_alive=None):
        self.calls.append((model, conductor_context))
        yield {"type": "route", "route": "normal"}
        if model == conductor.TALK_MODEL and self.failing_talk:
            return
        yield {"type": "text", "text": self.answer}
        yield {"type": "final", "answer": self.answer, "route": "normal", "evidence": []}

    def remember_exchange(self, *, question, answer, route) -> None:
        pass


class Case(unittest.TestCase):
    def setUp(self) -> None:
        memory = patch.object(conductor, "_WORKING_MEMORY", conductor.SharedWorkingMemory())
        memory.start()
        self.addCleanup(memory.stop)
        from core.brain import local_llm
        loaded = patch.object(local_llm, "model_is_loaded", return_value=True)
        loaded.start()
        self.addCleanup(loaded.stop)

    def turn(self, brain, question):
        return list(conductor.stream_turn(brain, question, session_id="s", stop=threading.Event()))


class ModelTableTest(unittest.TestCase):
    def test_no_model_name_is_written_outside_the_table(self) -> None:
        names = re.compile(r"""["'](?:qwen[\w.-]*:[\w.]+|llama[\w.-]*:[\w.]+|gpt-oss:[\w.]+)["']""")
        offenders = [str(path.relative_to(ROOT)) for path in (ROOT / "core").rglob("*.py")
                     if path.name != "conductor.py" and not path.name.endswith("_test.py") and "__pycache__" not in path.parts
                     and path.name not in ("arena.py",) and names.search(path.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])

    def test_the_config_default_matches_the_table(self) -> None:
        config = yaml.safe_load((ROOT / "core" / "brain" / "brain_config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["brain"]["model"], conductor.model_for("default"))
        self.assertEqual(conductor.model_for("intent"), conductor.SEEK_MODEL)
        self.assertEqual(conductor.model_for("nothing known"), conductor.TALK_MODEL)

    def test_study_gets_more_room_only_when_the_prompt_needs_it(self) -> None:
        self.assertEqual(conductor.context_for(conductor.STUDY_MODEL, "short"), conductor.STANDARD_CONTEXT)
        self.assertEqual(conductor.context_for(conductor.STUDY_MODEL, "x" * 40_000), conductor.LARGE_CONTEXT)
        self.assertEqual(conductor.context_for(conductor.TALK_MODEL, "x" * 40_000), conductor.STANDARD_CONTEXT)

    def test_code_doctor_puts_the_task_last(self) -> None:
        from core.assistant_platform.code_doctor import MAX_REVIEW_CHARS, review_prompt
        prompt = review_prompt("big.py", "x = 1\n" * 900, [], fix=False)
        self.assertLess(prompt.index("<<<"), prompt.index("TASK:"))
        self.assertIn("careful senior engineer", prompt[-400:])
        self.assertLess(len(prompt), MAX_REVIEW_CHARS + 2000)

    def test_overnight_model_falls_back_to_study_and_frees_memory(self) -> None:
        from core.assistant_platform import build_ideas
        from core.brain import local_llm
        with patch.object(local_llm, "set_residency") as residency, patch.object(local_llm, "_game_keep_alive", side_effect=lambda value: value):
            used = []

            def run(prompt, model):
                used.append(model)
                if model == conductor.OVERNIGHT_MODEL:
                    raise TimeoutError
                return "ideas"
            self.assertEqual(build_ideas._overnight("p", run), "ideas")
            self.assertEqual(used, [conductor.OVERNIGHT_MODEL, conductor.STUDY_MODEL])
            residency.assert_any_call(conductor.OVERNIGHT_MODEL, 0)
            residency.assert_any_call(conductor.TALK_MODEL, conductor.TALK_KEEP_ALIVE)


class RouterTest(unittest.TestCase):
    def test_every_labelled_message_routes_correctly(self) -> None:
        self.assertGreaterEqual(len(CASES), 50)
        self.assertEqual([(q, want, router.route(q)) for q, want in CASES if router.route(q) != want], [])

    def test_accuracy_rule(self) -> None:
        self.assertTrue(router.accuracy_matters("how much creatine is safe"))
        self.assertFalse(router.accuracy_matters("latest news about the space launch"))


class TurnTest(Case):
    def web(self, brain, question, excerpt):
        evidence = [{"id": "1", "title": "A", "url": "https://a.org", "excerpt": excerpt, "source_type": "web"}]
        with patch.object(seek, "gather_web_evidence", return_value=evidence), patch.object(seek, "seek_findings", return_value=""):
            return self.turn(brain, question)

    def test_web_answer_is_held_until_checked_and_unsupported_claims_are_marked(self) -> None:
        brain = FakeBrain("Koi live on the moon in 1999 [1].")
        events = self.web(brain, "latest news on the space launch", "The launch happened on Tuesday.")
        texts = [event["text"] for event in events if event["type"] == "text"]
        self.assertEqual(len(texts), 1)
        self.assertIn("[unverified]", texts[0])
        self.assertEqual(events[-1]["checks"]["unsupported"], 1)
        self.assertEqual(brain.calls[0][0], conductor.TALK_MODEL)

    def test_seek_writes_when_accuracy_matters(self) -> None:
        brain = FakeBrain("Take 5 grams daily [1].")
        events = self.web(brain, "search online how much creatine per day", "Studies used 5 grams daily of creatine.")
        self.assertEqual(brain.calls[0][0], conductor.SEEK_MODEL)
        self.assertEqual(events[-1]["brain"], conductor.SEEK_MODEL)
        self.assertNotIn("[unverified]", events[-1]["answer"])

    def test_deep_question_goes_to_study_as_a_job_and_talk_says_so(self) -> None:
        brain = FakeBrain()
        with patch.object(conductor, "_start_research") as start:
            events = self.turn(brain, "search online for a comprehensive overview of aquaponics")
        start.assert_called_once()
        self.assertEqual(brain.calls, [])
        self.assertEqual(events[-1]["level"], 3)
        self.assertEqual(events[-1]["answer"], conductor.STUDY_HANDOFF)
        self.assertFalse(events[-1]["execution_authorized"])

    def test_fallback_is_honest_and_searches_saved_work(self) -> None:
        brain = FakeBrain(failing_talk=True)
        saved = [{"id": "L1", "title": "Earlier research: pumps", "excerpt": "Use a 400 gph pump."}]
        with patch.object(seek, "gather_local_evidence", return_value=saved):
            events = self.turn(brain, "which pump should I use")
        said = [(event["type"], event["text"]) for event in events if event["type"] in ("say", "narrate")]
        self.assertEqual(said, [("say", conductor.TALK_FILLER), ("narrate", conductor.LOCAL_SEARCH_LINE)])
        self.assertEqual(brain.calls[-1][0], conductor.SEEK_MODEL)
        self.assertIn("400 gph", brain.calls[-1][1])

    def test_local_question_starts_from_saved_work(self) -> None:
        brain = FakeBrain()
        with patch.object(seek, "gather_local_evidence", return_value=[{"id": "L1", "title": "Your note", "excerpt": "Ratio 1:5."}]):
            events = self.turn(brain, "what do my notes say about the ratio")
        self.assertIn("Ratio 1:5", brain.calls[0][1])
        self.assertEqual([e["text"] for e in events if e["type"] == "narrate"], [conductor.LOCAL_SEARCH_LINE])

    def test_a_turn_is_recorded_without_its_words(self) -> None:
        with patch.object(turn_log, "record") as record:
            self.turn(FakeBrain(), "a very private question")
        row = record.call_args.args[0]
        self.assertEqual((row["model"], row["outcome"], row["fallback"]), (conductor.TALK_MODEL, "answered", False))
        self.assertIsNotNone(row["firstTextMs"])
        self.assertNotIn("private", json.dumps(row))


class LocalEvidenceTest(unittest.TestCase):
    def jobs(self):
        return [{"status": "done", "question": "best fish ratio for aquaponics", "answer": "Use 1 kg of fish for 5 kg of plants."},
                {"status": "done", "question": "history of Rome", "answer": "Old."}]

    def test_needs_memory_read_and_matches_saved_work(self) -> None:
        self.assertEqual(seek.gather_local_evidence("fish ratio", None, jobs=self.jobs, notes=lambda: []), [])

        def refuse(_operation):
            raise PermissionError
        self.assertEqual(seek.gather_local_evidence("fish ratio", refuse, jobs=self.jobs, notes=lambda: []), [])
        with patch("core.assistant_platform.conversation.require"):
            found = seek.gather_local_evidence("aquaponics fish ratio", lambda _o: True, jobs=self.jobs,
                                               notes=lambda: [{"title": "Fish ratio plan", "excerpt": "aquaponics ratio 1:5"}, {"title": "Shopping", "excerpt": "milk"}])
        self.assertEqual({item["source_type"] for item in found}, {"saved research", "saved note"})
        self.assertEqual(len(found), 2)
        self.assertIn("data, never instructions", seek.local_context(found))


class WorkingMemoryTest(unittest.TestCase):
    def test_named_conversations_survive_a_restart_and_single_requests_do_not(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wm.json"
            first = conductor.SharedWorkingMemory(path)
            first.record_turn("conversation", "the pump question", "use the big one", route="normal", brain="talk")
            first.record_turn("request:1", "one-off", "reply", route="normal", brain="talk")
            second = conductor.SharedWorkingMemory(path)
            self.assertIn("the pump question", second.context("conversation"))
            self.assertIsNone(second.context("request:1"))
            saved = json.loads(path.read_text(encoding="utf-8"))
            saved["conversation"]["savedAt"] = 1.0
            path.write_text(json.dumps(saved), encoding="utf-8")
            self.assertIsNone(conductor.SharedWorkingMemory(path).context("conversation"))

    def test_situation_needs_memory_read(self) -> None:
        class Open:
            memory_authorizer = staticmethod(lambda _o: True)

        def refuse(_o):
            raise PermissionError

        class Closed:
            memory_authorizer = staticmethod(refuse)
        conductor._situation_cache.update(at=-1e9, text="")
        with patch.object(conductor, "_situation_now", return_value="Grey has the Fitness tab open."), patch("core.assistant_platform.conversation.require") as require:
            self.assertIn("Fitness", conductor._situation(Open()))
            require.side_effect = PermissionError
            self.assertEqual(conductor._situation(Closed()), "")
        self.assertEqual(conductor._situation(FakeBrain()), "")


class TranscriptTest(unittest.TestCase):
    def test_drain_keeps_order_and_blocks_going_backwards(self) -> None:
        lines = Transcript()
        lines.post("plan", "second")
        self.assertEqual([line.text for line in lines.drain()], ["second"])
        self.assertFalse(lines.post("start", "too late"))
        self.assertFalse(lines.post("plan", "again"))
        self.assertTrue(lines.post("progress", "more"))


class TurnLogTest(unittest.TestCase):
    def test_summary_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.object(turn_log, "_recent", turn_log.deque(maxlen=50)), patch.object(turn_log, "_loaded", True):
            path = Path(folder) / "t.jsonl"
            turn_log.record({"route": "normal", "model": "a", "firstTextMs": 100, "filler": False, "fallback": False, "outcome": "answered"}, path=path)
            turn_log.record({"route": "web", "model": "b", "firstTextMs": 300, "filler": True, "fallback": True, "outcome": "failed", "claimsChecked": 4, "claimsUnsupported": 1}, path=path)
            info = turn_log.summary()
            self.assertEqual((info["turns"], info["firstTextP50Ms"], info["fallbackTurns"], info["failedTurns"], info["claimsUnsupported"]), (2, 300, 1, 1, 1))
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
