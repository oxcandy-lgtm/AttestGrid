import os
import sys
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from .node import AttestationNode
from .crypto import Ed25519Signer
from .store import ReceiptStore

# --- Configuration ---
KEYS_DIR = ".keys"
PRIVATE_KEY_FILE = os.path.join(KEYS_DIR, "ed25519_private.hex")
PUBLIC_KEY_FILE = os.path.join(KEYS_DIR, "ed25519_public.hex")
DB_PATH = "receipts.db"
NODE_ID = os.getenv("NODE_ID", "default-node")

# --- Application ---
app = FastAPI(
    title="Deterministic Attestation Node",
    version="0.1.0",
    description="A trust layer for AI agents, providing generic verifiable receipts."
)

# --- State ---
node: Optional[AttestationNode] = None

# --- Models ---
class AttestRequest(BaseModel):
    task_id: str
    input: Dict[str, Any]
    rules: Optional[Dict[str, Any]] = {}

class ReceiptResponse(BaseModel):
    task_id: str
    node_id: str
    validator_passed: bool
    signature: str
    sig_payload: str
    # We include other fields as convenience
    created_at: int
    validator_errors: List[str]

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

@app.post("/v1/attest", response_model=ReceiptResponse)
async def attest(req: AttestRequest):
    """
    Attest to a task execution options.
    For v0, this acts as a 'validator node' where the execution
    is a pass-through (identity function) of the input.
    """
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    # v0: Pass-through execution (Identity)
    # The 'result' is the 'input' itself, validated against 'rules'.
    def run_fn(data):
        return data

    try:
        receipt = node.attest(
            task_id=req.task_id,
            input_data=req.input,
            rules=req.rules,
            run_fn=run_fn
        )
        return receipt
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
