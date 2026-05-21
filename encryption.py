"""AES-256-GCM encryption for message content with legacy Fernet fallback."""
import base64
import hashlib
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_fernet_instance = None
_aesgcm_instance = None


def _get_fernet(key: str) -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        # Derive a 32-byte key from the config key, then base64 encode for Fernet
        derived = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        _fernet_instance = Fernet(fernet_key)
    return _fernet_instance


def _get_aesgcm(key: str) -> AESGCM:
    global _aesgcm_instance
    if _aesgcm_instance is None:
        derived = hashlib.sha256(key.encode()).digest()
        _aesgcm_instance = AESGCM(derived)
    return _aesgcm_instance


def encrypt_message(plaintext: str, key: str) -> str:
    """Encrypt a plaintext message and return base64-encoded ciphertext."""
    aesgcm = _get_aesgcm(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    payload = nonce + ciphertext
    return base64.urlsafe_b64encode(payload).decode('utf-8')


def decrypt_message(ciphertext: str, key: str) -> str:
    """Decrypt a base64-encoded ciphertext and return plaintext."""
    try:
        raw = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
        if len(raw) < 13:
            raise ValueError("Invalid payload length")
        nonce = raw[:12]
        data = raw[12:]
        aesgcm = _get_aesgcm(key)
        return aesgcm.decrypt(nonce, data, None).decode('utf-8')
    except Exception:
        f = _get_fernet(key)
        return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
