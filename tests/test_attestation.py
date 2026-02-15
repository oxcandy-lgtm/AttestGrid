import unittest
import json
import os
import shutil
import tempfile
from src.attestation.canonical_json import CanonicalJson
from src.attestation.crypto import Ed25519Signer
from src.attestation.store import ReceiptStore
from src.attestation.node import AttestationNode

class TestAttestation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_receipts.db")
        self.store = ReceiptStore(self.db_path)
        self.signer = Ed25519Signer() # Generate ephemeral key
        # We need a proper signer with a private key
        priv, pub = Ed25519Signer.generate_key_pair()
        self.signer = Ed25519Signer(priv)
        self.pubkey = pub
        self.node = AttestationNode("test-node-01", self.signer, self.store)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_canonical_json(self):
        obj1 = {"b": 1, "a": 2}
        obj2 = {"a": 2, "b": 1}
        self.assertEqual(CanonicalJson.dumps(obj1), CanonicalJson.dumps(obj2))
        self.assertEqual(CanonicalJson.dumps(obj1), '{"a":2,"b":1}')

    def test_crypto_sign_verify(self):
        msg = "hello world"
        sig = self.signer.sign(msg)
        self.assertTrue(Ed25519Signer.verify(sig, msg, self.pubkey))
        self.assertFalse(Ed25519Signer.verify(sig, "hello world!", self.pubkey))

    def test_attestation_flow(self):
        task_id = "task-1"
        input_data = {"prompt": "test"}
        rules = {"max_len": 100}
        
        def run_fn(inp):
            return {"response": "ok"}

        receipt = self.node.attest(task_id, input_data, rules, run_fn)
        
        self.assertEqual(receipt['task_id'], task_id)
        self.assertEqual(receipt['validator_passed'], 1)
        self.assertTrue('signature' in receipt)
        self.assertTrue('sig_payload' in receipt)

        # Verify signature on the receipt
        self.assertTrue(Ed25519Signer.verify(
            receipt['signature'], 
            receipt['sig_payload'], 
            self.pubkey
        ))

    def test_idempotency(self):
        task_id = "task-idempotent"
        call_count = 0
        
        def run_fn(inp):
            nonlocal call_count
            call_count += 1
            return "result"

        # First call
        r1 = self.node.attest(task_id, "input", {}, run_fn)
        self.assertEqual(call_count, 1)

        # Second call
        r2 = self.node.attest(task_id, "input", {}, run_fn)
        self.assertEqual(call_count, 1) # Should not increment
        self.assertEqual(r1['signature'], r2['signature'])

    def test_tampering(self):
        task_id = "task-tamper"
        r = self.node.attest(task_id, "input", {}, lambda x: "res")
        
        # Tamper with payload
        original_payload = r['sig_payload']
        payload_obj = json.loads(original_payload)
        payload_obj['input_hash'] = "fake_hash"
        tampered_payload = CanonicalJson.dumps(payload_obj)

        # Verification should fail
        self.assertFalse(Ed25519Signer.verify(r['signature'], tampered_payload, self.pubkey))

if __name__ == '__main__':
    unittest.main()
