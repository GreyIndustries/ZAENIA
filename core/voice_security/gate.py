"""RAM-only utterance checks and one-use audio-bound proofs."""
from dataclasses import dataclass
from array import array
import hashlib
import math
import secrets
import time

@dataclass(frozen=True)
class VoiceProof:
    token: str

class IdentityGate:
    def __init__(self, scorer, threshold, mic, generation, audit=lambda reason:None, clock=time.monotonic):
        if type(threshold) not in (int,float) or not math.isfinite(threshold) or not 0.1 <= threshold <= 1:
            raise ValueError('Calibrated speaker threshold must be between 0.1 and 1.')
        self.scorer,self.threshold,self.mic,self.generation=scorer,threshold,mic,generation
        self.audit,self.clock=audit,clock
        self.baseline=generation()
        self._proofs={}
    def valid(self,mic):
        try:return mic==self.mic and self.generation()==self.baseline
        except Exception:return False
    def verify(self,pcm,mic,sample_rate=16000):
        now=self.clock()
        self._proofs={k:r for k,r in self._proofs.items() if r[2]>now}
        if not self.valid(mic):
            self.audit('identity_revoked');return None
        if sample_rate!=16000 or not isinstance(pcm,bytes) or len(pcm)%2 or not 32000 <= len(pcm) <= 640000:
            self.audit('invalid_audio');return None
        samples=array('h');samples.frombytes(pcm)
        import sys
        if sys.byteorder!='little':samples.byteswap()
        if math.sqrt(sum((v/32768.0)**2 for v in samples)/len(samples)) < 0.008:
            self.audit('insufficient_audio');return None
        # Every overlapping window must match; a long owner prefix must not
        # authorize a clearly different speaker at the end of the turn.
        size=48000;hop=24000
        windows=[pcm[i:i+size] for i in range(0,max(1,len(pcm)-size+1),hop)]
        if len(pcm)>size:windows.append(pcm[-size:])
        try:
            for window in windows:
                score=float(self.scorer(window))
                if not math.isfinite(score) or score<self.threshold:
                    self.audit('speaker_rejected');return None
        except Exception:
            self.audit('verification_failed');return None
        if not self.valid(mic):
            self.audit('identity_revoked');return None
        proof=VoiceProof(secrets.token_urlsafe(32))
        self._proofs[proof.token]=(proof,hashlib.sha256(pcm).digest(),self.clock()+15)
        return proof
    def consume(self,proof,pcm,mic):
        if not isinstance(proof,VoiceProof):return False
        record=self._proofs.pop(proof.token,None)
        return bool(record and record[0] is proof and record[1]==hashlib.sha256(pcm).digest()
                    and record[2]>self.clock() and self.valid(mic))
    def revoke(self):
        self._proofs.clear();self.baseline=None

class VerifiedPipeline:
    def __init__(self,gate,transcribe,deliver):
        self.gate,self.transcribe,self.deliver=gate,transcribe,deliver
    # Last outcome of the voice check, for the status heartbeat only:
    # None (no turn yet), True (owner verified) or False (not verified).
    last_verified=None
    def process(self,pcm,mic):
        proof=self.gate.verify(pcm,mic)
        self.last_verified=proof is not None
        if proof is None:return False
        try:text=self.transcribe(pcm).strip()
        except Exception:
            self.gate.consume(proof,pcm,mic);self.gate.audit('transcription_failed');return False
        if not text or not self.gate.consume(proof,pcm,mic):return False
        self.deliver(text)
        return True


def validate_calibration(calibration,profile_id,profile_digest):
    if not isinstance(calibration,dict) or calibration.get("profile_id")!=profile_id or calibration.get("profile_cipher_digest")!=profile_digest:
        raise ValueError("Calibration is not bound to the current encrypted profile.")
    threshold=calibration.get("threshold")
    observed=calibration.get("observed",{})
    gap=calibration.get("minimum_required_gap")
    if not isinstance(observed,dict):raise ValueError("Invalid calibration observations.")
    genuine=observed.get("genuine_min");impostor=observed.get("impostor_max")
    for value in (threshold,gap,genuine,impostor):
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError("Invalid calibration score.")
    if not .1<=threshold<=1 or not 0<gap<=2 or not -1<=genuine<=1 or not -1<=impostor<=1:
        raise ValueError("Calibration scores are out of bounds.")
    if genuine-impostor<gap or not impostor<threshold<genuine:
        raise ValueError("Calibration does not separate genuine and impostor scores.")
    for key,minimum in (("genuine_sample_count",3),("impostor_sample_count",2)):
        if type(observed.get(key)) is not int or observed[key]<minimum:
            raise ValueError("Calibration needs multiple genuine and impostor samples.")
    return float(threshold)
