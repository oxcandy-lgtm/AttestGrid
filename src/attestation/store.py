import sqlite3
import time
import json
from typing import Optional, Dict, Any, List
from .canonical_json import CanonicalJson

class ReceiptStore:
    """
    Persistence layer for Attestation Receipts using SQLite.
    Ensures idempotency and auditability with a hardened schema.
    """

    def __init__(self, db_path: str = "receipts.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS receipts (
                    task_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    logic_version TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    rules_hash TEXT NOT NULL,
                    output_hash TEXT NOT NULL,
                    validator_passed INTEGER NOT NULL, -- 0 or 1
                    validator_errors TEXT NOT NULL,    -- JSON array string
                    sig_payload TEXT NOT NULL,         -- The exact canonical string that was signed
                    signature TEXT NOT NULL,           -- Hex string
                    result TEXT NOT NULL,              -- Canonical JSON of the result
                    created_at INTEGER NOT NULL        -- Epoch seconds
                );
            """)
            conn.commit()

    def get_receipt(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a receipt by task_id.
        Returns None if not found, otherwise a dictionary matching the schema.
        """
        with sqlite3.connect(self.db_path) as conn:
            # enable dictionary access
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM receipts WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                # Deserialize JSON fields
                try:
                    d['validator_errors'] = CanonicalJson.loads(d['validator_errors'])
                    d['result'] = CanonicalJson.loads(d['result'])
                    d['validator_passed'] = bool(d['validator_passed'])
                except Exception:
                    # Fallback or log error? For now, let it fail or return raw?
                    # If data is corrupt, maybe better to fail.
                    pass
                return d
            return None

    def store_receipt(
        self,
        task_id: str,
        node_id: str,
        logic_version: str,
        input_hash: str,
        rules_hash: str,
        output_hash: str,
        validator_passed: bool,
        validator_errors: List[str],
        sig_payload: str,
        signature: str,
        result: Any
    ):
        """
        Store a new receipt.
        Raises sqlite3.IntegrityError if task_id already exists (idempotency guard).
        """
        created_at = int(time.time())
        result_json = CanonicalJson.dumps(result)
        validator_errors_json = CanonicalJson.dumps(validator_errors)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO receipts (
                    task_id, node_id, logic_version, input_hash, rules_hash, output_hash,
                    validator_passed, validator_errors, sig_payload, signature, result, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                node_id,
                logic_version,
                input_hash,
                rules_hash,
                output_hash,
                1 if validator_passed else 0,
                validator_errors_json,
                sig_payload,
                signature,
                result_json,
                created_at
            ))
            conn.commit()
