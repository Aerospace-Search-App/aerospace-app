"""Auth şemaları — Taha'nın modülünün **şu anki** şekli (sözleşme §3, "Bu hafta: Taha'nın şekli" kutusu).

Ne işe yarar: `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me` uçlarının istek/cevap gövdeleri.
İskelet bu şekli birebir gösterir ki Taha'nın kodu takıldığında mobil ekip için hiçbir şey değişmesin.

Hedef şekilden farkı (birleştirmede yapılacak):
- `TokenResponse.user` (giriş cevabında kullanıcı nesnesi) eklenecek,
- `UserOut.role` (`ENGINEER` / `ADMIN`) eklenecek,
- yollar `/api/v1/auth/*` altına alınacak.
TODO(Taha): birleştirmede TokenResponse.user ve UserOut.role alanlarını ekle (sözleşme §3 hedef şekli).

Not: E-posta için `EmailStr` yerine basit bir `pattern` kullanılıyor; `EmailStr` ek bir bağımlılık
(`email-validator`) ister. Gerçek doğrulama (benzersizlik, normalize etme) Taha'nın servisinde yapılır.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Basit ve kasıtlı olarak hoşgörülü bir e-posta kalıbı: "bir şey @ bir şey . bir şey", boşluk yok.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PASSWORD_MIN_LENGTH = 8

# Baştaki/sondaki boşluk kırpılıp SONRA uzunluk/kalıp kontrol edilir (yalnız boşluk → 422).
# Parola alanları bilerek kırpılmaz: parola boşluk içerebilir.
StrippedStr = Annotated[str, StringConstraints(strip_whitespace=True)]


class RegisterRequest(BaseModel):
    """`POST /auth/register` gövdesi: yeni kullanıcı kaydı."""

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"email": "kagan@example.com", "password": "min8karakter", "full_name": "Kağan Bayrak"},
    ]})

    email: StrippedStr = Field(..., pattern=EMAIL_PATTERN, max_length=254,
                       description="Kullanıcının e-posta adresi (giriş adı).", examples=["kagan@example.com"])
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128,
                          description="En az 8 karakterli parola.", examples=["min8karakter"])
    full_name: StrippedStr = Field(..., min_length=1, max_length=100,
                           description="Ad soyad (1–100 karakter).", examples=["Kağan Bayrak"])


class LoginRequest(BaseModel):
    """`POST /auth/login` gövdesi (JSON). Parola uzunluğu burada kontrol edilmez; yanlışsa 401 döner."""

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"email": "kagan@example.com", "password": "min8karakter"},
    ]})

    email: StrippedStr = Field(..., pattern=EMAIL_PATTERN, max_length=254,
                       description="Kayıtlı e-posta adresi.", examples=["kagan@example.com"])
    password: str = Field(..., min_length=1, max_length=128,
                          description="Parola.", examples=["min8karakter"])


class RefreshRequest(BaseModel):
    """`POST /auth/refresh` gövdesi: süresi dolmamış refresh token ile yeni token çifti istenir."""

    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra={"examples": [
        {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh.demo"},
    ]})

    refresh_token: str = Field(..., min_length=1, description="Login cevabında alınan refresh token.",
                               examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh.demo"])


class TokenResponse(BaseModel):
    """Login ve refresh cevabı: access token (60 dk) + refresh token (7 gün).

    Taha'nın şu anki şeklinde `user` alanı **yok**. TODO(Taha): birleştirmede `user: UserOut` eklenecek.
    """

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.access.demo",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh.demo",
        "token_type": "bearer",
        "expires_in": 3600,
    }]})

    access_token: str = Field(..., description="İsteklerde `Authorization: Bearer <token>` olarak gönderilir.",
                              examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.access.demo"])
    refresh_token: str = Field(..., description="Access token süresi dolunca yenilemek için kullanılır.",
                               examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh.demo"])
    token_type: Literal["bearer"] = Field(default="bearer", description="Token tipi; her zaman \"bearer\".",
                                          examples=["bearer"])
    expires_in: int = Field(default=3600, ge=1, description="Access token'ın geçerlilik süresi (saniye).",
                            examples=[3600])


class UserOut(BaseModel):
    """Kullanıcı nesnesi (register ve `/auth/me` cevabı).

    Taha'nın şu anki şeklinde `role` alanı **yok**. TODO(Taha): birleştirmede `role: UserRole` eklenecek.
    """

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "id": 1, "email": "kagan@example.com", "full_name": "Kağan Bayrak",
        "created_at": "2026-10-26T09:30:00Z",
    }]})

    id: int = Field(..., description="Kullanıcı kimliği.", examples=[1])
    email: str = Field(..., description="E-posta adresi.", examples=["kagan@example.com"])
    full_name: str = Field(..., description="Ad soyad.", examples=["Kağan Bayrak"])
    created_at: datetime = Field(..., description="Kayıt zamanı (ISO 8601, UTC).",
                                 examples=["2026-10-26T09:30:00Z"])
