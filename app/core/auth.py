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


def verify_api_key(api_key: str, hashed: str) -> bool:
    """Verify an API key against its hash."""
    return _pwd_context.verify(api_key, hashed)
