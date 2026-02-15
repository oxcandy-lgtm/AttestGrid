import argparse
import sys
import json
from src.attestation.crypto import Ed25519Signer
from src.attestation.canonical_json import CanonicalJson

def main():
    parser = argparse.ArgumentParser(description="Verify a deterministic attestation receipt.")
    parser.add_argument("--receipt", required=True, help="Path to the receipt JSON file.")
    parser.add_argument("--pubkey", required=True, help="Path to the public key (hex) file or raw hex string.")
    
    args = parser.parse_args()

    # Load receipt
    try:
        with open(args.receipt, 'r') as f:
            receipt = json.load(f)
    except Exception as e:
        print(f"Error loading receipt: {e}")
        sys.exit(1)

    # Load public key
    pubkey_hex = ""
    try:
        # Check if arg is a file
        with open(args.pubkey, 'r') as f:
            pubkey_hex = f.read().strip()
    except Exception:
        # Assume it's a raw hex string
        pubkey_hex = args.pubkey.strip()
    
    # Required fields check
    if 'signature' not in receipt or 'sig_payload' not in receipt:
        print("Error: Receipt missing 'signature' or 'sig_payload'.")
        sys.exit(1)

    signature = receipt['signature']
    sig_payload = receipt['sig_payload']

    # Verify
    print(f"Verifying receipt for task: {receipt.get('task_id', 'unknown')}...")
    print(f"Node ID: {receipt.get('node_id', 'unknown')}")
    
    valid = Ed25519Signer.verify(signature, sig_payload, pubkey_hex)

    if valid:
        print("\n✅ VERIFICATION SUCCESSFUL")
        print("The signature matches the payload. The receipt is authentic.")
        
        # Optional: Print payload details
        try:
           payload_obj = CanonicalJson.loads(sig_payload)
           print("\nVerified Payload:")
           print(json.dumps(payload_obj, indent=2))
        except:
           print("\n(Payload is not valid JSON, but signature matches bytes)")

    else:
        print("\n❌ VERIFICATION FAILED")
        print("The signature does NOT match the payload.")
        sys.exit(1)

if __name__ == "__main__":
    main()
