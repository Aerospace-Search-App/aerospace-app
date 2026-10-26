"""Auth uçları (`/auth/*`) — Taha'nın modülünün şu anki şekli (sözleşme §3 kutusu), davranış **stub**.

Yollar şimdilik prefix'siz `/auth/*`; birleştirmede `main.py`'de tek satırla `/api/v1` altına alınacak.
TODO(Taha): gerçek implementasyon `auth_service.py` + `core/security.py`'ye takılır; bu dosya değişmez.
"""

from fastapi import APIRouter, Depends

from src.api.responses import errors
from src.application.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut
from src.application.services.auth_service import AuthService
from src.core.deps import get_auth_service, get_current_user
from src.domain.entities import User

router = APIRouter(prefix="/auth", tags=["Auth"])

_DEMO_NOTE = "Demo hesap: `demo@aerospace.local` / `demo12345`."


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    summary="Kayıt ol",
    description="Yeni kullanıcı hesabı oluşturur ve kullanıcı nesnesini döner. Parola en az 8 karakter. "
                "(Stub: Taha'nın modülü takılana kadar bellekte tutulur.)",
    responses=errors({409: "Bu e-posta ile kayıtlı kullanıcı var (CONFLICT)."}),
)
def register(body: RegisterRequest, svc: AuthService = Depends(get_auth_service)) -> UserOut:
    return UserOut.model_validate(svc.register(body.email, body.password, body.full_name))


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=200,
    summary="Giriş yap",
    description=f"E-posta ve parolayla giriş yapar; access (60 dk) ve refresh token döner. {_DEMO_NOTE} "
                "Stub modda token'lar `stub-access...` / `stub-refresh...` biçimindedir (gerçek JWT değil).",
    responses=errors({401: "E-posta veya parola hatalı (UNAUTHORIZED)."}),
)
def login(body: LoginRequest, svc: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return TokenResponse.model_validate(svc.login(body.email, body.password))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=200,
    summary="Token yenile",
    description="Login cevabındaki refresh token ile yeni bir token çifti alır.",
    responses=errors({401: "Refresh token geçersiz veya süresi dolmuş (UNAUTHORIZED)."}),
)
def refresh(body: RefreshRequest, svc: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return TokenResponse.model_validate(svc.refresh(body.refresh_token))


@router.get(
    "/me",
    response_model=UserOut,
    status_code=200,
    summary="Oturumdaki kullanıcı",
    description="Token'ın sahibi olan kullanıcıyı döner. `AUTH_ENABLED=false` iken demo kullanıcıyı döner.",
    responses=errors(auth=True),
)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
