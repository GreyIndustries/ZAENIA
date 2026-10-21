"""Foundation paths. Startup configuration is never taken from a model request."""
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_override = os.environ.get("ZAENIA_FOUNDATION_DATA_DIR")
DATA_DIR = Path(_override).resolve() if _override else PROJECT_ROOT / "data"
SECURE_DIR = DATA_DIR / "secure"
PASSKEY_FILE = SECURE_DIR / "passkey.hash"
SALT_FILE = SECURE_DIR / "master.salt"
VAULT_FILE = SECURE_DIR / "rules.vault"
MORAL_VAULT_FILE = SECURE_DIR / "moral_code.vault"
AUDIT_FILE = SECURE_DIR / "audit.log"
SPEAKER_PROFILE_FILE = SECURE_DIR / "speaker_profile.vault"
AUTH_RATE_FILE = SECURE_DIR / "auth_attempts.sqlite3"
SCRIPTURE_FILE = DATA_DIR / "scripture" / "corpus.sqlite3"

def ensure_storage() -> None:
    if SECURE_DIR.is_symlink():
        raise PermissionError("Secure storage must not be a symbolic link.")
    SECURE_DIR.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        SECURE_DIR.chmod(0o700)
