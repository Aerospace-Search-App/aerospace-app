"""Parola özeti ve token üretimi — **STUB** (Taha'nın gerçek JWT modülü takılana kadar).

Ne işe yarar:
- Parolalar düz metin saklanmaz: standart kütüphanedeki `hashlib.pbkdf2_hmac` ile tuzlanıp özetlenir.
- Token'lar gerçek JWT değildir; biçimi bilerek belirgindir: `stub-access.<user_id>.<imza>` /
  `stub-refresh.<user_id>.<imza>`. İmza, sabit bir anahtarla HMAC'tir; böylece sahte token "uydurulamaz"
  ama süre/iptal gibi özellikler yoktur. Aynı kullanıcı için hep aynı token üretilir (deterministik).

TODO(Taha): `bcrypt`/`passlib` ile parola özeti; `python-jose`/`PyJWT` ile süreli access (60 dk) ve
refresh (7 gün) JWT'leri; gizli anahtar `.env`'deki ayardan. Fonksiyon adları aynı kalırsa servisler değişmez.
"""

import hashlib
import hmac
import secrets
from typing import Literal

TokenKind = Literal["access", "refresh"]

ACCESS_TOKEN_EXPIRES_IN = 3600  # saniye (sözleşme §3: access token 60 dk)

# Sadece stub imzası için sabit anahtar; gizli bir değer DEĞİLDİR. TODO(Taha): ayardan gelen JWT_SECRET.
_STUB_SIGNING_KEY = b"aerospace-mobile-api-stub-key"
_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Parolayı rastgele tuzla özetler: `pbkdf2_sha256$<tekrar>$<tuz>$<özet>`."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    """Parola, saklanan özetle eşleşiyor mu (zamanlama saldırısına karşı `compare_digest`)."""
    try:
        _, iterations, salt, digest = (stored_hash or "").split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    except ValueError:
        return False
    return hmac.compare_digest(candidate, digest)


def _sign(kind: TokenKind, user_id: int) -> str:
    return hmac.new(_STUB_SIGNING_KEY, f"{kind}:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def create_token(kind: TokenKind, user_id: int) -> str:
    """Sahte (stub) token üretir, ör. `stub-access.1.3f9a...`."""
    return f"stub-{kind}.{user_id}.{_sign(kind, user_id)}"


def decode_token(kind: TokenKind, token: str) -> int | None:
    """Token geçerliyse kullanıcı id'sini, değilse `None` döner."""
    prefix, _, rest = token.partition(".")
    user_part, _, signature = rest.partition(".")
    if prefix != f"stub-{kind}" or not user_part.isdigit():
        return None
    user_id = int(user_part)
    return user_id if hmac.compare_digest(signature, _sign(kind, user_id)) else None
