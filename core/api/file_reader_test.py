import gzip
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from core.api import file_reader
from core.api.chat_files import extract_text


def zipped(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


class FileReaderTest(unittest.TestCase):
    def test_office_and_document_formats(self):
        pptx = zipped({"ppt/slides/slide2.xml": "<p:sld><a:t>Second</a:t></p:sld>", "ppt/slides/slide1.xml": "<a:t>Leg day</a:t><a:t>&amp; core</a:t>"})
        self.assertEqual(extract_text("deck.pptx", pptx), ("PowerPoint", "[slide 1]\nLeg day\n& core\n\n[slide 2]\nSecond"))
        odt = zipped({"content.xml": "<office:text><text:h>Title</text:h><text:p>Body <text:span>text</text:span></text:p></office:text>"})
        self.assertEqual(extract_text("a.odt", odt), ("OpenDocument text", "Title\nBody text"))
        epub = zipped({"OEBPS/ch1.xhtml": "<html><head><title>Ch 1</title></head><body><p>It was a dark night.</p></body></html>"})
        self.assertIn("It was a dark night.", extract_text("book.epub", epub)[1])
        self.assertIn("Hello there", extract_text("p.html", b"<html><body><script>x()</script><p>Hello there</p></body></html>")[1])
        self.assertEqual(extract_text("a.rtf", rb"{\rtf1\ansi{\fonttbl{\f0 Arial;}}\f0 Hello\par World caf\'e9}")[1], "Hello\nWorld café")
        notebook = json.dumps({"cells": [{"cell_type": "code", "source": ["print(1)"]}]}).encode()
        self.assertEqual(extract_text("n.ipynb", notebook), ("Jupyter notebook", "[code cell]\nprint(1)"))

    def test_email(self):
        raw = b"From: sgt@army.mil\r\nTo: grey@x.com\r\nSubject: Formation\r\nContent-Type: text/plain\r\n\r\nFormation moved to 0600."
        kind, text = extract_text("m.eml", raw)
        self.assertEqual(kind, "email")
        self.assertIn("Subject: Formation", text)
        self.assertIn("Formation moved to 0600.", text)

    def test_archives_and_database(self):
        archive = zipped({"notes/readme.md": "# Plan\nSquat day", "pic.bin": "\x00\x01"})
        kind, text = extract_text("bundle.zip", archive)
        self.assertIn("pic.bin", text)
        self.assertIn("Squat day", text)
        self.assertEqual(extract_text("log.txt.gz", gzip.compress(b"hello log")), ("gzip of text", "hello log"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "t.db"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE lifts (name TEXT, kg INT)")
            db.execute("INSERT INTO lifts VALUES ('squat', 140)")
            db.commit()
            db.close()
            kind, text = extract_text("t.db", path.read_bytes())
        self.assertEqual(kind, "SQLite database")
        self.assertIn("[table lifts: 1 rows; columns name, kg]", text)
        self.assertIn("('squat', 140)", text)

    def test_image_uses_the_vision_model(self):
        from PIL import Image
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20), "red").save(buffer, "GIF")
        seen = []
        kind, text = file_reader.extract("x.gif", buffer.getvalue(), ask_vision=lambda prompt, image: seen.append(image) or "A red square.")
        self.assertEqual((kind, text), ("image", "A red square."))
        self.assertTrue(seen[0])

    def test_audio_without_speech_and_video(self):
        import numpy as np
        import soundfile
        buffer = io.BytesIO()
        soundfile.write(buffer, np.zeros(16000, dtype="float32"), 16000, format="WAV")
        kind, text = file_reader.extract("quiet.wav", buffer.getvalue())
        self.assertEqual(kind, "audio")
        if "couldn't be transcribed" in text:  # no Vosk model in a clean checkout
            self.skipTest(text)
        self.assertIn("0 min 1 s", text)
        if not file_reader.find_ffmpeg():
            self.assertIn("needs FFmpeg", file_reader.extract("clip.mp4", b"\x00" * 10)[1])

    def test_unknown_binary_gets_type_and_strings(self):
        kind, text = extract_text("tool.exe", b"MZ\x90\x00" + b"\x00" * 20 + b"Hello from the program" + b"\x00" * 10)
        self.assertEqual(kind, "file")
        self.assertIn("Windows program", text)
        self.assertIn("Hello from the program", text)


if __name__ == "__main__":
    unittest.main()
