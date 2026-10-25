"""The Vault: passkey-locked storage for private documents, notes and research.

Opened from Settings with the same unlock as the Security tab (passkey in a
console, or spoken phrase plus voice), only in the paired desktop app. Each
item is encrypted with AES-256-GCM; the key is random and sealed to Grey's
Windows account with DPAPI (data/secure/vault.key.dpapi). Titles are inside
the encryption too, so the folder shows nothing about what's stored.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VAULT_DIR = PROJECT_ROOT / "data" / "vault"
KEY_FILE = PROJECT_ROOT / "data" / "secure" / "vault.key.dpapi"
MAX_ITEM = 15 * 2**20
MAX_ITEMS = 2000
_LOCK = threading.Lock()


def _dpapi(data: bytes, decrypt: bool = False) -> bytes:
    from core.voice_security.windows_protection import protect
    return protect(data, decrypt=decrypt)


class Vault:
    def __init__(self, folder: Path = VAULT_DIR, key_file: Path = KEY_FILE,
                 seal: Callable[..., bytes] = _dpapi):
        self.folder, self.key_file, self.seal = Path(folder), Path(key_file), seal
        self._key: bytes | None = None

    def _cipher(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if self._key is None:
            with _LOCK:
                if self.key_file.is_file():
                    self._key = self.seal(self.key_file.read_bytes(), decrypt=True)
                else:
                    key = AESGCM.generate_key(bit_length=256)
                    from core.foundation.security.io import atomic_write
                    atomic_write(self.key_file, self.seal(key), overwrite=False)
                    self._key = key
        return AESGCM(self._key)

    def _write(self, item_id: str, record: dict[str, Any]) -> None:
        nonce = os.urandom(12)
        blob = nonce + self._cipher().encrypt(nonce, json.dumps(record).encode("utf-8"), item_id.encode())
        from core.foundation.security.io import atomic_write
        self.folder.mkdir(parents=True, exist_ok=True)
        atomic_write(self.folder / f"{item_id}.bin", blob)

    def _read(self, item_id: str) -> dict[str, Any]:
        if not (len(item_id) == 32 and all(c in "0123456789abcdef" for c in item_id)):
            raise KeyError("No such item.")
        path = self.folder / f"{item_id}.bin"
        if not path.is_file():
            raise KeyError("No such item.")
        blob = path.read_bytes()
        return json.loads(self._cipher().decrypt(blob[:12], blob[12:], item_id.encode()))

    def save(self, *, title: str, text: str = "", name: str = "", data_b64: str = "", mime: str = "") -> dict[str, Any]:
        title = " ".join(str(title).split())[:200]
        if not title:
            raise ValueError("Give it a title.")
        raw = base64.b64decode(data_b64, validate=True) if data_b64 else b""
        if len(raw) + len(text) > MAX_ITEM:
            raise ValueError("Items can be up to 15 MB.")
        if len(list(self.folder.glob("*.bin"))) >= MAX_ITEMS:
            raise ValueError("The vault is full.")
        item_id = uuid.uuid4().hex
        record = {"title": title, "text": str(text)[:2_000_000], "name": str(name)[:200], "mime": str(mime)[:100],
                  "data": data_b64 if raw else "", "size": len(raw) or len(text),
                  "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self._write(item_id, record)
        return {"id": item_id, "title": title, "created": record["created"], "size": record["size"], "kind": "file" if raw else "note"}

    def list(self) -> list[dict[str, Any]]:
        items = []
        for path in self.folder.glob("*.bin") if self.folder.is_dir() else []:
            try:
                record = self._read(path.stem)
            except Exception:
                continue
            items.append({"id": path.stem, "title": record["title"], "created": record["created"], "size": record["size"],
                          "kind": "file" if record.get("data") else "note", "name": record.get("name", "")})
        return sorted(items, key=lambda item: item["created"], reverse=True)

    def get(self, item_id: str) -> dict[str, Any]:
        return {"id": item_id, **self._read(item_id)}

    def delete(self, item_id: str) -> None:
        self._read(item_id)  # only real vault items
        (self.folder / f"{item_id}.bin").unlink()


_VAULT: Vault | None = None


def vault() -> Vault:
    global _VAULT
    if _VAULT is None:
        _VAULT = Vault()
    return _VAULT
