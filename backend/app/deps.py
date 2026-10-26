"""FastAPI bağımlılıkları: JWT ile kimlik doğrulama ve admin kontrolü."""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .security import decode_token

USER_COLS = "id, email, username, full_name, role, organization, created_at"

bearer = HTTPBearer(auto_error=False, description="Giriş yanıtındaki access_token")


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Oturum gerekli", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(creds.credentials)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Oturum süresi doldu, tekrar giriş yapın")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Geçersiz oturum")
    user = db.fetch_one(f"SELECT {USER_COLS} FROM users WHERE id = %s", (user_id,))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Kullanıcı bulunamadı")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yönetici yetkisi gerekli")
    return user
