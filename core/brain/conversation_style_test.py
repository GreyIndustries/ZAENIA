"""User-led dialogue and bounded memory regression checks; no model or owner data."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.brain.conversation_style import user_led_answer, user_led_stream
from core.brain.recent_memory import recent_lines
from core.brain import brain_service


class ConversationStyleTests(unittest.TestCase):
    def test_terminal_invitations_are_removed_across_token_boundaries(self):
        endings = (
            "Do you want to know more?", "Would you like me to continue?",
            "Let me know if you need anything else.", "Anything else?",
            "Is there anything else I can help you with?",
            "Would you like to go into more detail?",
        )
        for ending in endings:
            text = "The answer is four. " + ending
            for size in (1, 2, 7, 500):
                with self.subTest(ending=ending, size=size):
                    chunks = (text[i:i + size] for i in range(0, len(text), size))
                    self.assertEqual("".join(user_led_stream(chunks)).strip(), "The answer is four.")

    def test_required_questions_examples_and_requested_dialogue_survive(self):
        examples = (
            ("What time should I put on the event?", "Add an event tomorrow"),
            ("I have the title. Do you want tea or coffee?", "Help select a drink"),
            ('She asked, "Do you want to know more?"', "Describe the scene"),
            ("The sentence is: Do you want to know more?", "Translate this exactly"),
            ("Do you want to know more?", "Write a follow-up question"),
            ("Result: 3.14.\n```\nDo you want to know more?\n```", "Write code"),
            ("You can let me know if you need anything else.", "Explain the phrase"),
            ("Done. Would you like to continue? Use the next page.", "Explain navigation"),
        )
        for text, question in examples:
            with self.subTest(text=text):
                self.assertEqual(user_led_answer(text, question=question), text)

    def test_ordinary_answer_starts_streaming_before_generator_finishes(self):
        pulled = []
        def source():
            pulled.append(1)
            yield "The answer is four."
            pulled.append(2)
            yield " Do you want to know more?"
        stream = user_led_stream(source())
        self.assertEqual(next(stream), "The answer is four.")
        self.assertEqual(pulled, [1])
        self.assertEqual("".join(stream), "")

    def test_false_candidate_has_bounded_buffer_and_is_preserved(self):
        text = "Done. Would you like " + "a" * 2500
        self.assertEqual(user_led_answer(text), text)

    def test_required_question_releases_when_its_sentence_is_complete(self):
        pulled = []
        def source():
            yield "I have the title."
            pulled.append('question')
            yield " Do you want tea or coffee?"
            pulled.append('rest')
            yield " Both are available."
        stream = user_led_stream(source())
        self.assertEqual(next(stream), "I have the title.")
        self.assertEqual(next(stream), " Do you want tea or coffee?")
        self.assertEqual(pulled, ['question'])
        self.assertEqual(''.join(stream), " Both are available.")

    def test_approval_consent_and_consequences_keep_their_required_question(self):
        examples = (
            ("The operation requires your approval. Would you like me to continue?", "Review the plan"),
            ("This change is permanent. Do you want me to continue?", "Review the change"),
            ("The transfer will cost money. Would you like me to continue?", "Review the transfer"),
            ("I can continue. Would you like me to continue?", "Ask for my permission first"),
        )
        for text, question in examples:
            with self.subTest(text=text):
                self.assertEqual(user_led_answer(text, question=question), text)

    def test_brain_ask_returns_and_remembers_the_same_clean_answer(self):
        service = brain_service.BrainService()
        result = {"answer": "Four. Anything else?", "route": "normal"}
        with patch.object(brain_service, "answer_question", return_value=result), \
                patch.object(service, "load_recent_messages", return_value=[]), \
                patch.object(service, "load_behavior_context", return_value=None), \
                patch.object(service, "load_conversation_context", return_value=None), \
                patch.object(service, "remember_exchange") as remember:
            reply = service.ask("Calculate two plus two")
        self.assertEqual(reply["answer"], "Four.")
        self.assertEqual(remember.call_args.kwargs["answer"], "Four.")
        self.assertFalse(reply["execution_authorized"])

    def test_brain_stream_text_final_and_memory_agree(self):
        service = brain_service.BrainService()
        with patch.object(brain_service, "classify_question", return_value=SimpleNamespace(route="normal", reason="fixture", confidence=1)), \
                patch.object(brain_service, "stream_chat_local", return_value=iter(["Four.", " Do you", " want to know more?"])), \
                patch.object(service, "load_recent_messages", return_value=[]), \
                patch.object(service, "load_behavior_context", return_value=None), \
                patch.object(service, "load_conversation_context", return_value=None), \
                patch.object(service, "remember_exchange") as remember:
            events = list(service.stream_ask("Calculate two plus two"))
        streamed = "".join(item["text"] for item in events if item["type"] == "text")
        self.assertEqual(streamed, "Four.")
        self.assertEqual(events[-1]["answer"], streamed)
        self.assertEqual(remember.call_args.kwargs["answer"], streamed)


class RecentMemoryTests(unittest.TestCase):
    def test_byte_window_at_record_boundary_retains_the_complete_record(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "journal.jsonl"
            last = b'{"role":"user","content":"latest"}\n'
            path.write_bytes(b'old record\n' + last)
            self.assertEqual(recent_lines(path, max_bytes=len(last)), [last.decode().strip()])

    def test_invalid_bounds_never_enable_an_unbounded_read(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                recent_lines(Path('unused'), max_bytes=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                recent_lines(Path('unused'), limit=value)

    def test_tail_read_is_bounded_and_discards_partial_record(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "journal.jsonl"
            path.write_bytes(b"x" * 1000000 + b'\n{"role":"user","content":"latest"}\n')
            self.assertEqual(recent_lines(path, max_bytes=100), ['{"role":"user","content":"latest"}'])
            with patch.object(brain_service, "MEMORY_PATH", path):
                self.assertEqual(brain_service.BrainService().load_recent_messages(), [{"role": "user", "content": "latest"}])

    def test_limits_and_legacy_records_survive_malformed_rows(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "journal.jsonl"
            rows = [{"role": "user", "content": "older"}, {"speaker": "Zack", "text": "latest"}, {"user": "next", "assistant": "reply"}]
            path.write_text("\ufeff" + "\n".join(json.dumps(row) for row in rows) + "\ninvalid\n", encoding="utf-8")
            self.assertEqual(len(recent_lines(path, limit=2)), 2)
            with patch.object(brain_service, "MEMORY_PATH", path):
                self.assertEqual(brain_service.BrainService(memory_limit=2).load_recent_messages(), [{"role": "user", "content": "next"}, {"role": "assistant", "content": "reply"}])

    def test_missing_and_invalid_utf8_do_not_crash_optional_memory(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "missing"
            self.assertEqual(recent_lines(path), [])
            path.write_bytes(b"\xffbad\n")
            with patch.object(brain_service, "MEMORY_PATH", path):
                self.assertEqual(brain_service.BrainService().load_recent_messages(), [])


if __name__ == "__main__":
    unittest.main()
