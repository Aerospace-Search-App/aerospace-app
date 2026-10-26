"""Parola hash'leme (bcrypt) ve JWT üretme/doğrulama."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings


def hash_password(password: str) -> str:
    # bcrypt 72 bayt sınırı: daha uzun parolalar kırpılır
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode())
    except ValueError:
        return False


def _encode(payload: dict, minutes: int) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(user_id: int, role: str) -> str:
    return _encode({"sub": str(user_id), "role": role, "typ": "access"}, get_settings().access_token_minutes)


def create_file_token(user_id: int, document_id: int) -> str:
    """PDF'i tarayıcıda açmak için kısa ömürlü, tek dokümana özel imzalı token."""
    return _encode({"sub": str(user_id), "doc": document_id, "typ": "file"}, get_settings().file_token_minutes)


def decode_token(token: str, expected_type: str = "access") -> dict:
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("Yanlış token türü")
    return payload
