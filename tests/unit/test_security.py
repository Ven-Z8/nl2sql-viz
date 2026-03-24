import pytest
from app.core.security import encrypt_credential, decrypt_credential

SECRET_KEY = "a" * 32  # 32-byte test key


def test_encrypt_decrypt_roundtrip():
    plaintext = "postgresql://user:pass@localhost/db"
    ciphertext = encrypt_credential(plaintext, SECRET_KEY)
    assert ciphertext != plaintext
    assert decrypt_credential(ciphertext, SECRET_KEY) == plaintext


def test_different_encryptions_of_same_value_differ():
    plaintext = "secret"
    c1 = encrypt_credential(plaintext, SECRET_KEY)
    c2 = encrypt_credential(plaintext, SECRET_KEY)
    assert c1 != c2  # random IV per encryption


def test_wrong_key_raises():
    ciphertext = encrypt_credential("secret", SECRET_KEY)
    wrong_key = "b" * 32
    with pytest.raises(Exception):
        decrypt_credential(ciphertext, wrong_key)
