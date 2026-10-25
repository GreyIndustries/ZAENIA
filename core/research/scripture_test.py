import tempfile
import unittest
from pathlib import Path

from core.research import scripture


def fake_offline(book, chapter, verse):
    if verse > 3:
        return None
    return {"book_name": "John", "translations": {"WEB-Classic": f"web {verse}", "ASV1901": f"asv {verse}"},
            "words": [{"dataset": "TAGNT", "original": "λόγος", "transliteration": "logos", "gloss": "word",
                       "lexical_and_morphology": "G3056=N-NSM"}]}


def fake_get(url, params=None, timeout=15):
    return {"verses": [{"verse": 1, "text": "kjv one\n"}, {"verse": 2, "text": "kjv two"}]}


class ScriptureTest(unittest.TestCase):
    def test_references(self):
        self.assertEqual(scripture.parse_reference("John 3:16"), ("John", 3, 16, 16))
        self.assertEqual(scripture.parse_reference("1 John 1:1-3"), ("1 John", 1, 1, 3))
        self.assertEqual(scripture.parse_reference("Song of Solomon 2"), ("Song of Solomon", 2, 1, 30))
        for bad in ("hello", "John 3:20-1", "John 1:1-60"):
            with self.assertRaises(ValueError):
                scripture.parse_reference(bad)

    def test_whole_chapter_stops_at_its_end_and_merges_translations(self):
        found = scripture.passage("John 1", ["WEB", "KJV"], get=fake_get, offline=fake_offline)
        self.assertEqual((found["reference"], len(found["verses"]), found["originalLanguage"]), ("John 1:1-3", 3, "Greek"))
        self.assertEqual(found["verses"][0]["texts"], {"WEB": "web 1", "KJV": "kjv one"})
        self.assertEqual(found["verses"][2]["texts"]["KJV"], "")
        self.assertEqual(found["verses"][0]["words"][0]["strong"], "G3056")
        text = scripture.passage_text(found)
        self.assertIn("[KJV] kjv one", text)
        self.assertIn("λόγος (logos, G3056: word)", text)

    def test_unknown_passage(self):
        with self.assertRaises(ValueError):
            scripture.passage("John 9:9", ["WEB"], get=fake_get, offline=lambda *a: None)

    def test_marks(self):
        with tempfile.TemporaryDirectory() as folder:
            marks = scripture.Marks(Path(folder) / "m.json")
            mark = marks.add("Psalm 23:1", "The Lord is my shepherd")
            self.assertEqual([m["reference"] for m in marks.list()], ["Psalm 23:1"])
            marks.delete(mark["id"])
            self.assertEqual(marks.list(), [])
            with self.assertRaises(ValueError):
                marks.add("not a verse")


if __name__ == "__main__":
    unittest.main()
