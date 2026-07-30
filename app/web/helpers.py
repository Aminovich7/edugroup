"""Veb-sahifalar uchun kichik yordamchilar: redirect, flash-xabar va shablon konteksti.

Flash-xabarlar query-parametr orqali uzatiladi (`?message=` / `?error=`) —
bu sessiya saqlashni talab qilmaydigan eng sodda usul va Post/Redirect/Get
patternига to'liq mos keladi.
"""

from urllib.parse import urlencode

from fastapi import Request, status
from fastapi.responses import RedirectResponse

from app.notifications import service as notifications_service
from app.templating import templates
from app.users.models import User

SEE_OTHER = status.HTTP_303_SEE_OTHER


def redirect_to(url: str, message: str | None = None, error: str | None = None):
    """Post/Redirect/Get: forma yuborilgandan keyin GET sahifaga yo'naltiradi."""
    flash = {key: value for key, value in (("message", message), ("error", error)) if value}
    target = f"{url}?{urlencode(flash)}" if flash else url
    return RedirectResponse(target, status_code=SEE_OTHER)


async def render(
    request: Request,
    template_name: str,
    current_user: User | None = None,
    session=None,
    **context,
):
    """Sahifani render qiladi va har bir shablonga umumiy kontekstni qo'shadi."""
    unread_count = 0
    if current_user is not None and session is not None:
        unread_count = await notifications_service.count_unread(session, current_user)

    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "current_user": current_user,
            "unread_count": unread_count,
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
            **context,
        },
    )


def dashboard_url_for(user: User) -> str:
    """Har bir rol o'z boshqaruv panelini ko'radi."""
    return f"/dashboard/{user.role.value}"


def error_message(error: Exception) -> str:
    """Service xatosidan foydalanuvchiga ko'rsatiladigan matnni oladi."""
    detail = getattr(error, "detail", None)
    return str(detail) if detail else str(error)
