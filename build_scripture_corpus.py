"""Reproducible offline corpus builder. Inputs are licensed source files only."""
from __future__ import annotations
from contextlib import closing
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from zipfile import ZipFile

BOOK_ROWS = [
    ("Gen", "GEN", "Genesis"), ("Exo", "EXO", "Exodus"), ("Lev", "LEV", "Leviticus"),
    ("Num", "NUM", "Numbers"), ("Deu", "DEU", "Deuteronomy"), ("Jos", "JOS", "Joshua"),
    ("Jdg", "JDG", "Judges"), ("Rut", "RUT", "Ruth"), ("1Sa", "1SA", "1 Samuel"),
    ("2Sa", "2SA", "2 Samuel"), ("1Ki", "1KI", "1 Kings"), ("2Ki", "2KI", "2 Kings"),
    ("1Ch", "1CH", "1 Chronicles"), ("2Ch", "2CH", "2 Chronicles"), ("Ezr", "EZR", "Ezra"),
    ("Neh", "NEH", "Nehemiah"), ("Est", "EST", "Esther"), ("Job", "JOB", "Job"),
    ("Psa", "PSA", "Psalms"), ("Pro", "PRO", "Proverbs"), ("Ecc", "ECC", "Ecclesiastes"),
    ("Sng", "SOL", "Song of Songs"), ("Isa", "ISA", "Isaiah"), ("Jer", "JER", "Jeremiah"),
    ("Lam", "LAM", "Lamentations"), ("Ezk", "EZE", "Ezekiel"), ("Dan", "DAN", "Daniel"),
    ("Hos", "HOS", "Hosea"), ("Jol", "JOE", "Joel"), ("Amo", "AMO", "Amos"),
    ("Oba", "OBA", "Obadiah"), ("Jon", "JON", "Jonah"), ("Mic", "MIC", "Micah"),
    ("Nam", "NAH", "Nahum"), ("Hab", "HAB", "Habakkuk"), ("Zep", "ZEP", "Zephaniah"),
    ("Hag", "HAG", "Haggai"), ("Zec", "ZEC", "Zechariah"), ("Mal", "MAL", "Malachi"),
    ("Mat", "MAT", "Matthew"), ("Mrk", "MAR", "Mark"), ("Luk", "LUK", "Luke"),
    ("Jhn", "JOH", "John"), ("Act", "ACT", "Acts"), ("Rom", "ROM", "Romans"),
    ("1Co", "1CO", "1 Corinthians"), ("2Co", "2CO", "2 Corinthians"), ("Gal", "GAL", "Galatians"),
    ("Eph", "EPH", "Ephesians"), ("Php", "PHI", "Philippians"), ("Col", "COL", "Colossians"),
    ("1Th", "1TH", "1 Thessalonians"), ("2Th", "2TH", "2 Thessalonians"),
    ("1Ti", "1TI", "1 Timothy"), ("2Ti", "2TI", "2 Timothy"), ("Tit", "TIT", "Titus"),
    ("Phm", "PHM", "Philemon"), ("Heb", "HEB", "Hebrews"), ("Jas", "JAM", "James"),
    ("1Pe", "1PE", "1 Peter"), ("2Pe", "2PE", "2 Peter"), ("1Jn", "1JO", "1 John"),
    ("2Jn", "2JO", "2 John"), ("3Jn", "3JO", "3 John"), ("Jud", "JUD", "Jude"),
    ("Rev", "REV", "Revelation"),
]

def build(source: Path, output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("Refusing to replace an existing corpus.")
    translations = {v[1]: v[0] for v in BOOK_ROWS}
    manifest = json.loads((source / "step_downloads.json").read_text())
    counts = Counter()
    with closing(sqlite3.connect(output)) as db, db:
        db.executescript("""
            PRAGMA journal_mode=DELETE;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE books (code TEXT PRIMARY KEY, name TEXT NOT NULL, position INTEGER NOT NULL, testament TEXT NOT NULL);
            CREATE TABLE tokens (book TEXT NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL, dataset TEXT NOT NULL, fields TEXT NOT NULL);
            CREATE TABLE translations (book TEXT NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL, edition TEXT NOT NULL, text TEXT NOT NULL, PRIMARY KEY(book,chapter,verse,edition));
            CREATE VIRTUAL TABLE verse_search USING fts5(book UNINDEXED, chapter UNINDEXED, verse UNINDEXED, edition UNINDEXED, text);
        """)
        db.executemany("INSERT INTO books VALUES (?,?,?,?)", [(r[0], r[2], i+1, "OT" if i<39 else "NT") for i,r in enumerate(BOOK_ROWS)])
        pattern = re.compile(r"^([1-3]?[A-Z][a-z]{1,2})\.(\d+)\.(\d+)")
        headers = {}
        for item in manifest["files"]:
            path = source / item["name"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Source integrity check failed.")
            dataset = "TAGNT" if path.name.startswith("TAGNT") else "TAHOT"
            batch = []
            header = []
            with path.open(encoding="utf-8-sig") as handle:
                for line in handle:
                    line = line.rstrip("\r\n")
                    match = pattern.match(line)
                    if not match:
                        if not re.match(r"^[1-3]?[A-Z][a-z]{1,2}\.", line):
                            if len(header) < 500:
                                header.append(line)
                        continue
                    if match[1] not in {r[0] for r in BOOK_ROWS}:
                        raise ValueError("Unmapped source book.")
                    fields = line.split("\t")
                    if "#" not in fields[0]:
                        # TAHOT also supplies redundant verse-level display lines.
                        continue
                    book, chapter, verse = match[1], int(match[2]), int(match[3])
                    batch.append((book, chapter, verse, dataset, json.dumps(fields, ensure_ascii=False, separators=(",", ":"))))
                    counts[book] += 1
            db.executemany("INSERT INTO tokens VALUES (?,?,?,?,?)", batch)
            headers[path.name] = header
        for name, edition in (("eng-asv", "ASV1901"), ("eng-web", "WEB-Classic")):
            archive = source / (name + "_vpl.zip")
            with ZipFile(archive) as zipped:
                text = zipped.read(name + "_vpl.txt").decode("utf-8-sig")
            batch = []
            extra = Counter()
            for line in text.splitlines():
                match = re.fullmatch(r"([A-Z0-9]{3}) (\d+):(\d+) (.*)", line)
                if not match:
                    raise ValueError("Malformed translation source row.")
                if match[1] not in translations:
                    extra[match[1]] += 1
                    continue
                batch.append((translations[match[1]], int(match[2]), int(match[3]), edition, match[4]))
            db.executemany("INSERT INTO translations VALUES (?,?,?,?,?)", batch)
            db.executemany("INSERT INTO verse_search VALUES (?,?,?,?,?)", batch)
            manifest[name] = {"url": "https://ebible.org/Scriptures/"+name+"_vpl.zip", "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "edition":edition, "included_verses":len(batch), "source_additional_books_not_in_this_corpus":dict(extra), "license":"Public domain"}
        db.execute("CREATE INDEX token_reference ON tokens(book,chapter,verse)")
        coverage = []
        for code, _, name in BOOK_ROWS:
            token_count, chapters, verses = db.execute("SELECT count(*),count(DISTINCT chapter),count(DISTINCT chapter || ':' || verse) FROM tokens WHERE book=?", (code,)).fetchone()
            compared = db.execute("SELECT edition,count(*) FROM translations WHERE book=? GROUP BY edition", (code,)).fetchall()
            if not token_count or len(compared) != 2:
                raise ValueError("Incomplete book coverage: "+name)
            coverage.append({"book":code,"name":name,"tokens":token_count,"chapters":chapters,"original_text_verse_references":verses,"translation_verses":dict(compared)})
        manifest.update({"schema_version":1,"canon":"39 Hebrew/Aramaic Old Testament books and all 27 New Testament books; no deuterocanonical original-language corpus", "coverage":coverage,"source_headers":headers,"adaptation":"Tab-separated word records converted to JSON rows and indexed in SQLite; all source word fields and textual-variant labels retained. English VPL text stored unchanged. Additional WEB books outside this declared 66-book corpus omitted explicitly.","versification_warning":"Reference numbers follow source conventions; alternate numbering remains in raw_reference. Do not assume translations and witness variants have a perfect word-for-word alignment.","historical_context":"No fabricated historical/cultural notes. Surrounding chapters are retrieved; time, people, situation and cultural interpretation require documented review."})
        db.executemany("INSERT INTO metadata VALUES (?,?)", [("schema_version","1"),("sources",json.dumps(manifest,ensure_ascii=False))])
        db.commit()
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Corpus integrity failed.")
    manifest["corpus_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest.pop("source_headers")
    output.with_name("corpus_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    result = build(args.source,args.output)
    print("Corpus:",len(result["coverage"]),"books;",sum(b["tokens"] for b in result["coverage"]),"word records;",result["corpus_sha256"])
