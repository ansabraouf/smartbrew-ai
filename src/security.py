"""Password hashing and authentication utilities."""

import hashlib
import hmac
import secrets

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt.

    Args:
        password: Plain-text password supplied during account creation.

    Returns:
        A string containing the algorithm, salt, and derived hash.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"

def verify_password(password: str, encoded: str) -> bool:
    """Check a password against its stored PBKDF2 hash.

    Args:
        password: Candidate password.
        encoded: Stored algorithm/salt/hash string.

    Returns:
        True if the candidate matches, otherwise False.
    """
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 310_000)
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False
