import hashlib
import secrets
import string
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def generate_api_key() -> str:
    """Generate a cryptographically secure 32-character alphanumeric API key."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def hash_api_key(api_key: str) -> str:
    """Hash an API key using argon2."""
    return _pwd_context.hash(api_key)


def key_digest(api_key: str) -> str:
    """Deterministic SHA-256 digest used as an O(1) lookup index.

    API keys are 32 chars of uniform random data, so an unsalted digest is safe
    as an index; the argon2 hash remains the credential verifier.
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, hashed: str) -> bool:
    """Verify an API key against its hash."""
    return _pwd_context.verify(api_key, hashed)
