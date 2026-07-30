"""Barcha rollar uchun umumiy sahifalar: dashboard yo'naltirish, profil, bildirishnomalar."""

import uuid

from fastapi import APIRouter, Form, Request

from app.core.exceptions import AppError
from app.notifications import service as notifications_service
from app.users import service as users_service
from app.users.schemas import ProfileUpdateRequest
from app.web.dependencies import CurrentWebUser, WebSession
from app.web.form_fields import FormDate, FormInteger, FormText
from app.web.helpers import dashboard_url_for, error_message, redirect_to, render

router = APIRouter()


@router.get("/dashboard")
async def dashboard_redirect(current_user: CurrentWebUser):
    """Foydalanuvchini o'z roliga mos boshqaruv paneliga yo'naltiradi."""
    return redirect_to(dashboard_url_for(current_user))


@router.get("/profile")
async def profile_page(request: Request, session: WebSession, current_user: CurrentWebUser):
    user = await users_service.get_profile(session, current_user)
    return await render(
        request, "profile.html", current_user=current_user, session=session, user=user
    )


@router.post("/web/profile/edit")
async def profile_edit_submit(
    session: WebSession,
    current_user: CurrentWebUser,
    full_name: FormText = None,
    phone: FormText = None,
    bio: FormText = None,
    specialization: FormText = None,
    experience_years: FormInteger = None,
    birth_date: FormDate = None,
):
    try:
        await users_service.update_profile(
            session,
            current_user,
            ProfileUpdateRequest(
                full_name=full_name,
                phone=phone,
                bio=bio,
                specialization=specialization,
                experience_years=experience_years,
                birth_date=birth_date,
            ),
        )
    except (AppError, ValueError) as error:
        return redirect_to("/profile", error=error_message(error))
    return redirect_to("/profile", message="Profil yangilandi")


@router.get("/notifications")
async def notifications_page(
    request: Request, session: WebSession, current_user: CurrentWebUser
):
    notifications = await notifications_service.list_my_notifications(session, current_user)
    return await render(
        request,
        "notifications.html",
        current_user=current_user,
        session=session,
        notifications=notifications,
    )


@router.post("/web/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    try:
        await notifications_service.mark_as_read(session, notification_id, current_user)
    except AppError as error:
        return redirect_to("/notifications", error=error_message(error))
    return redirect_to("/notifications")


@router.post("/web/notifications/read-all")
async def mark_all_notifications_read(session: WebSession, current_user: CurrentWebUser):
    await notifications_service.mark_all_as_read(session, current_user)
    return redirect_to("/notifications", message="Barchasi o'qilgan deb belgilandi")
