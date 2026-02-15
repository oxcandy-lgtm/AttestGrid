import os
import binascii
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

class Ed25519Signer:
    """
    Wrapper for Ed25519 signing and verification.
    Uses raw 32-byte hex strings for key storage to keep things simple.
    """

    def __init__(self, private_key_hex: str = None):
        """
        Initialize with an optional private key hex string.
        If None, no signing capability (verification only, if pubkey provided later).
        """
        self._private_key = None
        if private_key_hex:
            private_bytes = binascii.unhexlify(private_key_hex)
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)

    @property
    def public_key_hex(self) -> str:
        """Returns the public key in hex format."""
        if not self._private_key:
            raise ValueError("No private key loaded.")
        public_key = self._private_key.public_key()
        public_bytes = public_key.public_bytes(
            encoding=lambda: b'', # Hack to get raw bytes? No, wait.
            # Ed25519 public keys are just bytes.
            # cryptography library requires serialization format.
            # Let's use Raw encoding if available or standard SubjectPublicKeyInfo
        )
        # Actually for Ed25519 in 'cryptography', public_bytes can utilize Raw format
        from cryptography.hazmat.primitives import serialization
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return binascii.hexlify(public_bytes).decode('utf-8')

    def sign(self, message: str) -> str:
        """
        Sign a text message (UTF-8). Returns signature as hex string.
        """
        if not self._private_key:
            raise ValueError("Signing capability requires a private key.")
        
        signature_bytes = self._private_key.sign(message.encode('utf-8'))
        return binascii.hexlify(signature_bytes).decode('utf-8')

    @staticmethod
    def verify(signature_hex: str, message: str, public_key_hex: str) -> bool:
        """
        Verify a signature against a message and public key.
        """
        try:
            public_bytes = binascii.unhexlify(public_key_hex)
            signature_bytes = binascii.unhexlify(signature_hex)
            
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
            public_key.verify(signature_bytes, message.encode('utf-8'))
            return True
        except (InvalidSignature, binascii.Error, ValueError):
            return False

    @staticmethod
    def generate_key_pair() -> tuple[str, str]:
        """
        Generate a new random key pair.
        Returns (private_key_hex, public_key_hex).
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        
        # Get private bytes (Raw)
        from cryptography.hazmat.primitives import serialization
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Get public bytes (Raw)
        public_key = private_key.public_key()
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        return (
            binascii.hexlify(private_bytes).decode('utf-8'),
            binascii.hexlify(public_bytes).decode('utf-8')
        )
