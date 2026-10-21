"""Offline interlinear evidence and separate, owner-reviewed context notes."""
from __future__ import annotations
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from core.foundation.auth.passkey import consume_fresh_auth, payload_digest
from core.foundation.security.audit import audit
from core.foundation.security.crypto import decrypt_text_scoped, encrypt_text_scoped
from core.foundation.security.io import atomic_write, file_lock, reject_link
from core.foundation.storage.paths import SCRIPTURE_FILE, SECURE_DIR, PROJECT_ROOT

CONTEXT_FILE = SECURE_DIR / "scripture_context.vault"
CONTEXT_SCOPE = "scripture_context_v1"
MANIFEST_FILE = PROJECT_ROOT / "data" / "scripture" / "corpus_manifest.json"
CONTEXT_FIELDS = ("passage_context", "historical_time", "situation", "culture", "people")

def canonical_reference(reference: str) -> tuple[str, int, int]:
    match = re.fullmatch(r"([1-3]?[A-Z][a-z]{1,2})[ .](\d+)[.:](\d+)", reference.strip())
    if not match or not 1 <= int(match[2]) <= 150 or not 0 <= int(match[3]) <= 176:
        raise ValueError("Use a STEP reference such as 1Jn.4.8, Pro.18.13 or Psa.103.1.")
    return match[1], int(match[2]), int(match[3])

def _context_records(passphrase: str) -> dict:
    reject_link(CONTEXT_FILE)
    if not CONTEXT_FILE.exists():
        return {"version":1,"records":{}}
    value = json.loads(decrypt_text_scoped(CONTEXT_FILE.read_bytes(),passphrase,scope=CONTEXT_SCOPE))
    if not isinstance(value,dict) or value.get("version") != 1 or not isinstance(value.get("records"),dict):
        raise ValueError("Malformed protected context notes.")
    return value

def update_context(record: dict, passphrase: str) -> None:
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(passphrase,"scripture.context.update")
    expected = {"reference", "sources", *CONTEXT_FIELDS}
    if not isinstance(record,dict) or set(record) != expected:
        raise ValueError("Context needs reference, passage_context, historical_time, situation, culture, people and sources.")
    book, chapter, verse = canonical_reference(record["reference"])
    if record["reference"] != f"{book}.{chapter}.{verse}":
        raise ValueError("Use the canonical reference in a context note.")
    for name in CONTEXT_FIELDS:
        if not isinstance(record[name],str) or not record[name].strip() or len(record[name]) > 4000:
            raise ValueError("Document each context field, including uncertainty.")
    if not isinstance(record["sources"],list) or not 1 <= len(record["sources"]) <= 20 or any(not isinstance(s,str) or not s.strip() or len(s) > 2000 for s in record["sources"]):
        raise ValueError("Context notes require documented sources.")
    Corpus().passage(record["reference"])
    snapshot = json.loads(json.dumps(record,ensure_ascii=False))
    consume_fresh_auth(passphrase,operation="scripture.context.update",payload={"record_digest":payload_digest(snapshot)})
    with file_lock(CONTEXT_FILE.with_suffix(".lock")):
        document = _context_records(passphrase)
        if len(document["records"]) >= 10000 and snapshot["reference"] not in document["records"]:
            raise ValueError("Context-note limit reached.")
        document["records"][snapshot["reference"]] = snapshot
        encrypted = encrypt_text_scoped(json.dumps(document,ensure_ascii=False),passphrase,scope=CONTEXT_SCOPE)
        atomic_write(CONTEXT_FILE,encrypted)
    audit("scripture.context_saved",operation="scripture.context.update",reason_code="owner_documented_review")

class Corpus:
    """Read-only source evidence. Glosses/variants are evidence, not verdicts."""
    def __init__(self, path: Path = SCRIPTURE_FILE):
        self.path = Path(path)
        reject_link(self.path)
        reject_link(MANIFEST_FILE)
        self.manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        expected = self.manifest["corpus_sha256"]
        digest = hashlib.sha256()
        with self.path.open("rb") as handle:
            for block in iter(lambda:handle.read(1024*1024),b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError("Scripture corpus integrity failed; restore the packaged corpus.")

    def _connect(self):
        db = sqlite3.connect(self.path.resolve().as_uri()+"?mode=ro",uri=True)
        try:
            db.execute("PRAGMA query_only=ON")
        except BaseException:
            db.close()
            raise
        return db

    def coverage(self) -> dict:
        return {"canon":self.manifest["canon"],"books":self.manifest["coverage"],
                "new_testament_books":27,"translations":["ASV1901","WEB-Classic"],
                "historical_context":self.manifest["historical_context"],
                "versification_warning":self.manifest["versification_warning"]}

    def passage(self, reference: str, *, passphrase: str | None = None) -> dict:
        book, chapter, verse = canonical_reference(reference)
        with closing(self._connect()) as db:
            rows = db.execute("SELECT dataset,fields FROM tokens WHERE book=? AND chapter=? AND verse=? ORDER BY rowid",(book,chapter,verse)).fetchall()
            translation = db.execute("SELECT edition,text FROM translations WHERE book=? AND chapter=? AND verse=? ORDER BY edition",(book,chapter,verse)).fetchall()
            if not rows and not translation:
                raise ValueError("This reference is absent from the declared corpus.")
            context = db.execute("SELECT chapter,verse,edition,text FROM translations WHERE book=? AND chapter BETWEEN ? AND ? ORDER BY chapter,verse,edition",(book,max(1,chapter-1),chapter+1)).fetchall()
            title = db.execute("SELECT name FROM books WHERE code=?",(book,)).fetchone()[0]
        words = []
        for dataset, raw in rows:
            fields = json.loads(raw)
            if dataset == "TAGNT":
                split = re.fullmatch(r"(.*?) \(([^()]*)\)",fields[1])
                original, transliteration = (split[1],split[2]) if split else (fields[1],"")
                word = {"raw_reference":fields[0],"original":original,"transliteration":transliteration,
                        "gloss":fields[2],"lexical_and_morphology":fields[3],"lemma_gloss":fields[4],"editions":fields[5]}
            else:
                word = {"raw_reference":fields[0],"original":fields[1],"transliteration":fields[2],
                        "gloss":fields[3],"lexical":fields[4],"morphology":fields[5],"editions":"TAHOT: preserve L/Q/K/variant markers in raw_reference"}
            words.append({"dataset":dataset,**word,"all_source_fields":fields})
        canonical = f"{book}.{chapter}.{verse}"
        reviewed = _context_records(passphrase)["records"].get(canonical) if passphrase is not None else None
        return {"reference":canonical,"book_name":title,"words":words,"translations":dict(translation),
                "surrounding_chapters":[{"chapter":c,"verse":v,"edition":e,"text":t} for c,v,e,t in context],
                "reviewed_context":reviewed,"missing_context_fields":[] if reviewed else list(CONTEXT_FIELDS),
                "context_status":"Owner-documented interpretation; evaluate sources and uncertainty" if reviewed else "Historical/cultural/person context requires review; no doctrinal conclusion is manufactured",
                "variant_warning":self.manifest["versification_warning"],
                "source_credit":"STEP Bible / Tyndale House Cambridge (CC BY 4.0); eBible.org ASV1901 and WEB Classic (public domain)"}

    def search(self, text: str, *, limit: int = 20) -> list[dict]:
        if not isinstance(text,str) or not text.strip() or len(text) > 200 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid Scripture search.")
        # Treat input as a literal phrase, never as SQL or arbitrary FTS syntax.
        query = '"'+text.replace('"','""')+'"'
        with closing(self._connect()) as db:
            rows = db.execute("SELECT book,chapter,verse,edition,text FROM verse_search WHERE verse_search MATCH ? LIMIT ?",(query,limit)).fetchall()
        return [{"reference":f"{b}.{c}.{v}","edition":e,"text":t} for b,c,v,e,t in rows]
