from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from backend.workflow import store


PBKDF2_ITERATIONS = 120_000
TOKEN_STORE: dict[str, dict] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        iterations_s, salt_hex, digest_hex = stored.split("$", 2)
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def issue_token(user: dict) -> str:
    token = secrets.token_urlsafe(32)
    TOKEN_STORE[token] = {
        "user_id": user["id"],
        "role": user["role"],
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    return token


def resolve_token(token: str) -> dict | None:
    record = TOKEN_STORE.get(token)
    if not record:
        return None
    return store.get_user_by_id(record["user_id"])


def authenticate(email: str, password: str) -> dict | None:
    user = store.get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "roll_number": user.get("roll_number"),
        "department": user.get("department"),
        "programme": user.get("programme"),
        "phone": user.get("phone"),
        "photo_url": user.get("photo_url"),
    }
