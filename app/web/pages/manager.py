"""Manager sahifasi: moderatsiya navbati, guruh biriktirish, to'lov tasdiqlash."""

import uuid

from fastapi import APIRouter, Form, Request

from app.core.exceptions import AppError
from app.courses import repository as courses_repository
from app.enrollments import service as enrollments_service
from app.enrollments.models import EnrollmentStatus
from app.groups import repository as groups_repository
from app.groups import service as groups_service
from app.notifications import service as notifications_service
from app.payments import service as payments_service
from app.users import service as users_service
from app.users.models import UserRole, UserStatus
from app.web.dependencies import CurrentWebUser, WebSession
from app.web.form_fields import FormUuid, QueryUuid, query_enum
from app.web.helpers import error_message, redirect_to, render

router = APIRouter()

MANAGER_DASHBOARD_URL = "/dashboard/manager"


@router.get("/dashboard/manager")
async def manager_dashboard(
    request: Request,
    session: WebSession,
    current_user: CurrentWebUser,
    enrollment_status: query_enum(EnrollmentStatus) = None,
    enrollment_group_id: QueryUuid = None,
):
    """Tasdiqlanishi kerak bo'lgan profillar, to'lovlar, guruhlar va yozilishlar."""
    groups = await groups_service.list_groups(session)
    group_cards = [
        {
            "group": group,
            "course": await courses_repository.get_by_id(session, group.course_id),
            "waitlist": await groups_service.get_waitlist(session, group.id, current_user),
        }
        for group in groups
    ]

    enrollments = await enrollments_service.list_all_enrollments(
        session, group_id=enrollment_group_id, status=enrollment_status
    )
    enrollment_rows = [
        {
            "enrollment": enrollment,
            "group": await groups_repository.get_by_id(session, enrollment.group_id),
        }
        for enrollment in enrollments
    ]

    return await render(
        request,
        "dashboard/manager.html",
        current_user=current_user,
        session=session,
        pending_users=await users_service.list_users(session, status=UserStatus.pending),
        pending_payments=await payments_service.list_pending_payments(session),
        approved_teachers=await users_service.list_users(
            session, role=UserRole.teacher, status=UserStatus.approved
        ),
        group_cards=group_cards,
        enrollment_rows=enrollment_rows,
        enrollment_filters={
            "status": enrollment_status.value if enrollment_status else "",
            "group_id": enrollment_group_id or "",
        },
        notifications=await notifications_service.list_my_notifications(session, current_user),
    )


@router.post("/web/manager/users/{user_id}/approve")
async def approve_user_submit(
    user_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    try:
        await users_service.approve_user(session, user_id, current_user)
    except AppError as error:
        return redirect_to(MANAGER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(MANAGER_DASHBOARD_URL, message="Profil tasdiqlandi")


@router.post("/web/manager/users/{user_id}/reject")
async def reject_user_submit(
    user_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    reason: str = Form(...),
):
    try:
        await users_service.reject_user(session, user_id, current_user, reason)
    except AppError as error:
        return redirect_to(MANAGER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(MANAGER_DASHBOARD_URL, message="Profil rad etildi")


@router.post("/web/manager/groups/{group_id}/assign-teacher")
async def assign_teacher_submit(
    group_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    teacher_id: FormUuid = None,
):
    """Guruhni tasdiqlaydi (draft -> active) va kerak bo'lsa teacher'ni almashtiradi."""
    try:
        await groups_service.assign_teacher(
            session, group_id, current_user, teacher_id=teacher_id
        )
    except AppError as error:
        return redirect_to(MANAGER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(MANAGER_DASHBOARD_URL, message="Guruh tasdiqlandi va faollashtirildi")


@router.post("/web/manager/payments/{payment_id}/confirm")
async def confirm_payment_submit(
    payment_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    try:
        await payments_service.confirm_payment(session, payment_id, current_user)
    except AppError as error:
        return redirect_to(MANAGER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(MANAGER_DASHBOARD_URL, message="To'lov tasdiqlandi")


@router.post("/web/manager/payments/{payment_id}/reject")
async def reject_payment_submit(
    payment_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    reason: str = Form(...),
):
    try:
        await payments_service.reject_payment(session, payment_id, current_user, reason)
    except AppError as error:
        return redirect_to(MANAGER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(MANAGER_DASHBOARD_URL, message="To'lov rad etildi")
