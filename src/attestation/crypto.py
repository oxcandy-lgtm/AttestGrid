import os
import binascii
from typing import Tuple, Optional

# --- Backend Selection ---
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _crypto_ed
    from cryptography.hazmat.primitives import serialization as _crypto_ser
    from cryptography.exceptions import InvalidSignature as _CryptoInvalidSignature
    _HAS_CRYPTOGRAPHY = True
except Exception:
    _HAS_CRYPTOGRAPHY = False

try:
    import pure25519.ed25519_oop as _pure_ed
    _HAS_PURE_ED = True
except Exception:
    _HAS_PURE_ED = False

class Ed25519Signer:
    """
    Wrapper for Ed25519 signing and verification.
    Automatically chooses between 'cryptography' (fast) and 'pure25519' (pure python fallback).
    Uses raw 32-byte hex strings for key storage.
    """

    def __init__(self, private_key_hex: str = None):
        """
        Initialize with an optional private key hex string.
        """
        self._private_key_hex = private_key_hex

    @property
    def public_key_hex(self) -> str:
        """Returns the public key in hex format."""
        if not self._private_key_hex:
            raise ValueError("No private key loaded.")
        
        # We store keys as hex. Let's derive public key based on available backend.
        priv_bytes = binascii.unhexlify(self._private_key_hex)
        
        if _HAS_CRYPTOGRAPHY:
            sk = _crypto_ed.Ed25519PrivateKey.from_private_bytes(priv_bytes)
            pk = sk.public_key()
            public_bytes = pk.public_bytes(
                encoding=_crypto_ser.Encoding.Raw,
                format=_crypto_ser.PublicFormat.Raw
            )
            return binascii.hexlify(public_bytes).decode('utf-8')
        
        if _HAS_PURE_ED:
            sk = _pure_ed.SigningKey(priv_bytes)
            public_bytes = sk.get_verifying_key().to_bytes()
            return binascii.hexlify(public_bytes).decode('utf-8')
            
        raise RuntimeError("No ed25519 backend available. Install 'ed25519' or 'cryptography'.")

    def sign(self, message: str) -> str:
        """
        Sign a text message (UTF-8). Returns signature as hex string.
        """
        if not self._private_key_hex:
            raise ValueError("Signing capability requires a private key.")
        
        msg_bytes = message.encode('utf-8')
        priv_bytes = binascii.unhexlify(self._private_key_hex)
        
        if _HAS_CRYPTOGRAPHY:
            sk = _crypto_ed.Ed25519PrivateKey.from_private_bytes(priv_bytes)
            signature_bytes = sk.sign(msg_bytes)
            return binascii.hexlify(signature_bytes).decode('utf-8')
            
        if _HAS_PURE_ED:
            sk = _pure_ed.SigningKey(priv_bytes)
            signature_bytes = sk.sign(msg_bytes)
            return binascii.hexlify(signature_bytes).decode('utf-8')

        raise RuntimeError("No ed25519 backend available.")

    @staticmethod
    def verify(signature_hex: str, message: str, public_key_hex: str) -> bool:
        """
        Verify a signature against a message and public key.
        """
        try:
            pub_bytes = binascii.unhexlify(public_key_hex)
            sig_bytes = binascii.unhexlify(signature_hex)
            msg_bytes = message.encode('utf-8')
            
            if _HAS_CRYPTOGRAPHY:
                try:
                    pk = _crypto_ed.Ed25519PublicKey.from_public_bytes(pub_bytes)
                    pk.verify(sig_bytes, msg_bytes)
                    return True
                except _CryptoInvalidSignature:
                    return False
            
            if _HAS_PURE_ED:
                try:
                    vk = _pure_ed.VerifyingKey(pub_bytes)
                    vk.verify(sig_bytes, msg_bytes)
                    return True
                except _pure_ed.BadSignatureError:
                    return False
                    
            raise RuntimeError("No ed25519 backend available.")
        except (binascii.Error, ValueError, RuntimeError):
            return False

    @staticmethod
    def generate_key_pair() -> Tuple[str, str]:
        """
        Generate a new random key pair.
        Returns (private_key_hex, public_key_hex).
        """
        if _HAS_CRYPTOGRAPHY:
            sk = _crypto_ed.Ed25519PrivateKey.generate()
            pk = sk.public_key()
            
            priv_bytes = sk.private_bytes(
                encoding=_crypto_ser.Encoding.Raw,
                format=_crypto_ser.PrivateFormat.Raw,
                encryption_algorithm=_crypto_ser.NoEncryption()
            )
            pub_bytes = pk.public_bytes(
                encoding=_crypto_ser.Encoding.Raw,
                format=_crypto_ser.PublicFormat.Raw
            )
            return (
                binascii.hexlify(priv_bytes).decode('utf-8'),
                binascii.hexlify(pub_bytes).decode('utf-8')
            )
            
        if _HAS_PURE_ED:
            sk, vk = _pure_ed.create_keypair()
            return (
                binascii.hexlify(sk.to_bytes()).decode('utf-8'),
                binascii.hexlify(vk.to_bytes()).decode('utf-8')
            )

        raise RuntimeError("No ed25519 backend available.")
