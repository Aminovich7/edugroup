"""Student sahifasi va uning forma-handlerlari."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Form, Request

from app.core.exceptions import AppError
from app.courses import repository as courses_repository
from app.enrollments import service as enrollments_service
from app.groups import repository as groups_repository
from app.lessons import service as lessons_service
from app.notifications import service as notifications_service
from app.payments import repository as payments_repository
from app.payments import service as payments_service
from app.payments.schemas import PaymentCreateRequest
from app.web.dependencies import CurrentWebUser, WebSession
from app.web.form_fields import FormText, FormUuid
from app.web.helpers import error_message, redirect_to, render

router = APIRouter()

STUDENT_DASHBOARD_URL = "/dashboard/student"


@router.get("/dashboard/student")
async def student_dashboard(
    request: Request, session: WebSession, current_user: CurrentWebUser
):
    """Yozilishlarim, to'lov jadvalim, darslarim va bildirishnomalarim."""
    enrollments = await enrollments_service.list_my_enrollments(session, current_user)

    enrollment_cards = []
    for enrollment in enrollments:
        group = await groups_repository.get_by_id(session, enrollment.group_id)
        course = await courses_repository.get_by_id(session, group.course_id) if group else None
        plan = await payments_repository.get_plan_by_enrollment(session, enrollment.id)
        enrollment_cards.append(
            {"enrollment": enrollment, "group": group, "course": course, "plan": plan}
        )

    progress_records = await lessons_service.list_progress_for_student(session, current_user)

    return await render(
        request,
        "dashboard/student.html",
        current_user=current_user,
        session=session,
        enrollment_cards=enrollment_cards,
        payments=await payments_service.list_my_payments(session, current_user),
        watched_count=sum(1 for record in progress_records if record.watched),
        notifications=await notifications_service.list_my_notifications(session, current_user),
    )


@router.post("/web/enrollments")
async def enroll_submit(
    session: WebSession, current_user: CurrentWebUser, group_id: uuid.UUID = Form(...)
):
    """Guruhga yozilish. Guruh to'la bo'lsa student navbatga qo'yiladi."""
    try:
        enrollment = await enrollments_service.request_enrollment(
            session, group_id, current_user
        )
    except AppError as error:
        return redirect_to(f"/groups/{group_id}", error=error_message(error))

    if enrollment.waitlist_position is not None:
        message = f"Guruh to'la — siz navbatda {enrollment.waitlist_position}-o'rindasiz"
    else:
        message = "Yozildingiz. Endi to'lovni amalga oshiring."
    return redirect_to(f"/groups/{group_id}", message=message)


@router.post("/web/enrollments/{enrollment_id}/cancel")
async def cancel_enrollment_submit(
    enrollment_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    reason: FormText = None,
    next_url: str = Form(default=STUDENT_DASHBOARD_URL),
):
    """Yozilishni bekor qiladi. Manager/superadmin uchun sabab majburiy."""
    try:
        await enrollments_service.cancel_enrollment(
            session, enrollment_id, current_user, reason=reason
        )
    except AppError as error:
        return redirect_to(next_url, error=error_message(error))
    return redirect_to(next_url, message="Yozilish bekor qilindi")


@router.post("/web/enrollments/{enrollment_id}/payment-plan")
async def create_payment_plan_submit(
    enrollment_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    installments_count: int = Form(...),
):
    try:
        await payments_service.create_payment_plan(
            session, enrollment_id, installments_count, current_user
        )
    except (AppError, ValueError) as error:
        return redirect_to(STUDENT_DASHBOARD_URL, error=error_message(error))
    return redirect_to(STUDENT_DASHBOARD_URL, message="Bo'lib to'lash jadvali yaratildi")


@router.post("/web/payments")
async def create_payment_submit(
    session: WebSession,
    current_user: CurrentWebUser,
    amount: Decimal = Form(...),
    enrollment_id: FormUuid = None,
    installment_id: FormUuid = None,
):
    """To'liq to'lov yoki navbatdagi bo'lak uchun to'lov yozuvi yaratadi."""
    try:
        await payments_service.create_payment(
            session,
            PaymentCreateRequest(
                enrollment_id=enrollment_id, installment_id=installment_id, amount=amount
            ),
            current_user,
        )
    except (AppError, ValueError) as error:
        return redirect_to(STUDENT_DASHBOARD_URL, error=error_message(error))
    return redirect_to(
        STUDENT_DASHBOARD_URL, message="To'lov yuborildi — manager tasdiqlashini kuting"
    )


@router.post("/web/lessons/{lesson_id}/progress")
async def mark_lesson_watched_submit(
    lesson_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    next_url: str = Form(default=STUDENT_DASHBOARD_URL),
):
    try:
        await lessons_service.mark_watched(session, lesson_id, current_user)
    except AppError as error:
        return redirect_to(next_url, error=error_message(error))
    return redirect_to(next_url, message="Dars ko'rildi deb belgilandi")
