"""Supplementary spoken phrase. A phrase match never proves speaker identity."""
from __future__ import annotations
import json
import queue
import re
import time
from argon2 import PasswordHasher, extract_parameters
from argon2.exceptions import VerificationError, InvalidHashError
from core.foundation.auth.passkey import consume_fresh_auth, require_passkey
from core.foundation.security.audit import audit
from core.foundation.security.io import atomic_write, file_lock, reject_link
from core.foundation.storage.paths import PROJECT_ROOT, SECURE_DIR, ensure_storage

VOICE_PHRASE_FILE = SECURE_DIR / "voice_phrase.hash"
VOICE_DEVICE_FILE = SECURE_DIR / "voice_device.json"
MODEL_DIR = PROJECT_ROOT / "data" / "models" / "vosk-model-small-en-us-0.15"
ph = PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2,hash_len=32,salt_len=16)

def normalize_phrase(text: str) -> str:
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9\s]","",text.lower().strip()))

def model_exists() -> bool:
    return MODEL_DIR.is_dir()

def list_input_devices() -> list[dict]:
    import sounddevice as sd
    return [{"index":i,"name":d.get("name","Unknown"),"hostapi":d.get("hostapi"),
             "max_input_channels":d.get("max_input_channels"),"default_samplerate":d.get("default_samplerate")}
            for i,d in enumerate(sd.query_devices()) if d.get("max_input_channels",0)>0]

def save_allowed_mic_by_index(device_index: int, passphrase: str | None = None) -> dict:
    if type(device_index) is not int or device_index < 0:
        raise ValueError("Invalid microphone index.")
    selected = next((d for d in list_input_devices() if d["index"]==device_index),None)
    if selected is None:
        raise ValueError("No input microphone has that index.")
    payload = {"device_index":device_index,"name":selected["name"],"hostapi":selected["hostapi"]}
    proof = passphrase if passphrase is not None else require_passkey(operation="auth.mic.change",payload=payload)
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(proof,"auth.mic.change")
    consume_fresh_auth(proof,operation="auth.mic.change",payload=payload)
    config = {"allowed_device_name":selected["name"],"allowed_hostapi":selected["hostapi"],
              "last_known_index":device_index,"created_for":"ZÆNIA voice phrase authentication","fallback_allowed":False}
    ensure_storage()
    with file_lock(VOICE_DEVICE_FILE.with_suffix(".lock")):
        atomic_write(VOICE_DEVICE_FILE,json.dumps(config,indent=2).encode())
    audit("voice.mic_changed",operation="auth.mic.change",reason_code="explicit_owner_selection")
    return config

def load_allowed_mic_config() -> dict:
    reject_link(VOICE_DEVICE_FILE)
    config = json.loads(VOICE_DEVICE_FILE.read_text(encoding="utf-8"))
    if not isinstance(config,dict) or config.get("fallback_allowed") is not False or not isinstance(config.get("allowed_device_name"),str) or type(config.get("allowed_hostapi")) is not int:
        raise PermissionError("The approved microphone configuration is invalid.")
    return config

def get_allowed_mic_index() -> int:
    config = load_allowed_mic_config()
    devices = [d for d in list_input_devices() if d["name"]==config["allowed_device_name"] and d["hostapi"]==config["allowed_hostapi"]]
    if len(devices)!=1:
        audit("voice.mic_unavailable",reason_code="missing_or_ambiguous_approved_device")
        name = str(config["allowed_device_name"]).strip()
        hint = " Open SteelSeries GG and turn Sonar on, then try again." if "sonar" in name.lower() else ""
        raise RuntimeError(f"Approved microphone '{name}' is missing or ambiguous. No fallback microphone is allowed.{hint}")
    return devices[0]["index"]

def listen_for_phrase(seconds: int = 5) -> str:
    if type(seconds) is not int or not 1 <= seconds <= 15:
        raise ValueError("Recording duration must be between 1 and 15 seconds.")
    if not model_exists():
        raise FileNotFoundError("The configured local Vosk model is missing.")
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer
    device = get_allowed_mic_index()
    audio: queue.Queue[bytes] = queue.Queue(maxsize=128)
    model = Model(str(MODEL_DIR))
    recognizer = KaldiRecognizer(model,16000)
    def callback(indata,frames,time_info,status):
        if status:
            audit("voice.recording_status",reason_code="audio_device_status")
        try:
            audio.put_nowait(bytes(indata))
        except queue.Full:
            pass
    parts = []
    deadline = time.monotonic()+seconds
    print("Listening through the approved microphone...")
    with sd.RawInputStream(device=device,samplerate=16000,blocksize=8000,dtype="int16",channels=1,callback=callback):
        while time.monotonic()<deadline:
            try: data=audio.get(timeout=min(0.25,max(0.001,deadline-time.monotonic())))
            except queue.Empty: continue
            if recognizer.AcceptWaveform(data):
                parts.append(json.loads(recognizer.Result()).get("text",""))
        parts.append(json.loads(recognizer.FinalResult()).get("text",""))
    return normalize_phrase(" ".join(parts))

def voice_phrase_exists() -> bool:
    reject_link(VOICE_PHRASE_FILE)
    return VOICE_PHRASE_FILE.is_file()

def create_voice_phrase(passphrase: str | None = None) -> None:
    if voice_phrase_exists():
        raise RuntimeError("Voice phrase already exists. Reset it explicitly before enrollment.")
    proof = passphrase if passphrase is not None else require_passkey(operation="auth.voice.enroll")
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(proof,"auth.voice.enroll")
    consume_fresh_auth(proof,operation="auth.voice.enroll")
    first = listen_for_phrase()
    if not first:
        raise ValueError("No phrase was detected.")
    print("Speak the same phrase again.")
    second = listen_for_phrase()
    if first != second:
        raise ValueError("Spoken phrases did not match.")
    ensure_storage()
    atomic_write(VOICE_PHRASE_FILE,ph.hash(first).encode(),overwrite=False)
    audit("voice.phrase_created",operation="auth.voice.enroll",reason_code="supplementary_phrase_only")

def verify_voice_phrase() -> bool:
    if not voice_phrase_exists():
        raise RuntimeError("Voice phrase has not been enrolled.")
    spoken = listen_for_phrase()
    if not spoken:
        return False
    try:
        stored = VOICE_PHRASE_FILE.read_text(encoding="utf-8")
        parameters = extract_parameters(stored)
        if not (1<=parameters.time_cost<=10 and 8192<=parameters.memory_cost<=262144 and 1<=parameters.parallelism<=16):
            return False
        valid = ph.verify(stored,spoken)
    except (VerificationError,InvalidHashError,ValueError):
        valid = False
    audit("voice.phrase_checked",reason_code="phrase_match" if valid else "phrase_rejected")
    return valid

def require_voice_phrase() -> None:
    if not verify_voice_phrase():
        raise PermissionError("Supplementary voice phrase failed.")

def reset_voice_phrase(passphrase: str | None = None) -> None:
    proof = passphrase if passphrase is not None else require_passkey(operation="auth.voice.reset")
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(proof,"auth.voice.reset")
    consume_fresh_auth(proof,operation="auth.voice.reset")
    reject_link(VOICE_PHRASE_FILE)
    with file_lock(VOICE_PHRASE_FILE.with_suffix(".lock")):
        VOICE_PHRASE_FILE.unlink(missing_ok=True)
    audit("voice.phrase_reset",operation="auth.voice.reset",reason_code="owner_requested_reset")

def reset_approved_mic(passphrase: str | None = None) -> None:
    proof = passphrase if passphrase is not None else require_passkey(operation="auth.mic.reset")
    from core.foundation.rules.policy import assert_owner_scope
    assert_owner_scope(proof,"auth.mic.reset")
    consume_fresh_auth(proof,operation="auth.mic.reset")
    reject_link(VOICE_DEVICE_FILE)
    with file_lock(VOICE_DEVICE_FILE.with_suffix(".lock")):
        VOICE_DEVICE_FILE.unlink(missing_ok=True)
    audit("voice.mic_reset",operation="auth.mic.reset",reason_code="owner_requested_reset")
