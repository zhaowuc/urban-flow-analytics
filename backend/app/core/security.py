from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from backend.app.core.config import settings


PBKDF2_ITERATIONS = 180_000


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64decode(salt_text), int(rounds)
        )
        return hmac.compare_digest(digest, _b64decode(digest_text))
    except (TypeError, ValueError):
        return False


def create_access_token(user_id: int, username: str, roles: list[str], expires_in: int = 28_800) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "roles": roles,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }
    body = _b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        body, signature_text = token.split(".", 1)
        expected = hmac.new(settings.secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_text)):
            return None
        payload = json.loads(_b64decode(body))
        if int(payload.get("exp", 0)) <= int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None

