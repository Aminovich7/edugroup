"""Ilova bo'ylab ishlatiladigan xato turlari va ularning handler'lari.

Service qatlami shu xatolarni ko'taradi. JSON API ularni JSON javobga,
web qatlami esa flash-xabarga aylantiradi (app/web/pages/*.py).
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded

API_PREFIX = "/api"


class AppError(HTTPException):
    """Barcha biznes-xatolarning umumiy asosi."""


class NotFoundError(AppError):
    def __init__(self, detail: str = "Topilmadi") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class PermissionDeniedError(AppError):
    def __init__(self, detail: str = "Ruxsat yo'q") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotAuthenticatedError(AppError):
    def __init__(self, detail: str = "Avtorizatsiya talab qilinadi") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class BusinessRuleError(AppError):
    """Biznes qoidasi buzilgan — masalan to'la guruh yoki noto'g'ri status."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidDataError(AppError):
    """Ma'lumot formati to'g'ri, lekin qiymati qoidaga mos emas (422)."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def register_exception_handlers(app: FastAPI, templates: Jinja2Templates) -> None:
    """Xato javoblarini so'rov turiga qarab JSON yoki HTML qilib qaytaradi."""

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, error: HTTPException) -> Response:
        if _is_api_request(request):
            return JSONResponse({"detail": error.detail}, status_code=error.status_code)
        if error.status_code == status.HTTP_401_UNAUTHORIZED:
            return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        return _render_error_page(request, templates, error.status_code, str(error.detail))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> Response:
        problems = _describe_validation_problems(error)
        if _is_api_request(request):
            return JSONResponse(
                {"detail": problems}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        message = "; ".join(problem["message"] for problem in problems)
        return _render_error_page(
            request, templates, status.HTTP_422_UNPROCESSABLE_ENTITY, message
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, error: RateLimitExceeded) -> Response:
        # Xavfsizlik uchun qolgan urinishlar soni oshkor qilinmaydi (TZ 14.5).
        message = "Juda ko'p urinish. Iltimos, biroz kuting."
        if _is_api_request(request):
            return JSONResponse(
                {"detail": message}, status_code=status.HTTP_429_TOO_MANY_REQUESTS
            )
        return _render_error_page(
            request, templates, status.HTTP_429_TOO_MANY_REQUESTS, message
        )


def _is_api_request(request: Request) -> bool:
    return request.url.path.startswith(API_PREFIX)


def _describe_validation_problems(error: RequestValidationError) -> list[dict[str, str]]:
    """Pydantic xatolarini sodda, JSON'ga yoziladigan ko'rinishga keltiradi.

    Xom `error.errors()` ichida istisno obyektlari bo'lishi mumkin — ular
    JSON'ga serializatsiya qilinmaydi, shuning uchun faqat maydon va matn olinadi.
    """
    return [
        {
            "field": ".".join(str(part) for part in item["loc"]),
            "message": item["msg"],
        }
        for item in error.errors()
    ]


def _render_error_page(
    request: Request, templates: Jinja2Templates, status_code: int, message: str
) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"status_code": status_code, "message": message},
        status_code=status_code,
    )
