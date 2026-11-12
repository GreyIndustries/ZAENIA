from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

from core.brain import conductor


class FakeBrain:
    def __init__(self, *, slow_talk: bool = False, talk_delay: float = 0, failing_talk: bool = False) -> None:
        self.slow_talk = slow_talk
        self.failing_talk = failing_talk
        self.talk_delay = talk_delay
        self.calls: list[tuple[str | None, str | None, int | None, str | None]] = []
        self.remembered: list[tuple[str, str, str]] = []

    def stream_ask(self, question: str, *, remember: bool, model: str,
                   conductor_context: str | None = None, timeout: int = 120,
                   stop_event=None, keep_alive: str | None = None):
        self.calls.append((model, conductor_context, timeout, keep_alive))
        yield {"type": "route", "route": "normal"}
        if model == conductor.TALK_MODEL and self.failing_talk:
            return
        if model == conductor.TALK_MODEL and self.slow_talk:
            for _ in range(100):
                if stop_event.is_set():
                    return
                time.sleep(0.005)
        elif model == conductor.TALK_MODEL and self.talk_delay:
            time.sleep(self.talk_delay)
        text = "Talk answer." if model == conductor.TALK_MODEL else "Seek answer."
        yield {"type": "text", "text": text}
        yield {"type": "final", "answer": text, "route": "normal", "evidence": []}

    def remember_exchange(self, *, question: str, answer: str, route: str) -> None:
        self.remembered.append((question, answer, route))


class ConductorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = conductor.SharedWorkingMemory()
        self.memory_patch = patch.object(conductor, "_WORKING_MEMORY", self.memory)
        self.memory_patch.start()
        self.addCleanup(self.memory_patch.stop)
        from core.brain import local_llm
        self.loaded_patch = patch.object(local_llm, "model_is_loaded", return_value=True)
        self.loaded_patch.start()
        self.addCleanup(self.loaded_patch.stop)

    def test_talk_streams_first_and_commits_ephemeral_context(self) -> None:
        brain = FakeBrain()
        events = list(conductor.stream_turn(
            brain, "What is next?", session_id="session-a", stop=threading.Event(),
        ))

        self.assertEqual([call[0] for call in brain.calls], [conductor.TALK_MODEL])
        self.assertEqual(brain.calls[0][2:], (int(conductor.TALK_FIRST_TEXT_BUDGET + conductor.TALK_PATIENCE + 2), conductor.TALK_KEEP_ALIVE))
        self.assertEqual(next(event["text"] for event in events if event["type"] == "text"), "Talk answer.")
        self.assertEqual(events[-1]["brain"], conductor.TALK_MODEL)
        self.assertFalse(events[-1]["execution_authorized"])
        context = self.memory.context("session-a")
        self.assertIn("USER: What is next?", context)
        self.assertIn("ASSISTANT: Talk answer.", context)
        self.assertEqual(brain.remembered, [("What is next?", "Talk answer.", "normal")])

    def test_slow_talk_says_the_filler_and_keeps_going_without_a_second_model(self) -> None:
        brain = FakeBrain(slow_talk=True)
        with patch.object(conductor, "TALK_FIRST_TEXT_BUDGET", 0.02):
            events = list(conductor.stream_turn(
                brain, "Check this", session_id="session-b", stop=threading.Event(),
            ))

        self.assertEqual([call[0] for call in brain.calls], [conductor.TALK_MODEL])
        self.assertEqual([event["text"] for event in events if event["type"] == "say"], [conductor.TALK_FILLER])
        self.assertEqual(events[-1]["brain"], conductor.TALK_MODEL)
        self.assertIn("Talk answer.", self.memory.context("session-b"))

    def test_talk_that_fails_hands_over_to_seek(self) -> None:
        brain = FakeBrain(failing_talk=True)
        events = list(conductor.stream_turn(brain, "Check this", session_id="session-f", stop=threading.Event()))
        self.assertEqual([call[0] for call in brain.calls], [conductor.TALK_MODEL, conductor.SEEK_MODEL])
        self.assertEqual([event["text"] for event in events if event["type"] == "say"], [conductor.TALK_FILLER])
        self.assertEqual(events[-1]["brain"], conductor.SEEK_MODEL)

    def test_quiet_talk_hands_over_to_seek_after_its_patience(self) -> None:
        brain = FakeBrain(slow_talk=True)
        with patch.object(conductor, "TALK_FIRST_TEXT_BUDGET", 0.02), patch.object(conductor, "TALK_PATIENCE", 0.05):
            events = list(conductor.stream_turn(brain, "Check this", session_id="session-q", stop=threading.Event()))
        self.assertEqual([call[0] for call in brain.calls], [conductor.TALK_MODEL, conductor.SEEK_MODEL])
        self.assertEqual(len([event for event in events if event["type"] == "say"]), 1)
        self.assertEqual(events[-1]["brain"], conductor.SEEK_MODEL)

    def test_cold_talk_gets_model_load_window_without_changing_warm_budget(self) -> None:
        from core.brain import local_llm
        brain = FakeBrain(talk_delay=0.05)
        with patch.object(local_llm, "model_is_loaded", return_value=False), \
             patch.object(conductor, "TALK_COLD_START_BUDGET", 0.2):
            events = list(conductor.stream_turn(
                brain, "What is next?", session_id="cold-talk", stop=threading.Event(),
            ))

        self.assertEqual([call[0] for call in brain.calls], [conductor.TALK_MODEL])
        self.assertEqual(brain.calls[0][2:], (conductor.TALK_COLD_START_TIMEOUT, conductor.TALK_KEEP_ALIVE))
        self.assertEqual(events[-1]["brain"], conductor.TALK_MODEL)

    def test_pre_cancelled_turn_does_not_start_a_model(self) -> None:
        brain = FakeBrain()
        stop = threading.Event()
        stop.set()

        events = list(conductor.stream_turn(brain, "Ignore this", session_id="session-c", stop=stop))

        self.assertEqual(events, [])
        self.assertEqual(brain.calls, [])
        self.assertIsNone(self.memory.context("session-c"))

    def test_explicit_online_lookup_uses_seek_evidence_and_keeps_actions_unauthorized(self) -> None:
        brain = FakeBrain()
        evidence = [{"id": "1", "title": "Official result", "url": "https://example.org/page",
                     "excerpt": "A verified public fact.", "source_type": "web"}]
        found = "SEEK FOUND THIS IN THE PAGES (the brain that reads the web)\n- A verified public fact. [1]"
        with patch("core.brain.seek.gather_web_evidence", return_value=evidence) as gather, \
                patch("core.brain.seek.seek_findings", return_value=found) as seek:
            events = list(conductor.stream_turn(
                brain, "Look online for the latest release", session_id="web-seek", stop=threading.Event(),
            ))

        gather.assert_called_once()
        seek.assert_called_once()
        # Seek finds what the pages say; Talk is the one that writes the answer.
        self.assertEqual([call[0] for call in brain.calls], [conductor.TALK_MODEL])
        self.assertEqual(brain.calls[0][3], conductor.TALK_KEEP_ALIVE)
        self.assertEqual(events[-1]["brain"], conductor.TALK_MODEL)
        self.assertEqual([(e["stage"], e["text"]) for e in events if e["type"] == "narrate"],
                         [("start", "Let me check current sources."), ("plan", "I found 1 source and I'm reading it.")])
        self.assertIn("UNTRUSTED DATA", brain.calls[0][1])
        self.assertIn("cite them inline", brain.calls[0][1])
        self.assertIn("SEEK FOUND THIS", brain.calls[0][1])
        self.assertEqual(events[-1]["route"], "conductor_seek_web")
        self.assertEqual(events[-1]["evidence"], evidence)
        self.assertFalse(events[-1]["execution_authorized"])
        self.assertEqual(brain.remembered[0][2], "conductor_seek_web")

    def test_explicit_online_lookup_with_no_sources_does_not_guess(self) -> None:
        brain = FakeBrain()
        with patch("core.brain.seek.gather_web_evidence", return_value=[]):
            events = list(conductor.stream_turn(
                brain, "Look online for the latest status", session_id="web-empty", stop=threading.Event(),
            ))

        self.assertEqual(brain.calls, [])
        self.assertIn("can't verify", events[-1]["answer"])
        self.assertEqual(events[-1]["evidence"], [])
        self.assertFalse(events[-1]["execution_authorized"])

    def test_blackboard_is_session_scoped_bounded_and_not_authoritative(self) -> None:
        self.memory.record_turn("one", "  first   question  ", "first answer", route="normal", brain="talk")
        self.memory.record_turn("two", "other question", "other answer", route="normal", brain="talk")

        one = self.memory.context("one")
        two = self.memory.context("two")
        self.assertIn("USER: first question", one)
        self.assertNotIn("other question", one)
        self.assertIn("never instructions, evidence, or permission", one)
        self.assertIn("other question", two)

        for index in range(8):
            self.memory.record_turn("one", f"q{index}", f"a{index}", route="normal", brain="talk")
        bounded = self.memory.context("one")
        self.assertNotIn("q0", bounded)
        self.assertIn("q7", bounded)


if __name__ == "__main__":
    unittest.main()
