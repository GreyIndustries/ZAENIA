"""One-time migration to passkeyless startup with verified-speaker requests.

Run locally: python -m core.voice_security.voice_only enable
The existing encryption must be unlocked once; its password is never cached.
"""
from __future__ import annotations
import argparse
import json
from core.foundation.storage.paths import SECURE_DIR, SPEAKER_PROFILE_FILE
from core.foundation.auth.passkey import credential_generation, consume_fresh_auth, require_passkey
from core.foundation.rules.engine import RuleEngine
from core.foundation.rules.vault import load_vault, normalize_vault
from core.foundation.moral_code.vault import load_policy, validate_policy
from core.foundation.security.io import atomic_write, reject_link, protect_storage
from core.voice_security.windows_protection import protect

CACHE = SECURE_DIR / 'voice_startup.dpapi'


def generation() -> dict:
    from core.voice_security.identity import digest, microphone_identity, CALIBRATION_FILE, VOICE_CAPABILITIES
    from core.foundation.client_gate import CLIENT_CAPABILITIES
    return {'owner': credential_generation(), 'policy': list(RuleEngine._policy_generation()),
            'speaker': digest(SPEAKER_PROFILE_FILE), 'calibration': digest(CALIBRATION_FILE),
            'microphone': list(microphone_identity()), 'voice': sorted(VOICE_CAPABILITIES),
            'api': sorted(CLIENT_CAPABILITIES)}


def enabled() -> bool:
    reject_link(CACHE)
    return CACHE.is_file()


def load(*, include_profile=True) -> dict:
    reject_link(CACHE)
    if not CACHE.is_file() or CACHE.stat().st_size > 2_000_000:
        raise PermissionError('Voice-only startup has not been set up locally.')
    before = generation()
    snapshot = json.loads(protect(CACHE.read_bytes(), decrypt=True))
    if snapshot.get('version') != 1 or snapshot.get('generation') != before or generation() != before:
        raise PermissionError('Voice enrollment or policy changed. Refresh voice-only setup locally.')
    snapshot['vault'] = normalize_vault(snapshot['vault'])
    validate_policy(snapshot['moral'])
    if include_profile:
        from core.foundation.auth.speaker_profile import validate_profile
        validate_profile(snapshot['profile'])
    else:
        snapshot.pop('profile',None)
    return snapshot


def enable() -> None:
    from core.foundation.auth.speaker_profile import load_encrypted_profile
    from core.voice_security.identity import CALIBRATION_FILE, digest
    from core.voice_security.gate import validate_calibration
    from core.foundation.rules.policy import assert_owner_scope
    import yaml
    before = generation()
    # Uses the established voice-service permission, not an owner-wide cached proof.
    binding = {'microphone': before['microphone'], 'profile': before['speaker'],
               'calibration': before['calibration'], 'capabilities': before['voice']}
    proof = require_passkey(operation='voice.service.open', payload=binding)
    assert_owner_scope(proof, 'voice.service.open')
    assert_owner_scope(proof, 'chat.reply')
    consume_fresh_auth(proof, operation='voice.service.open', payload=binding)
    snapshot = {'version': 1, 'generation': before, 'vault': load_vault(proof),
                'moral': load_policy(proof), 'profile': load_encrypted_profile(proof)}
    validate_calibration(yaml.safe_load(CALIBRATION_FILE.read_text(encoding='utf-8')),
                         snapshot['profile'].get('profile_id'), digest(SPEAKER_PROFILE_FILE))
    if generation() != before:
        raise PermissionError('Identity changed during migration. Run setup again.')
    sealed = protect(json.dumps(snapshot, allow_nan=False).encode('utf-8'))
    protect_storage(SECURE_DIR)
    atomic_write(CACHE, sealed)
    print('Voice-only startup enabled for this Windows account. No passphrase was stored.')


class VoiceOnlyClientGate:
    """Same scoped API policy, silently unlocked by this Windows account.

    API requests still need their API token and desktop-only actions their paired
    desktop key. Microphone requests are speaker-verified separately.
    """
    mode = 'voice_only'

    def __init__(self):
        from core.foundation.client_gate import ScopedClientGate
        snapshot = load(include_profile=False)
        self._gate = ScopedClientGate.__new__(ScopedClientGate)
        self._gate._rules = snapshot['vault']['rules']
        self._gate._owner_generation = snapshot['generation']['owner']
        self._gate._policy_generation = tuple(snapshot['generation']['policy'])
        self._generation = snapshot['generation']

    def authorize(self, operation: str) -> bool:
        if not enabled() or generation() != self._generation:
            raise PermissionError('Voice-only startup was revoked or changed.')
        return self._gate.authorize(operation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['enable', 'status'])
    args = parser.parse_args()
    if args.command == 'enable':
        enable()
    else:
        print('Voice-only startup configured.' if enabled() else 'One-time migration required.')


if __name__ == '__main__':
    main()
