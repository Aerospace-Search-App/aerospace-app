"""Auth servisi — **STUB** (Taha'nın kimlik doğrulama modülü takılana kadar).

Ne yapar: kayıt (e-posta tekrarsa 409), giriş (yanlış bilgi → 401), token yenileme (geçersiz → 401).
Token'lar `src/core/security.py`'deki sahte (stub) token'lardır: `stub-access.<id>.<imza>`.
Seed'li demo hesabı: `demo@aerospace.local` / `demo12345`.

TODO(Taha): Gerçek JWT (süreli access/refresh), bcrypt parola özeti, refresh token iptali.
Metot imzaları aynı kalırsa router'lar ve mobil uygulama değişmez.
"""

from dataclasses import dataclass

from loguru import logger

from src.core.errors import ConflictError, UnauthorizedError
from src.core.security import ACCESS_TOKEN_EXPIRES_IN, create_token, decode_token, hash_password, verify_password
from src.domain.entities import User
from src.domain.enums import UserRole
from src.domain.interfaces import UserRepository


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Login/refresh sonucu (`TokenResponse` şemasına birebir dönüşür)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRES_IN


class AuthService:
    """Kayıt, giriş ve token yenileme (stub)."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def register(self, email: str, password: str, full_name: str) -> User:
        normalized = email.strip().lower()
        if self._users.get_by_email(normalized) is not None:
            raise ConflictError("Bu e-posta adresiyle kayıtlı bir kullanıcı zaten var.")
        user = self._users.add(User(id=0, email=normalized, full_name=full_name.strip(), role=UserRole.ENGINEER,
                                    password_hash=hash_password(password)))
        logger.info("Kullanıcı kaydedildi: id={}", user.id)
        return user

    def login(self, email: str, password: str) -> TokenPair:
        user = self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("E-posta veya parola hatalı.")
        return self._tokens(user)

    def refresh(self, refresh_token: str) -> TokenPair:
        user_id = decode_token("refresh", refresh_token)
        user = self._users.get(user_id) if user_id is not None else None
        if user is None:
            raise UnauthorizedError("Refresh token geçersiz veya süresi dolmuş.")
        return self._tokens(user)

    def user_from_access_token(self, token: str) -> User | None:
        """Access token geçerliyse kullanıcıyı döner (`get_current_user`, `AUTH_ENABLED=true` iken kullanır)."""
        user_id = decode_token("access", token)
        return self._users.get(user_id) if user_id is not None else None

    @staticmethod
    def _tokens(user: User) -> TokenPair:
        return TokenPair(access_token=create_token("access", user.id), refresh_token=create_token("refresh", user.id))
