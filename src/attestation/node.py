import hashlib
import json
from typing import Any, Callable, Dict, List, Optional
from .canonical_json import CanonicalJson
from .crypto import Ed25519Signer
from .store import ReceiptStore

class AttestationNode:
    """
    The core logic for the Deterministic Attestation Node.
    Orchestrates execution, validation, and signing.
    """

    def __init__(
        self,
        node_id: str,
        signer: Ed25519Signer,
        store: ReceiptStore,
        logic_version: str = "1.0.0"
    ):
        self.node_id = node_id
        self.signer = signer
        self.store = store
        self.logic_version = logic_version

    def _hash(self, data: Any) -> str:
        """
        Compute SHA256 hash of canonical JSON representation.
        """
        canonical = CanonicalJson.dumps(data)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def attest(
        self,
        task_id: str,
        input_data: Any,
        rules: Dict[str, Any],
        run_fn: Callable[[Any], Any]
    ) -> Dict[str, Any]:
        """
        Execute a task deterministically and return a signed receipt.
        
        Args:
            task_id: Unique identifier for the task.
            input_data: Input data for the run_fn.
            rules: Validation rules (schema/logic) to check against the result.
            run_fn: The function to execute (e.g., LLM call or calculation).
        
        Returns:
            The stored Receipt dictionary.
        """
        # 1. Idempotency Check
        existing_receipt = self.store.get_receipt(task_id)
        if existing_receipt:
            return existing_receipt

        # 2. Execution
        try:
            result = run_fn(input_data)
        except Exception as e:
            # For now, if execution fails, we might want to store a failure receipt?
            # Or just propagate. User instructions imply "Deterministic Attestation" 
            # of *outputs*. If it crashes, maybe no output.
            # Let's propagate for now, or wrap in an error result.
            # Assuming run_fn handles its own error boundaries or we treat exceptions as failures.
            # Let's keep it simple: propagate.
            raise e

        # 3. Validation (Simple mock validation logic for v0)
        # In a real system, 'rules' would be a schema or policy.
        # Here we just check if result matches 'expected_schema' if present, etc.
        # For v0, let's assume 'rules' contains a 'validator_fn' or we just say "passed"
        # if run_fn succeeded, unless rules say otherwise.
        # Let's stick to the user's "pure validator logic" comment.
        # We will assume 'rules' might have some simple checks.
        
        validator_passed = True
        validator_errors = []
        
        # Example validation: if rules has 'required_keys', check them.
        if isinstance(result, dict) and 'required_keys' in rules:
            for key in rules['required_keys']:
                if key not in result:
                    validator_passed = False
                    validator_errors.append(f"Missing key: {key}")

        # 4. Construct Signature Payload
        input_hash = self._hash(input_data)
        rules_hash = self._hash(rules)
        output_hash = self._hash(result)

        sig_payload_dict = {
            "task_id": task_id,
            "node_id": self.node_id,
            "logic_version": self.logic_version,
            "input_hash": input_hash,
            "rules_hash": rules_hash,
            "output_hash": output_hash,
            "validator": {
                "passed": validator_passed,
                "errors": validator_errors
            }
        }
        
        # Canonicalize the payload structure itself
        sig_payload_str = CanonicalJson.dumps(sig_payload_dict)

        # 5. Sign
        signature = self.signer.sign(sig_payload_str)

        # 6. Store
        self.store.store_receipt(
            task_id=task_id,
            node_id=self.node_id,
            logic_version=self.logic_version,
            input_hash=input_hash,
            rules_hash=rules_hash,
            output_hash=output_hash,
            validator_passed=validator_passed,
            validator_errors=validator_errors,
            sig_payload=sig_payload_str,
            signature=signature,
            result=result
        )

        return self.store.get_receipt(task_id)
