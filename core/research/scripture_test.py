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

    def test_hebrew_verses_from_sefaria(self):
        def get(url, params=None, timeout=15):
            if "sefaria" in url:
                self.assertTrue(url.endswith("John.1.1-3"))
                return {"ref": "x", "versions": [{"language": "he", "text": ["<big>בְּ</big>רֵאשִׁ֖ית", "שׁנִי", "שׁלִישִׁי"]}]}
            return fake_get(url, params)
        found = scripture.passage("John 1", ["WEB", "HEB"], get=get, offline=fake_offline)
        self.assertEqual([v["texts"]["HEB"] for v in found["verses"]], ["בְּרֵאשִׁית", "שׁנִי", "שׁלִישִׁי"])

    def test_jewish_text(self):
        def get(url, params=None, timeout=15):
            self.assertEqual((url, params), (scripture.SEFARIA + "Pirkei_Avot_1:1-2", {"version": ["english", "hebrew"]}))
            return {"ref": "Pirkei Avot 1:1-2", "heRef": "אבות", "book": "Pirkei Avot", "sections": ["1", "1"], "sectionNames": ["Chapter", "Mishnah"],
                    "versions": [{"language": "en", "versionTitle": "Kulp", "license": "CC-BY",
                                  "text": ['Moses<sup class="footnote-marker">a</sup><i class="footnote">note</i> received <b>Torah</b>', "Shimon"]},
                                 {"language": "he", "versionTitle": "Torat Emet", "license": "Public Domain", "text": ["משה", "שמעון"]}]}
        found = scripture.jewish("Pirkei Avot 1:1-2", get=get)
        self.assertEqual(found["verses"][0], {"verse": 1, "texts": {"EN": "Moses received Torah", "HE": "משה"}, "words": []})
        self.assertIn("Kulp (CC-BY)", found["credit"])
        with self.assertRaises(ValueError):
            scripture.jewish("bad<script>", get=get)
        with self.assertRaises(ValueError):
            scripture.jewish("Nothing 1", get=lambda *a, **k: {"error": "Could not find title"})

    def test_quran(self):
        self.assertEqual(scripture.parse_quran("2:255"), (2, 255, 255))
        self.assertEqual(scripture.parse_quran("Surah 36:1-12"), (36, 1, 12))
        self.assertEqual(scripture.parse_quran("1"), (1, 1, None))
        for bad in ("115", "2:10-1", "hello"):
            with self.assertRaises(ValueError):
                scripture.parse_quran(bad)
        def get(url, params=None, timeout=15):
            self.assertIn("/surah/2/editions/quran-uthmani,en.pickthall", url)
            self.assertEqual(params, {"offset": 254, "limit": 2})
            ayahs = lambda t: [{"numberInSurah": 255, "text": t + "1"}, {"numberInSurah": 256, "text": t + "2"}]
            return {"data": [{"englishName": "Al-Baqara", "englishNameTranslation": "The Cow", "numberOfAyahs": 286, "ayahs": ayahs("ar")},
                             {"englishName": "Al-Baqara", "ayahs": ayahs("en")}]}
        found = scripture.quran("2:255-256", ["AR", "PICKTHALL"], get=get)
        self.assertEqual(found["reference"], "Surah 2 (Al-Baqara) 255-256")
        self.assertEqual(found["verses"][1]["texts"], {"AR": "ar2", "PICKTHALL": "en2"})

    def test_marks(self):
        with tempfile.TemporaryDirectory() as folder:
            marks = scripture.Marks(Path(folder) / "m.json")
            mark = marks.add("Psalm 23:1", "The Lord is my shepherd")
            self.assertEqual([m["reference"] for m in marks.list()], ["Psalm 23:1"])
            marks.delete(mark["id"])
            self.assertEqual(marks.list(), [])
            with self.assertRaises(ValueError):
                marks.add("not a verse")
            self.assertEqual(marks.add("Berakhot 2a", source="jewish")["source"], "jewish")
            with self.assertRaises(ValueError):
                marks.add("x", source="other")


if __name__ == "__main__":
    unittest.main()
