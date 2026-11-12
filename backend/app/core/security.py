import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # Argon2id with the library's current recommended parameters

# Verifying against this when the account does not exist keeps response timing
# similar for known and unknown emails.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def derive_csrf_token(session_token: str, secret_key: str) -> str:
    return hmac.new(
        secret_key.encode(), f"csrf:{session_token}".encode(), hashlib.sha256
    ).hexdigest()


def csrf_token_matches(provided: str | None, session_token: str, secret_key: str) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(provided, derive_csrf_token(session_token, secret_key))
