"""Password hashing and session-token helpers.

New passwords are hashed with Argon2id using the OWASP-recommended parameters
(19 MiB memory, 2 iterations, 1 lane), which stay affordable on a small server.
Hashes made earlier with scrypt still verify and are upgraded to Argon2id at the
user's next successful sign-in (see ``needs_rehash``). Session tokens are random
256-bit values; only their SHA-256 digest is stored, so a database leak does not
expose usable sessions.
"""

import base64
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_argon2 = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
ARGON2_PREFIX = "$argon2id$"

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
HASH_PREFIX = "scrypt"

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    return _argon2.hash(password)


def is_password_hash(stored: str) -> bool:
    """True for a real password hash; False for the marker of a passwordless account."""
    return stored.startswith((ARGON2_PREFIX, f"{HASH_PREFIX}$"))


def needs_rehash(stored: str) -> bool:
    """Older scrypt hashes, or Argon2 hashes made with weaker parameters, should be replaced."""
    if stored.startswith(ARGON2_PREFIX):
        try:
            return _argon2.check_needs_rehash(stored)
        except InvalidHashError:
            return False
    return stored.startswith(f"{HASH_PREFIX}$")


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith(ARGON2_PREFIX):
        try:
            return _argon2.verify(stored, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    return _verify_scrypt(password, stored)


def _hash_scrypt(password: str) -> str:
    """Legacy format, kept so tests can create accounts that predate Argon2id."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN)
    return f"{HASH_PREFIX}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def _verify_scrypt(password: str, stored: str) -> bool:
    try:
        prefix, n, r, p, salt, digest = stored.split("$")
        if prefix != HASH_PREFIX:
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
