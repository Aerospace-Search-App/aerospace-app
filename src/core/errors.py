"""Hata tipleri ve tek tip hata cevabı.

Ne işe yarar: Servisler HTTP bilmez; bir sorun olduğunda `NotFoundError("Standart bulunamadı: id=7")` gibi
bir `AppError` alt sınıfı fırlatır. Burada kayıtlı global handler'lar bu hatayı yakalayıp HTTP koduna ve
her zaman aynı JSON formatına çevirir:

    {"error": {"code": "NOT_FOUND", "message": "Standart bulunamadı: id=7", "details": null}}

Benzetme: Havalimanındaki tek "kayıp eşya" bankosu gibi; hata nereden gelirse gelsin, yolcuya (mobil
uygulamaya) hep aynı formda cevap verilir. Böylece mobil ekip tek bir hata modeli yazar.

Kural: istemciye ham `str(e)` veya stack trace dönülmez; beklenmeyen hatalar sadece loglanır.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Tüm uygulama hatalarının atası. Alt sınıflar sadece `status_code` ve `code` belirler."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "Beklenmeyen bir hata oluştu."

    def __init__(self, message: str | None = None, details: Any = None) -> None:
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "BAD_REQUEST"
    default_message = "Geçersiz istek."


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    default_message = "Kimlik doğrulaması gerekli."


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    default_message = "Bu işlem için yetkiniz yok."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    default_message = "Kayıt bulunamadı."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    default_message = "Kayıt zaten mevcut."


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"
    default_message = "Dosya boyutu sınırı aşıldı."


class UnsupportedFileError(AppError):
    status_code = 415
    code = "UNSUPPORTED_FILE"
    default_message = "Desteklenmeyen dosya türü. Sadece PDF kabul edilir."


class LLMUnavailableError(AppError):
    status_code = 503
    code = "LLM_UNAVAILABLE"
    default_message = "Dil modeli servisine şu anda ulaşılamıyor."


# Starlette'in kendi ürettiği HTTP hataları (bilinmeyen yol, yanlış metot vb.) için kod + Türkçe mesaj.
# METHOD_NOT_ALLOWED sözleşmedeki hata kodu listesinde yok (bkz. rapor: sözleşme sorusu).
_HTTP_STATUS_MAP: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "Geçersiz istek."),
    401: ("UNAUTHORIZED", "Kimlik doğrulaması gerekli."),
    403: ("FORBIDDEN", "Bu işlem için yetkiniz yok."),
    404: ("NOT_FOUND", "İstenen adres bulunamadı."),
    405: ("METHOD_NOT_ALLOWED", "Bu adres için HTTP metodu desteklenmiyor."),
    413: ("PAYLOAD_TOO_LARGE", "İstek gövdesi çok büyük."),
    415: ("UNSUPPORTED_FILE", "Desteklenmeyen içerik türü."),
}


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    """Sözleşmedeki `ErrorResponse` gövdesini üretir (tek yerde tanımlı ki format hiç kaymasın)."""
    return {"error": {"code": code, "message": message, "details": details}}


def _error_response(status_code: int, code: str, message: str, details: Any = None,
                    headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(error_body(code, message, details)),
        headers=headers,
    )


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Servislerin fırlattığı `AppError`'ları kendi kod/mesajıyla döner."""
    assert isinstance(exc, AppError)
    return _error_response(exc.status_code, exc.code, exc.message, exc.details)


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Framework'ün ürettiği HTTP hatalarını (404 bilinmeyen yol, 405 vb.) aynı formata çevirir."""
    assert isinstance(exc, StarletteHTTPException)
    code, message = _HTTP_STATUS_MAP.get(exc.status_code, ("HTTP_ERROR", "İstek işlenemedi."))
    if exc.status_code == 404:
        message = f"İstenen adres bulunamadı: {request.url.path}"
    return _error_response(exc.status_code, code, message, headers=getattr(exc, "headers", None))


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """422: Pydantic doğrulama hatalarını sade bir alan listesine çevirir.

    Ham `input` / `ctx` alanları bilinçli olarak dönülmez: içlerinde JSON'a çevrilemeyen nesneler
    (ör. exception) olabilir ve kullanıcının gönderdiği veriyi geri yansıtmak gereksizdir.
    """
    assert isinstance(exc, RequestValidationError)
    details = [
        {"field": ".".join(str(part) for part in err.get("loc", ())), "message": str(err.get("msg", ""))}
        for err in exc.errors()
    ]
    return _error_response(422, "VALIDATION_ERROR", "İstek doğrulanamadı. Alanları kontrol edin.", details)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """500: Beklenmeyen hata. Ayrıntı sadece loga yazılır; istemciye genel mesaj döner."""
    logger.opt(exception=exc).error("Beklenmeyen hata: {} {}", request.method, request.url.path)
    return _error_response(500, "INTERNAL_ERROR", "Sunucuda beklenmeyen bir hata oluştu.")


def register_exception_handlers(app: FastAPI) -> None:
    """Tüm global hata handler'larını uygulamaya kaydeder (`create_app` içinde bir kez çağrılır)."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
