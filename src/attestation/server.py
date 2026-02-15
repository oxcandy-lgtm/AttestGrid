import os
import sys
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from .node import AttestationNode
from .crypto import Ed25519Signer
from .store import ReceiptStore
from .canonical_json import CanonicalJson
import hashlib
import time

# --- Configuration ---
KEYS_DIR = ".keys"
PRIVATE_KEY_FILE = os.path.join(KEYS_DIR, "ed25519_private.hex")
PUBLIC_KEY_FILE = os.path.join(KEYS_DIR, "ed25519_public.hex")
DB_PATH = "receipts.db"
NODE_ID = os.getenv("NODE_ID", "default-node")

# --- Application ---
app = FastAPI(
    title="Deterministic Attestation Node",
    version="0.2.0-pre",
    description="A trust layer for AI agents, providing generic verifiable receipts."
)

# --- State ---
node: Optional[AttestationNode] = None

# --- Helpers ---
def receipt_hash(sig_payload_obj: dict, sig_hex: str) -> str:
    """
    Computes a deterministic hash of the receipt for future proof framing.
    Hash = SHA256( canonical(sig_payload) + "." + sig )
    """
    # IMPORTANT: must match canonicalization rules used everywhere else
    sig_payload_canon = CanonicalJson.dumps(sig_payload_obj)
    s = f"{sig_payload_canon}.{sig_hex}".encode("utf-8")
    return hashlib.sha256(s).hexdigest()

# --- Models ---
class AttestRequest(BaseModel):
    task_id: str
    input: Dict[str, Any]
    rules: Optional[Dict[str, Any]] = {}

class ReceiptModel(BaseModel):
    task_id: str
    node_id: str
    validator_passed: bool
    signature: str
    sig_payload: str
    created_at: int
    validator_errors: List[str]

class ReceiptMeta(BaseModel):
    request_id: str
    cached: bool
    ts: int
    processing_time_ms: int
    receipt_hash: str
    protocol: str = "AttestGrid/v0.2.0-pre"

class VerifyRequest(BaseModel):
    receipt: Dict[str, Any]

class VerifyResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    receipt_hash: Optional[str] = None

class AttestationResponse(BaseModel):
    receipt: ReceiptModel
    proof: Optional[Dict[str, Any]] = None
    meta: ReceiptMeta

# --- Startup ---
@app.on_event("startup")
def startup_event():
    global node
    
    # 1. Key Management
    if not os.path.exists(KEYS_DIR):
        os.makedirs(KEYS_DIR)
        
    if not os.path.exists(PRIVATE_KEY_FILE):
        print(f"Generating new keypair in {KEYS_DIR}...")
        priv, pub = Ed25519Signer.generate_key_pair()
        with open(PRIVATE_KEY_FILE, "w") as f:
            f.write(priv)
        with open(PUBLIC_KEY_FILE, "w") as f:
            f.write(pub)
    else:
        print(f"Loading existing keys from {KEYS_DIR}...")
    
    # Load private key
    with open(PRIVATE_KEY_FILE, "r") as f:
        priv_hex = f.read().strip()
        
    signer = Ed25519Signer(priv_hex)
    store = ReceiptStore(DB_PATH)
    
    node = AttestationNode(
        node_id=NODE_ID,
        signer=signer,
        store=store
    )
    print(f"Attestation Node {NODE_ID} initialized.")

# --- Routes ---

@app.get("/v1/node/public-key")
async def get_public_key():
    """
    Returns the public key in hex format.
    """
    if not os.path.exists(PUBLIC_KEY_FILE):
        raise HTTPException(status_code=500, detail="Keys not initialized")
    with open(PUBLIC_KEY_FILE, "r") as f:
        return {"public_key_hex": f.read().strip()}

@app.post("/v1/verify", response_model=VerifyResponse)
async def verify_receipt(req: VerifyRequest):
    """
    Verifies a receipt against this node's public key.
    Checks signature validity and returns a stable receipt_hash.
    """
    try:
        receipt = req.receipt
        
        # 1. Extract signature components
        sig_payload = receipt.get("sig_payload")
        # Support both 'signature' (internal model) and 'sig' (user requested alias)
        sig_hex = receipt.get("signature") or receipt.get("sig")

        if not isinstance(sig_payload, (dict, str)) or not isinstance(sig_hex, str):
            return VerifyResponse(valid=False, reason="missing_sig_payload_or_sig")

        # If payload is string (escaped JSON), load it. If dict, use as is.
        # The store saves it as string in python, but over API it might be dict or string depending on how it was serialized in receipt.
        # existing 'attest' returns 'receipt' with 'sig_payload' as STRING (JSON).
        # But if client sends it back as JSON object, we handle both.
        if isinstance(sig_payload, str):
            try:
                sig_payload_obj = CanonicalJson.loads(sig_payload)
                sig_payload_str = sig_payload
            except:
                return VerifyResponse(valid=False, reason="malformed_sig_payload_string")
        else:
            sig_payload_obj = sig_payload
            sig_payload_str = CanonicalJson.dumps(sig_payload_obj)

        # 2. Sanity Checks (Optional)
        node_id = receipt.get("node_id")
        logic_version = receipt.get("logic_version")
        
        if node_id and node_id != NODE_ID:
            return VerifyResponse(valid=False, reason="node_id_mismatch")
        
        # 3. Verify Signature
        # Need public key
        if not os.path.exists(PUBLIC_KEY_FILE):
             return VerifyResponse(valid=False, reason="node_keys_missing")
             
        with open(PUBLIC_KEY_FILE, "r") as f:
            pub_hex = f.read().strip()
            
        # Reconstruct message exactly as signed
        # The signature is over CanonicalJson.dumps(sig_payload_obj)
        # Which is exactly sig_payload_str if we normalized it correctly.
        # To be safe, always re-canonicalize from the object form.
        msg_to_verify = CanonicalJson.dumps(sig_payload_obj)
        
        is_valid = Ed25519Signer.verify(sig_hex, msg_to_verify, pub_hex)
        
        if not is_valid:
            return VerifyResponse(valid=False, reason="invalid_signature")
            
        # 4. Success -> Return Hash
        # Calculate receipt hash using the helper
        r_hash = receipt_hash(sig_payload_obj, sig_hex)
        
        return VerifyResponse(valid=True, receipt_hash=r_hash)

    except Exception as e:
        return VerifyResponse(valid=False, reason=f"exception: {str(e)}")

@app.post("/v1/attest", response_model=AttestationResponse)
async def attest(req: AttestRequest):
    """
    Attest to a task execution options.
    Returns { receipt, proof, meta } structure.
    """
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    start = time.perf_counter()
    request_id = hashlib.sha256(f"{req.task_id}-{time.time()}".encode()).hexdigest()[:8]

    # v0: Pass-through execution (Identity)
    def run_fn(data):
        return data

    try:
        # Check cache logic if needed, but AttestationNode handles idempotency via store.
        receipt_dict = node.attest(
            task_id=req.task_id,
            input_data=req.input,
            rules=req.rules,
            run_fn=run_fn
        )
        
        # Parse payload to get object for hashing
        # receipt_dict["sig_payload"] is a STRING (JSON).
        # We need the OBJECT for receipt_hash(sig_payload_obj, ...).
        sig_payload_obj = CanonicalJson.loads(receipt_dict["sig_payload"])

        meta = {
            "request_id": request_id,
            "cached": False, # Naive assumption, store handles idempotency but doesn't signal 'cached'
            "ts": int(time.time()),
            "processing_time_ms": int((time.perf_counter() - start) * 1000),
            "receipt_hash": receipt_hash(sig_payload_obj, receipt_dict["signature"]),
            "protocol": "AttestGrid/v0.2.0-pre",
        }

        return {
            "receipt": receipt_dict,
            "proof": None,
            "meta": meta
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
