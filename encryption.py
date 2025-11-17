import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import hashlib
import base64

def get_encryption_key(api_key: str) -> bytes:
    """Derives a 32-byte encryption key from the API key using SHA-256."""
    return hashlib.sha256(api_key.encode('utf-8')).digest()

def encrypt_data(data: str, api_key: str) -> str | None:
    """Encrypts data using AES-256-GCM and returns a base64-encoded string."""
    try:
        key = get_encryption_key(api_key)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # GCM recommended nonce size
        data_bytes = data.encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
        # Return nonce and ciphertext concatenated and base64-encoded
        return base64.b64encode(nonce + ciphertext).decode('utf-8')
    except Exception as e:
        print(f"Encryption failed: {e}")
        return None

def decrypt_data(encrypted_data_b64: str, api_key: str) -> str | None:
    """Decrypts a base64-encoded AES-256-GCM string."""
    try:
        key = get_encryption_key(api_key)
        encrypted_data = base64.b64decode(encrypted_data_b64)
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        aesgcm = AESGCM(key)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        print(f"Decryption failed: {e}")
        return None
