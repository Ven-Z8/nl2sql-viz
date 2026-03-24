from app.core.auth import hash_api_key, verify_api_key, generate_api_key


def test_generate_api_key_is_32_chars():
    key = generate_api_key()
    assert len(key) == 32
    assert key.isalnum()


def test_hash_and_verify_roundtrip():
    key = generate_api_key()
    hashed = hash_api_key(key)
    assert verify_api_key(key, hashed) is True


def test_wrong_key_fails_verification():
    key = generate_api_key()
    hashed = hash_api_key(key)
    assert verify_api_key("wrongkey", hashed) is False
