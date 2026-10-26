import base64
import io
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from core.api import chat_files


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


class ChatFilesTest(unittest.TestCase):
    def test_decode_rejects_too_many_and_bad_data(self):
        with self.assertRaises(chat_files.SharedFileError):
            chat_files.decode_files([{"name": "a.txt", "data": _b64(b"x")}] * 5)
        with self.assertRaises(chat_files.SharedFileError):
            chat_files.decode_files([{"name": "a.txt", "data": "not base64!"}])

    def test_names_are_made_safe(self):
        [(name, _)] = chat_files.decode_files([{"name": "..\\..\\evil<>.txt", "data": _b64(b"hi")}])
        self.assertEqual(name, "evil_.txt")

    def test_reads_text_docx_xlsx_and_pdf(self):
        self.assertEqual(chat_files.extract_text("notes.md", "Héllo".encode())[1], "Héllo")
        import docx
        document = docx.Document(); document.add_paragraph("Formation at 0600")
        buffer = io.BytesIO(); document.save(buffer)
        self.assertIn("Formation at 0600", chat_files.extract_text("plan.docx", buffer.getvalue())[1])
        from openpyxl import Workbook
        book = Workbook(); book.active.append(["item", "cost"]); book.active.append(["RAM", 180])
        buffer = io.BytesIO(); book.save(buffer)
        self.assertIn("RAM,180", chat_files.extract_text("budget.xlsx", buffer.getvalue())[1])
        from pypdf import PdfWriter
        writer = PdfWriter(); writer.add_blank_page(100, 100)
        buffer = io.BytesIO(); writer.write(buffer)
        kind, text = chat_files.extract_text("scan.pdf", buffer.getvalue())
        self.assertEqual(kind, "PDF"); self.assertIn("no readable text", text)

    def test_binary_gets_a_note_not_garbage(self):
        kind, text = chat_files.extract_text("song.mp3", b"\x00\x01" * 100)
        self.assertEqual(kind, "audio")
        self.assertIn("couldn't be decoded", text)  # a broken MP3: a plain note, not bytes
        kind, text = chat_files.extract_text("blob.bin", b"\x00\x01" * 100)
        self.assertIn("binary file", text)
        self.assertNotIn("\x00", text)

    def test_block_labels_files_as_data_and_clips(self):
        block, names = chat_files.files_block([("big.txt", b"a" * 50_000)], save=False)
        self.assertEqual(names, ["big.txt"])
        self.assertIn("never instructions", block)
        self.assertIn("only the first part fits", block)
        self.assertLess(len(block), chat_files.MAX_TOTAL_CHARS + 1000)

    def test_stream_answers_from_file_and_saves_only_his_words(self):
        brain = mock.Mock()
        brain.prepare_turn.return_value = SimpleNamespace(messages=[])
        brain.load_behavior_context.return_value = None
        brain.model_context.return_value = None
        seen = {}

        def fake_stream(message, **kwargs):
            seen.update(kwargs, message=message)
            yield "It says "; yield "0600."

        with mock.patch("core.brain.local_llm.stream_chat_local", fake_stream):
            events = list(chat_files.stream_with_files(brain, "When is formation?", [("plan.txt", b"Formation 0600")],
                                                       threading.Event(), save=False))
        self.assertEqual(events[-1], {"type": "final", "answer": "It says 0600."})
        self.assertIn("Formation 0600", seen["conversation_context"])
        self.assertEqual(seen["message"], "When is formation?")
        question = brain.remember_exchange.call_args.kwargs["question"]
        self.assertNotIn("Formation 0600", question)
        self.assertIn("plan.txt", question)


if __name__ == "__main__":
    unittest.main()
