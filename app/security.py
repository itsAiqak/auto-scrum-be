"""Passwords and login tokens. Standard library only: scrypt for passwords, SHA-256 for stored session tokens."""

import base64
import hashlib
import hmac
import secrets

# scrypt cost (n, r, p). Stored with each hash, so it can be raised later without breaking old passwords.
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    """'scrypt$n$r$p$salt$hash' (base64), with a new random salt each time."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except ValueError:
        return False
    return scheme == "scrypt" and hmac.compare_digest(actual, expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """What the database keeps instead of the token, so a leaked database can't be used to log in."""
    return hashlib.sha256(token.encode()).hexdigest()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()
