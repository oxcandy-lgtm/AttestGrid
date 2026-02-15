import json
from typing import Any

class CanonicalJson:
    """
    Handles deterministic JSON serialization for attestation receipts.
    Ensures that fields are sorted and whitespace is minimal/consistent.
    """
    
    @staticmethod
    def dumps(data: Any) -> str:
        """
        Serialize data to a canonical JSON string.
        
        Rules:
        - Keys sorted (sort_keys=True)
        - No whitespace after separators (separators=(',', ':'))
        - UTF-8 characters preserved (ensure_ascii=False)
        """
        return json.dumps(
            data,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False
        )

    @staticmethod
    def loads(json_str: str) -> Any:
        """
        Load data from a JSON string.
        """
        return json.loads(json_str)
