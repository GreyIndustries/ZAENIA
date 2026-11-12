import base64
import tempfile
import unittest
from pathlib import Path

from core.api.vault import Vault


class VaultTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.vault = Vault(root / "vault", root / "secure" / "vault.key", seal=lambda data, decrypt=False: data)

    def tearDown(self):
        self.folder.cleanup()

    def test_notes_and_files_are_encrypted_at_rest(self):
        note = self.vault.save(title="Bank PIN hint", text="my secret hint")
        doc = self.vault.save(title="passport.png", name="passport.png", data_b64=base64.b64encode(b"\x89PNG data").decode(), mime="image/png")
        raw = b"".join(path.read_bytes() for path in (Path(self.folder.name) / "vault").glob("*.bin"))
        self.assertNotIn(b"secret hint", raw)
        self.assertNotIn(b"Bank PIN", raw)  # titles are encrypted too
        self.assertEqual({item["kind"] for item in self.vault.list()}, {"note", "file"})
        self.assertEqual(self.vault.get(note["id"])["text"], "my secret hint")
        self.assertEqual(base64.b64decode(self.vault.get(doc["id"])["data"]), b"\x89PNG data")
        self.vault.delete(note["id"])
        self.assertEqual(len(self.vault.list()), 1)

    def test_tampering_and_bad_ids_fail(self):
        item = self.vault.save(title="x", text="y")
        path = Path(self.folder.name) / "vault" / f"{item['id']}.bin"
        data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(bytes(data))
        with self.assertRaises(Exception):
            self.vault.get(item["id"])
        for bad in ("../../secure/vault.key", "abc"):
            with self.assertRaises(KeyError):
                self.vault.get(bad)


if __name__ == "__main__":
    unittest.main()
