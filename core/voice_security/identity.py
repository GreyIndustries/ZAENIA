"""Owner-approved, revocable voice service with narrow local action grants."""
from pathlib import Path
import hashlib
import math
from core.foundation.auth.passkey import require_passkey,consume_fresh_auth,credential_generation
from core.foundation.rules.engine import RuleEngine
from core.foundation.rules.models import OPERATIONS
from core.foundation.rules.vault import load_vault,CANONICAL_HARD
from core.foundation.moral_code.vault import load_policy
from core.foundation.rules.policy import assert_owner_scope
from core.foundation.security.io import reject_link
from core.foundation.security.audit import audit
from core.foundation.storage.paths import SPEAKER_PROFILE_FILE,SECURE_DIR
from core.voice_security.gate import IdentityGate,validate_calibration

CALIBRATION_FILE=SECURE_DIR/'speaker_auth_calibration.yaml'
VOICE_CAPABILITIES=frozenset({'chat.reply','ui.tasks.write','ui.calendar.write','memory.read','memory.write',
                            'notifications.read','notifications.write','calendar.read','tasks.read'})
VOICE_CAPABILITIES = VOICE_CAPABILITIES | frozenset({'weather.read','status.read','assistant.platform.read',
    'assistant.apps.launch','assistant.documents.read','assistant.platform.write','files.read'})

def digest(path):
    reject_link(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()

def microphone_identity():
    from core.foundation.auth.voice_passkey import get_allowed_mic_index,VOICE_DEVICE_FILE
    import sounddevice as sd
    index=get_allowed_mic_index()
    device=sd.query_devices(index)
    return (index,str(device['name']),int(device['hostapi']),digest(VOICE_DEVICE_FILE))

class OwnerIdentity:
    def __init__(self):
        import numpy as np
        import torch
        import yaml
        from core.foundation.auth.speaker_profile import load_encrypted_profile
        from core.foundation.auth.speaker_verifier import SpeakerVerifier
        self.mic=microphone_identity()
        self.capabilities=VOICE_CAPABILITIES
        binding={'microphone':list(self.mic),'profile':digest(SPEAKER_PROFILE_FILE),
                 'calibration':digest(CALIBRATION_FILE),'capabilities':sorted(self.capabilities)}
        from core.voice_security import voice_only
        self.voice_only=voice_only.enabled()
        proof=None
        if self.voice_only:
            approved_generation=self.generation()
            snapshot=voice_only.load()
            self.rules=snapshot['vault']['rules']
            profile=snapshot['profile']
            del snapshot
        else:
            proof=require_passkey(operation='voice.service.open',payload=binding)
            assert_owner_scope(proof,'voice.service.open')
            assert_owner_scope(proof,'chat.reply')
            consume_fresh_auth(proof,operation='voice.service.open',payload=binding)
            approved_generation=self.generation()
            self.rules=load_vault(proof)['rules'];load_policy(proof)
            profile=load_encrypted_profile(proof)
        calibration=yaml.safe_load(CALIBRATION_FILE.read_text(encoding='utf-8'))
        try:threshold=validate_calibration(calibration,profile.get('profile_id'),binding['profile'])
        except ValueError as error:
            raise RuntimeError('Run profile-bound live calibration: py -3.11 -m core.voice_security.calibrate') from error
        values=profile['speaker_embedding']
        if not all(math.isfinite(float(v)) for v in values):raise RuntimeError('Invalid speaker embedding.')
        self.reference=torch.nn.functional.normalize(torch.tensor(values,dtype=torch.float32),p=2,dim=0)
        self.verifier=SpeakerVerifier()
        if self.verifier.sample_rate!=16000 or self.verifier.missing_model_files():
            raise RuntimeError('A complete local 16 kHz ECAPA model is required; run the existing model setup first.')
        # A missing model is rejected before load_model can attempt cache/network repair.
        self.verifier.load_model()
        def scorer(pcm):
            waveform=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768.0
            candidate=self.verifier.create_embedding(waveform)
            return self.verifier.compare_embeddings(self.reference,candidate)
        self.baseline=approved_generation
        if self.generation()!=approved_generation or microphone_identity()!=self.mic:
            raise PermissionError("Protected identity or policy changed during startup.")
        if (binding['profile'],binding['calibration'])!=(digest(SPEAKER_PROFILE_FILE),digest(CALIBRATION_FILE)):
            raise PermissionError('Identity changed during startup; restart and authenticate.')
        del proof,profile,values
        self.gate=IdentityGate(scorer,threshold,self.mic,self.generation,
            lambda reason:audit('voice.turn_rejected',operation='chat.reply',reason_code=reason))
    def generation(self):
        return (credential_generation(),RuleEngine._policy_generation(),digest(SPEAKER_PROFILE_FILE),digest(CALIBRATION_FILE),microphone_identity())
    def authorize(self,operation='chat.reply'):
        if getattr(self,'voice_only',False):
            from core.voice_security.voice_only import enabled
            if not enabled():raise PermissionError('Voice-only startup was revoked; restart voice.')
        spec=OPERATIONS.get(operation) if isinstance(operation,str) else None
        if spec is None or operation not in self.capabilities or spec.sensitive:
            raise PermissionError('This operation is not approved for the voice service.')
        if self.generation()!=self.baseline:raise PermissionError('Owner credential or protected policy changed; restart voice.')
        if any(r['enabled'] and r['id'] not in CANONICAL_HARD and r['action'] in ('deny','require_reauth')
               and ('*' in r['operations'] or operation in r['operations']) for r in self.rules):
            raise PermissionError('The active policy requires a different authorization for this operation.')
    def close(self):
        self.gate.revoke();self.reference=None;self.verifier=None
