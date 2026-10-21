"""No real biometrics, credentials or microphone activation in these tests."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from core.voice_security import voice_only
from core.voice_security.windows_protection import protect


class VoiceOnlyTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache=Path(self.temp.name)/'test.dpapi'
        self.cache.write_bytes(b'fake-cipher')
        self.generation={'owner':'test-owner','policy':['a','b']}
        self.snapshot={'version':1,'generation':self.generation,
                       'vault':{'rules':[]},'moral':{},'profile':{'test':True}}

    def load(self, **overrides):
        snapshot={**self.snapshot,**overrides}
        with patch.object(voice_only,'CACHE',self.cache), \
             patch.object(voice_only,'generation',return_value=self.generation), \
             patch.object(voice_only,'protect',return_value=json.dumps(snapshot).encode()), \
             patch.object(voice_only,'normalize_vault',side_effect=lambda value:value), \
             patch.object(voice_only,'validate_policy'), \
             patch.dict(sys.modules,{'core.foundation.auth.speaker_profile':SimpleNamespace(validate_profile=lambda value:None)}):
            return voice_only.load()

    def test_valid_windows_snapshot_never_requests_a_passphrase(self):
        with patch.object(voice_only,'require_passkey',side_effect=AssertionError('Unexpected passkey prompt')):
            self.assertEqual(self.load()['profile'],{'test':True})

    def test_stale_snapshot_rejected_without_passkey_fallback(self):
        with self.assertRaises(PermissionError):self.load(generation={'owner':'older'})
        with self.assertRaises(PermissionError):self.load(version=2)

    def test_missing_and_oversized_cache_rejected(self):
        self.cache.unlink()
        with self.assertRaises(PermissionError):self.load()
        self.cache.write_bytes(b'X'*2_000_001)
        with self.assertRaises(PermissionError):self.load()

    def test_cached_api_still_applies_deny_and_sensitive_rules(self):
        snapshot={**self.snapshot,'vault':{'rules':[{'id':'test-deny','enabled':True,
                  'action':'deny','operations':['ui.tasks.write']}]}}
        with patch.object(voice_only,'load',return_value=snapshot), \
             patch.object(voice_only,'generation',return_value=self.generation), \
             patch.object(voice_only,'enabled',return_value=True), \
             patch('core.foundation.client_gate.credential_generation',return_value='test-owner'), \
             patch('core.foundation.client_gate.RuleEngine._policy_generation',return_value=('a','b')), \
             patch('core.foundation.client_gate.audit'):
            gate=voice_only.VoiceOnlyClientGate()
            self.assertTrue(gate.authorize('chat.reply'))
            self.assertFalse(gate.authorize('ui.tasks.write'))
            self.assertFalse(gate.authorize('auth.token.create'))
            with patch.object(voice_only,'enabled',return_value=False), self.assertRaises(PermissionError):
                gate.authorize('chat.reply')

    @unittest.skipUnless(os.name=='nt','Windows account protection')
    def test_windows_encryption_roundtrip_and_tamper_rejection(self):
        sample=b'isolated synthetic voice profile, no real owner data'
        sealed=protect(sample)
        self.assertNotIn(sample,sealed)
        self.assertEqual(protect(sealed,decrypt=True),sample)
        with self.assertRaises(OSError):protect(sealed[:-10]+b'XXXXXXXXXX',decrypt=True)


if __name__=='__main__':unittest.main()
