"""Utilities for PIN authentication without storing credentials in plain text."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import re
from typing import Optional

PBKDF2_ITERATIONS = int(os.environ.get("AUTH_PBKDF2_ITERATIONS", "310000"))


def normalize_identity(value: str) -> str:
    """Normalize NIP/NIK to digits only."""
    return re.sub(r"\D", "", str(value or ""))


def normalize_activation_code(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def valid_identity(value: str) -> bool:
    return len(normalize_identity(value)) in {16, 18}


def valid_pin(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", str(value or "")))


def generate_activation_code() -> str:
    """Create a one-time, 12-digit activation code for in-person delivery."""
    digits = f"{secrets.randbelow(10**12):012d}"
    return f"{digits[:4]}-{digits[4:8]}-{digits[8:]}"


def hash_credential(value: str, *, iterations: Optional[int] = None) -> str:
    """Salted PBKDF2-HMAC-SHA256 encoding suitable for PINs and activation codes."""
    salt = secrets.token_bytes(16)
    rounds = iterations or PBKDF2_ITERATIONS
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, rounds)
    return "$".join((
        "pbkdf2_sha256",
        str(rounds),
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    ))


def verify_credential(value: str, encoded: str) -> bool:
    try:
        algorithm, rounds_text, salt_text, expected_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_text)
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(expected_text + "=" * (-len(expected_text) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeEncodeError):
        return False


def hash_session_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(str(left or "").encode(), str(right or "").encode())
