"""Superadmin sahifalari: umumiy statistika, hisobotlar, audit log, manager boshqaruvi."""

import uuid
from datetime import date

from fastapi import APIRouter, Form, Request

from app.audit import service as audit_service
from app.audit.models import AuditEntityType
from app.core.exceptions import AppError
from app.courses import service as courses_service
from app.groups import service as groups_service
from app.lessons import service as lessons_service
from app.payments import service as payments_service
from app.reports import service as reports_service
from app.users import service as users_service
from app.users.models import UserRole
from app.users.schemas import ManagerCreateRequest
from app.web.dependencies import CurrentWebUser, WebSession
from app.web.form_fields import FormText, QueryDate, QueryUuid, query_enum
from app.web.helpers import error_message, redirect_to, render

router = APIRouter()

SUPERADMIN_DASHBOARD_URL = "/dashboard/superadmin"


@router.get("/dashboard/superadmin")
async def superadmin_dashboard(
    request: Request,
    session: WebSession,
    current_user: CurrentWebUser,
    date_from: QueryDate = None,
    date_to: QueryDate = None,
    group_id: QueryUuid = None,
    teacher_id: QueryUuid = None,
    entity_type: query_enum(AuditEntityType) = None,
):
    """Statistika, daromad hisoboti, to'lovlar, audit log va manager boshqaruvi."""
    payments, payments_count, payments_total = await payments_service.list_payments(
        session,
        group_id=group_id,
        teacher_id=teacher_id,
        date_from=date_from,
        date_to=date_to,
    )
    audit_logs, _ = await audit_service.list_logs(session, entity_type=entity_type)

    return await render(
        request,
        "dashboard/superadmin.html",
        current_user=current_user,
        session=session,
        overview=await reports_service.get_overview(session),
        revenue=await reports_service.get_revenue_report(
            session,
            date_from=date_from,
            date_to=date_to,
            group_id=group_id,
            teacher_id=teacher_id,
        ),
        payments=payments,
        payments_count=payments_count,
        payments_total=payments_total,
        audit_logs=audit_logs,
        managers=await users_service.list_managers(session),
        teachers=await users_service.list_users(session, role=UserRole.teacher),
        students=await users_service.list_users(session, role=UserRole.student),
        filters={
            "date_from": date_from or "",
            "date_to": date_to or "",
            "group_id": group_id or "",
            "teacher_id": teacher_id or "",
            "entity_type": entity_type.value if entity_type else "",
        },
    )


# --- Hisobot sahifalari ------------------------------------------------------


@router.get("/reports/groups/{group_id}")
async def group_report_page(
    group_id: uuid.UUID, request: Request, session: WebSession, current_user: CurrentWebUser
):
    """Guruh hisoboti — teacher (o'ziniki), manager va superadmin uchun."""
    report = await reports_service.get_group_report(session, group_id, current_user)
    return await render(
        request,
        "report_group.html",
        current_user=current_user,
        session=session,
        report=report,
    )


@router.get("/reports/teachers/{teacher_id}")
async def teacher_report_page(
    teacher_id: uuid.UUID, request: Request, session: WebSession, current_user: CurrentWebUser
):
    """Teacher hisoboti — manager va superadmin uchun."""
    if current_user.role not in (UserRole.manager, UserRole.superadmin):
        return redirect_to("/", error="Bu hisobotni ko'rish huquqingiz yo'q")

    report = await reports_service.get_teacher_report(session, teacher_id)
    return await render(
        request,
        "report_teacher.html",
        current_user=current_user,
        session=session,
        report=report,
    )


# --- Manager boshqaruvi (TZ 6.11) -------------------------------------------


@router.get("/web/superadmin/managers")
async def managers_page(
    request: Request, session: WebSession, current_user: CurrentWebUser
):
    if current_user.role != UserRole.superadmin:
        return redirect_to("/", error="Ruxsat yo'q")

    return await render(
        request,
        "managers.html",
        current_user=current_user,
        session=session,
        managers=await users_service.list_managers(session),
    )


@router.post("/web/superadmin/managers")
async def create_manager_submit(
    session: WebSession,
    current_user: CurrentWebUser,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: FormText = None,
):
    if current_user.role != UserRole.superadmin:
        return redirect_to("/", error="Ruxsat yo'q")
    try:
        await users_service.create_manager(
            session,
            ManagerCreateRequest(
                full_name=full_name, email=email, password=password, phone=phone
            ),
        )
    except (AppError, ValueError) as error:
        return redirect_to("/web/superadmin/managers", error=error_message(error))
    return redirect_to("/web/superadmin/managers", message="Manager akkaunti yaratildi")


@router.post("/web/superadmin/users/{user_id}/block")
async def block_user_submit(
    user_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    next_url: str = Form(default=SUPERADMIN_DASHBOARD_URL),
):
    if current_user.role != UserRole.superadmin:
        return redirect_to("/", error="Ruxsat yo'q")
    try:
        await users_service.block_user(session, user_id, current_user)
    except AppError as error:
        return redirect_to(next_url, error=error_message(error))
    return redirect_to(next_url, message="Foydalanuvchi bloklandi")


@router.post("/web/superadmin/users/{user_id}/unblock")
async def unblock_user_submit(
    user_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    next_url: str = Form(default=SUPERADMIN_DASHBOARD_URL),
):
    if current_user.role != UserRole.superadmin:
        return redirect_to("/", error="Ruxsat yo'q")
    try:
        await users_service.unblock_user(session, user_id)
    except AppError as error:
        return redirect_to(next_url, error=error_message(error))
    return redirect_to(next_url, message="Foydalanuvchi blokdan chiqarildi")


# --- Soft-delete qilingan yozuvlarni tiklash --------------------------------


@router.post("/web/courses/{course_id}/restore")
async def restore_course_submit(
    course_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    return await _restore(
        lambda: courses_service.restore_course(session, course_id, current_user), current_user
    )


@router.post("/web/groups/{group_id}/restore")
async def restore_group_submit(
    group_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    return await _restore(
        lambda: groups_service.restore_group(session, group_id, current_user), current_user
    )


@router.post("/web/lessons/{lesson_id}/restore")
async def restore_lesson_submit(
    lesson_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    return await _restore(
        lambda: lessons_service.restore_lesson(session, lesson_id, current_user), current_user
    )


async def _restore(restore_action, current_user):
    """Uchala restore formasi uchun umumiy: ruxsatni tekshiradi va natijani xabar qiladi."""
    if current_user.role != UserRole.superadmin:
        return redirect_to("/", error="Ruxsat yo'q")
    try:
        await restore_action()
    except AppError as error:
        return redirect_to(SUPERADMIN_DASHBOARD_URL, error=error_message(error))
    return redirect_to(SUPERADMIN_DASHBOARD_URL, message="Yozuv tiklandi")
