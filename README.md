# Deterministic Attestation Node
The Trust Layer for AI agents.

**Public Node:** https://veridict.matrix.jp  
**Live Stats:** https://veridict.matrix.jp/v1/stats

This node provides deterministic, signed, and verifiable receipts for structured task execution.
It prevents silent corruption, retry loops, and unverifiable LLM outputs.

> [!NOTE]
> On shared hosting, we use the pure-Python `ed25519` backend by default. `cryptography` is optional for performance.

## Why?
LLM outputs are probabilistic.

> This node is self-auditing: stats are generated from real receipts and verifications.

<!-- ATTESTGRID_STATS_START -->
**Live stats (auto-updated):**
- Total Receipts: **27**
- Verifications: **0**
- Blocked (passed:false): **10**
- Block rate: **0.370**
<!-- ATTESTGRID_STATS_END -->

They may:
- Produce structurally valid JSON with incorrect data
- Hallucinate addresses, IDs, or entities
- Change output between retries

This node introduces:
- Deterministic hashing
- Ed25519 cryptographic signatures
- Idempotent task execution
- Public verification without trusting the server

## Implementation Overview

### Canonical JSON
Implemented in: `src/attestation/canonical_json.py`

- `sort_keys=True`
- `separators=(',', ':')`
- No whitespace
- Strict deterministic serialization

This guarantees stable hashing across environments.

### Ed25519 Signing
Implemented in: `src/attestation/crypto.py`

- Uses `cryptography`
- RAW hex key format
- Lazy key generation
- Public verification support

### Hardened Receipt Schema
Implemented in: `src/attestation/store.py`

Schema includes:
- `node_id`
- `logic_version`
- `input_hash`
- `rules_hash`
- `output_hash`
- `validator_passed`
- `sig_payload`
- `signature`
- Epoch timestamp

This ensures auditability and forward compatibility.

### Decoupled Attestation Logic
Implemented in: `src/attestation/node.py`

The node:
- Accepts `task_id`, `input_data`, `rules`
- Uses injected `run_fn` (pure deterministic logic in v0)
- Builds a strictly defined signature payload
- Signs it
- Persists receipt
- Returns deterministic result

LLM execution is intentionally decoupled in v0.

## Signature Contract (MUST NOT CHANGE)
The signature is computed over:
```scss
canonical_json(receipt.sig_payload)
```

Where `sig_payload` contains:
- `task_id`
- `node_id`
- `logic_version`
- `input_hash`
- `rules_hash`
- `output_hash`
- `validator { passed, errors }`

Metadata such as timestamps, request IDs, or processing times are **NOT** signed.
This allows metadata changes without breaking verification.

## Automated Test Results
Test suite: `tests/test_attestation.py`

Includes:
- `test_canonical_json`
- `test_crypto_sign_verify`
- `test_attestation_flow`
- `test_idempotency`
- `test_tampering`

Result:
```nginx
Ran 5 tests in 0.059s
OK
```

## Manual Verification

### Step 1 — Generate a Receipt
Run your task using `AttestationNode`.
A receipt JSON will be produced.

### Step 2 — Verify Locally
```bash
python scripts/verify_receipt.py \
  --receipt receipt.json \
  --pubkey .keys/ed25519_public.hex
```

Output:
```yaml
Verifying receipt for task: task-1...
Node ID: test-node-01
✅ VERIFICATION SUCCESSFUL
The signature matches the payload. The receipt is authentic.
```
You do not need to trust the server.
Verification is purely mathematical.


### Step 3 — Verify via API (v0.2.0)
You can also verify a receipt using the node's verification endpoint.
This checks the signature against the node's public key and returns a stable receipt hash.

```bash
curl -s -X POST "http://localhost:8000/v1/verify" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "receipt": { ... your receipt object ... }
}
JSON
```
Response:
```json
{
  "valid": true,
  "receipt_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

## Public transparency endpoint

This node exposes public stats for auditability:

```bash
curl -s http://localhost:8000/v1/stats | jq
```

**Current status:** Total Receipts: `/v1/stats.receipts_total` | Blocked (passed:false): `/v1/stats.passed_false`

## What This Enables
- Detect hallucinated structured outputs
- Prevent silent pipeline corruption
- Avoid retry token burn
- Provide cryptographic audit trails
- Enable deterministic execution gates
- Future on-chain execution triggers

## Roadmap
- v1: Integrate with LLM execution loop
- v2: Network API wrapper (FastAPI)
- v3: Multi-node trust network
- v4: Optional on-chain attestation anchoring

## Philosophy
This project is not about generating outputs.
It is about verifying them.

If LLMs are probabilistic,

## v0.2.0-pre: proof container + receipt_hash

Responses now include:

- `proof`: reserved for future attestations (timestamp / transparency log / on-chain anchor)
- `meta.receipt_hash`: `sha256(canonical(sig_payload) + "." + sig)`

This allows attaching future proofs without changing the original signed receipt.
