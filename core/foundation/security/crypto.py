"""Compatible Scrypt/Fernet encryption with distinct subsystem key domains."""
from __future__ import annotations
import base64
import hashlib
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from core.foundation.security.io import atomic_write, file_lock, reject_link
from core.foundation.storage.paths import SALT_FILE, VAULT_FILE, MORAL_VAULT_FILE, SPEAKER_PROFILE_FILE, SECURE_DIR, ensure_storage

def get_or_create_salt() -> bytes:
    ensure_storage()
    with file_lock(SALT_FILE.with_suffix(".lock")):
        reject_link(SALT_FILE)
        if SALT_FILE.exists():
            salt = SALT_FILE.read_bytes()
            if len(salt) != 16:
                raise RuntimeError("The existing master salt is invalid; restore its backup.")
            return salt
        if any(path.exists() for path in (VAULT_FILE, MORAL_VAULT_FILE, SPEAKER_PROFILE_FILE)) or any(SECURE_DIR.glob("*.vault")):
            raise RuntimeError("Encrypted data exists but its master salt is missing. Restore the original salt; a replacement would not unlock the data.")
        salt = os.urandom(16)
        atomic_write(SALT_FILE, salt, overwrite=False)
        return salt

def _derive_key_from_salt(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or not passphrase or len(passphrase.encode("utf-8")) > 16384:
        raise ValueError("Invalid encryption passphrase.")
    # Preserve the established parameters: existing ciphertext must still decrypt.
    key = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(key)

def derive_fernet_key(passphrase: str) -> bytes:
    return _derive_key_from_salt(passphrase, get_or_create_salt())

def derive_scoped_fernet_key(passphrase: str, scope: str) -> bytes:
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("Encryption scope cannot be empty.")
    material = get_or_create_salt() + b"\x00ZAENIA-SECURE-SCOPE\x00" + scope.strip().encode("utf-8")
    return _derive_key_from_salt(passphrase, hashlib.sha256(material).digest()[:16])

def encrypt_text(plain_text: str, passphrase: str) -> bytes:
    return Fernet(derive_fernet_key(passphrase)).encrypt(plain_text.encode("utf-8"))

def decrypt_text(cipher_text: bytes, passphrase: str) -> str:
    return Fernet(derive_fernet_key(passphrase)).decrypt(cipher_text).decode("utf-8")

def encrypt_text_scoped(plain_text: str, passphrase: str, *, scope: str) -> bytes:
    return Fernet(derive_scoped_fernet_key(passphrase, scope)).encrypt(plain_text.encode("utf-8"))

def decrypt_text_scoped(cipher_text: bytes, passphrase: str, *, scope: str) -> str:
    return Fernet(derive_scoped_fernet_key(passphrase, scope)).decrypt(cipher_text).decode("utf-8")
