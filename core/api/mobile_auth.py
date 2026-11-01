"""One-use spoken challenges and revocable browser sessions, kept in RAM."""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

COOKIE = "zaenia_mobile_session"
CHALLENGE_COOKIE = "zaenia_voice_challenge"
APP_HEADER = "X-ZAENIA-APP"
CHALLENGE_TTL = 90
SESSION_TTL = 8 * 60 * 60
IDLE_TTL = 30 * 60
WORDS = ("apple", "river", "garden", "yellow", "seven", "window", "coffee", "purple", "silver",
         "orange", "winter", "morning", "paper", "summer", "happy", "little", "sunny", "table",
         "water", "music", "forest", "planet", "rabbit", "pencil")


class VoiceLoginError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


def key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def decode_clip(audio) -> bytes:
    if not isinstance(audio, str) or len(audio) > 640_000:
        raise VoiceLoginError("Keep the recording between 2 and 15 seconds.", 400)
    try:
        pcm = base64.b64decode(audio, validate=True)
    except (binascii.Error, ValueError) as error:
        raise VoiceLoginError("The recording could not be read.", 400) from error
    if len(pcm) % 2 or not 64_000 <= len(pcm) <= 480_000:
        raise VoiceLoginError("Keep the recording between 2 and 15 seconds.", 400)
    return pcm


class LocalSpeaker:
    """Uses the existing ECAPA model and profile-bound live calibration."""
    def __init__(self):
        self._baseline = None
        self._gate = None

    def verify(self, pcm: bytes) -> bool:
        from core.api import mobile_voice_profile as profile
        baseline = profile.session_generation()
        if baseline != self._baseline:
            import numpy as np
            import torch
            from core.foundation.auth.speaker_verifier import SpeakerVerifier
            from core.voice_security.gate import IdentityGate, validate_calibration
            snapshot = profile.load()
            reference = torch.nn.functional.normalize(torch.tensor(snapshot["embedding"], dtype=torch.float32), p=2, dim=0)
            threshold = validate_calibration(snapshot["calibration"], snapshot["profile_id"], snapshot["generation"]["profile"])
            verifier = SpeakerVerifier()
            if verifier.sample_rate != 16000 or verifier.missing_model_files():
                raise VoiceLoginError("The local speaker model needs setup on your PC.", 503)
            verifier.load_model()

            def score(clip):
                waveform = np.frombuffer(clip, dtype="<i2").astype(np.float32) / 32768.0
                return verifier.compare_embeddings(reference, verifier.create_embedding(waveform))

            if profile.session_generation() != baseline:
                raise VoiceLoginError("Voice enrollment changed. Try again.", 503)
            self._gate = IdentityGate(score, threshold, "mobile-browser", profile.session_generation)
            self._baseline = baseline
        # Trim leading/trailing silence before checking overlapping speaker windows.
        from array import array
        import math
        import sys
        samples = array("h")
        samples.frombytes(pcm)
        if sys.byteorder != "little":
            samples.byteswap()
        active = [i for i in range(0, len(samples), 320) if
                  math.sqrt(sum((v / 32768.0) ** 2 for v in samples[i:i + 320]) / len(samples[i:i + 320])) >= .008]
        if not active:
            return False
        pcm = pcm[max(0, active[0] - 1600) * 2:min(len(samples), active[-1] + 1920) * 2]
        proof = self._gate.verify(pcm, "mobile-browser")
        return proof is not None and self._gate.consume(proof, pcm, "mobile-browser")


@dataclass
class Session:
    created: float
    touched: float
    generation: object


class MobileAuth:
    def __init__(self, *, speaker=None, transcribe=None, generation=None, available=None, clock=time.monotonic):
        from core.api import mobile_voice_profile as profile
        self.speaker = speaker or LocalSpeaker().verify
        if transcribe is None:
            from core.api.ui_voice import recognize
            transcribe = recognize
        self.transcribe = transcribe
        self.generation = generation or profile.session_generation
        self.available = available or profile.configured
        self.clock = clock
        self.challenges = {}
        self.sessions = {}
        self.attempts = defaultdict(deque)
        self.lock = threading.RLock()
        self.verification_lock = threading.Lock()

    def _purge(self):
        now = self.clock()
        self.challenges = {k: v for k, v in self.challenges.items() if now < v[0]}
        self.sessions = {k: s for k, s in self.sessions.items() if now - s.created < SESSION_TTL and now - s.touched < IDLE_TTL}
        for bucket in list(self.attempts):
            while self.attempts[bucket] and self.attempts[bucket][0] <= now - 600:
                self.attempts[bucket].popleft()
            if not self.attempts[bucket]:
                del self.attempts[bucket]

    def _limit(self, bucket: str, maximum: int):
        self._purge()
        if len(self.attempts) >= 2048 and bucket not in self.attempts:
            raise VoiceLoginError("Voice sign-in is busy. Try again later.", 429)
        if len(self.attempts[bucket]) >= maximum:
            raise VoiceLoginError("Too many voice sign-in attempts. Try again in 10 minutes.", 429)
        self.attempts[bucket].append(self.clock())

    def challenge(self, peer: str, binding: str) -> dict:
        with self.lock:
            self._limit("challenge:all", 60)
            self._limit("challenge:" + peer, 10)
            try:
                ready = self.available()
            except Exception:
                ready = False
            if not ready:
                raise VoiceLoginError("Enable mobile voice sign-in once on your PC, then try again.", 503)
            challenge = secrets.token_urlsafe(32)
            phrase = " ".join(secrets.SystemRandom().sample(WORDS, 6))
            self.challenges[key(challenge)] = (self.clock() + CHALLENGE_TTL, key(binding), peer, phrase)
            return {"challenge_id": challenge, "phrase": phrase, "expires_in": CHALLENGE_TTL}

    def verify(self, challenge: str, binding: str, peer: str, audio) -> str:
        with self.lock:
            self._limit("verify:all", 30)
            self._limit("verify:" + peer, 5)
            record = self.challenges.pop(key(challenge), None)
            if not record or record[1] != key(binding) or record[2] != peer:
                raise VoiceLoginError("That voice prompt expired. Start a new voice check.")
        pcm = decode_clip(audio)
        if not self.verification_lock.acquire(blocking=False):
            raise VoiceLoginError("Another voice check is running. Please try again.", 429)
        try:
            before = self.generation()
            heard = " ".join(re.findall(r"[a-z]+", self.transcribe(pcm).lower()))
            if heard != record[3] or not self.speaker(pcm):
                raise VoiceLoginError("I couldn't verify your voice and the displayed words. Try a fresh prompt.")
            if self.generation() != before or not self.available():
                raise VoiceLoginError("Voice enrollment changed. Try again.", 503)
            token = secrets.token_urlsafe(32)
            with self.lock:
                self._purge()
                if len(self.sessions) >= 64:
                    oldest = min(self.sessions, key=lambda k: self.sessions[k].created)
                    del self.sessions[oldest]
                self.sessions[key(token)] = Session(self.clock(), self.clock(), before)
            return token
        except VoiceLoginError:
            raise
        except Exception as error:
            raise VoiceLoginError("Voice sign-in needs setup on your PC. You can still use your access token.", 503) from error
        finally:
            self.verification_lock.release()

    def issue_session(self) -> str:
        """A phone session for a sign-in that was verified another way (Face ID, face_passkey.py)."""
        token = secrets.token_urlsafe(32)
        with self.lock:
            self._purge()
            if len(self.sessions) >= 64:
                oldest = min(self.sessions, key=lambda k: self.sessions[k].created)
                del self.sessions[oldest]
            self.sessions[key(token)] = Session(self.clock(), self.clock(), self.generation())
        return token

    def authenticated(self, token: str) -> bool:
        if not token or len(token) > 128:
            return False
        with self.lock:
            self._purge()
            session = self.sessions.get(key(token))
            try:
                valid = session is not None and self.available() and session.generation == self.generation()
            except Exception:
                valid = False
            if not valid:
                self.sessions.pop(key(token), None)
                return False
            session.touched = self.clock()
            return True

    def logout(self, token: str):
        with self.lock:
            self.sessions.pop(key(token), None)
