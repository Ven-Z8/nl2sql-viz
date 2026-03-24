import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_credential(plaintext: str, secret_key: str) -> str:
    """Encrypt a credential string using AES-256-GCM.

    Args:
        plaintext: The credential string to encrypt
        secret_key: The secret key (will be padded/truncated to 32 bytes)

    Returns:
        Base64-encoded string containing nonce + ciphertext
    """
    key = secret_key.encode()[:32].ljust(32, b"\0")
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_credential(token: str, secret_key: str) -> str:
    """Decrypt a credential token using AES-256-GCM.

    Args:
        token: The base64-encoded token to decrypt
        secret_key: The secret key (will be padded/truncated to 32 bytes)

    Returns:
        The decrypted credential string

    Raises:
        cryptography.exceptions.InvalidTag: If decryption fails (wrong key or corrupted data)
    """
    key = secret_key.encode()[:32].ljust(32, b"\0")
    aesgcm = AESGCM(key)
    raw = base64.b64decode(token)
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
