"""To'lov biznes-logikasi.

Asosiy qoidalar (TZ 3.7, 3.8, 9-bo'lim):
- To'lov yoki bo'lib to'lash rejasi faqat enrollment.status == awaiting_payment
  bo'lganda yaratiladi (navbatdagi student to'lay olmaydi).
- Birinchi tasdiqlangan to'lov enrollment'ni darhol active qiladi — student
  shu zahoti videolarga kirish huquqini oladi.
- Oxirgi bo'lak to'langanda PaymentPlan avtomatik completed bo'ladi.
- To'lov RAD ETILSA enrollment statusi o'zgarmaydi — student qayta to'lay oladi.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleError,
    InvalidDataError,
    NotFoundError,
    PermissionDeniedError,
)
from app.courses import repository as courses_repository
from app.enrollments import repository as enrollments_repository
from app.enrollments.models import Enrollment, EnrollmentStatus
from app.groups import repository as groups_repository
from app.groups.models import Group
from app.notifications import service as notifications_service
from app.notifications.models import NotificationType
from app.payments import repository
from app.payments.models import (
    Installment,
    InstallmentStatus,
    Payment,
    PaymentMethod,
    PaymentPlan,
    PaymentPlanStatus,
    PaymentStatus,
)
from app.payments.schemas import PaymentCreateRequest
from app.users.models import User, UserRole, UserStatus

DAYS_BETWEEN_INSTALLMENTS = 30


# --- Bo'lib to'lash rejasi ---------------------------------------------------


async def create_payment_plan(
    session: AsyncSession, enrollment_id: uuid.UUID, installments_count: int, student: User
) -> PaymentPlan:
    """Kurs narxini 2–4 ta teng bo'lakka bo'lib, to'lov jadvalini yaratadi."""
    enrollment = await _get_own_enrollment(session, enrollment_id, student)
    _ensure_awaiting_payment(enrollment)

    if await repository.get_plan_by_enrollment(session, enrollment_id) is not None:
        raise BusinessRuleError("Bu yozilish uchun to'lov rejasi allaqachon mavjud")

    total_amount = await _get_course_price(session, enrollment.group_id)
    plan = PaymentPlan(
        enrollment_id=enrollment_id,
        total_amount=total_amount,
        installments_count=installments_count,
        status=PaymentPlanStatus.active,
    )
    session.add(plan)
    await session.flush()

    for sequence_number, amount in enumerate(
        _split_amount(total_amount, installments_count), start=1
    ):
        session.add(
            Installment(
                payment_plan_id=plan.id,
                sequence_number=sequence_number,
                amount_due=amount,
                due_date=date.today()
                + timedelta(days=DAYS_BETWEEN_INSTALLMENTS * (sequence_number - 1)),
                status=InstallmentStatus.pending,
            )
        )

    await session.commit()
    await session.refresh(plan)
    return plan


async def get_payment_plan(
    session: AsyncSession, enrollment_id: uuid.UUID, viewer: User
) -> PaymentPlan:
    """To'lov jadvalini qaytaradi — student (o'ziniki), manager yoki superadmin."""
    enrollment = await enrollments_repository.get_by_id(session, enrollment_id)
    if enrollment is None:
        raise NotFoundError("Yozilish topilmadi")

    is_owner = enrollment.student_id == viewer.id
    is_staff = viewer.role in (UserRole.manager, UserRole.superadmin)
    if not is_owner and not is_staff:
        raise PermissionDeniedError("Bu to'lov jadvali sizga tegishli emas")

    plan = await repository.get_plan_by_enrollment(session, enrollment_id)
    if plan is None:
        raise NotFoundError("To'lov rejasi topilmadi")
    return plan


# --- To'lov yaratish ---------------------------------------------------------


async def create_payment(
    session: AsyncSession, data: PaymentCreateRequest, student: User
) -> Payment:
    """Student "to'ladim" deb belgilaydi — yozuv pending holatda yaratiladi."""
    if student.status != UserStatus.approved:
        raise PermissionDeniedError("To'lov uchun profilingiz tasdiqlangan bo'lishi kerak")

    installment = None
    if data.installment_id is not None:
        installment = await repository.get_installment(session, data.installment_id)
        if installment is None:
            raise NotFoundError("To'lov bo'lagi topilmadi")
        plan = await session.get(PaymentPlan, installment.payment_plan_id)
        enrollment = await _get_own_enrollment(session, plan.enrollment_id, student)
    else:
        enrollment = await _get_own_enrollment(session, data.enrollment_id, student)
        plan = await repository.get_plan_by_enrollment(session, enrollment.id)

    if installment is not None:
        # Mavjud rejaning keyingi bo'laklari enrollment active bo'lgandan keyin ham
        # to'lanadi: birinchi bo'lak tasdiqlanishi bilan enrollment active bo'lib
        # qoladi, lekin reja hali yopilmagan.
        _ensure_installment_can_be_paid(enrollment)
        if installment.status == InstallmentStatus.paid:
            raise BusinessRuleError("Bu bo'lak allaqachon to'langan")
        _ensure_amount_matches(data.amount, installment.amount_due, "bo'lak summasi")
    else:
        # To'liq to'lov — bu yangi to'lov oqimining boshlanishi, shuning uchun
        # yozilish to'lov kutayotgan holatda bo'lishi shart.
        _ensure_awaiting_payment(enrollment)
        if plan is not None:
            raise BusinessRuleError(
                "Bu yozilishda bo'lib to'lash rejasi bor — to'lanadigan bo'lakni tanlang"
            )
        course_price = await _get_course_price(session, enrollment.group_id)
        _ensure_amount_matches(data.amount, course_price, "kurs narxi")

    payment = Payment(
        enrollment_id=enrollment.id,
        student_id=student.id,
        installment_id=installment.id if installment else None,
        amount=data.amount,
        method=PaymentMethod.manual,
        status=PaymentStatus.pending,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


# --- Tasdiqlash / rad etish --------------------------------------------------


async def confirm_payment(
    session: AsyncSession, payment_id: uuid.UUID, moderator: User
) -> Payment:
    """To'lovni tasdiqlaydi va kerak bo'lsa yozilishni faollashtiradi."""
    payment = await _get_pending_payment(session, payment_id)

    payment.status = PaymentStatus.confirmed
    payment.confirmed_by = moderator.id
    payment.confirmed_at = datetime.now(UTC)

    if payment.installment_id is not None:
        await _mark_installment_paid(session, payment.installment_id)

    enrollment = await enrollments_repository.get_by_id(session, payment.enrollment_id)
    if enrollment.status == EnrollmentStatus.awaiting_payment:
        enrollment.status = EnrollmentStatus.active
        enrollment.activated_at = datetime.now(UTC)
        await notifications_service.create_notification(
            session,
            user_id=enrollment.student_id,
            notification_type=NotificationType.enrollment_activated,
            title="Guruhga qabul qilindingiz",
            message="To'lovingiz tasdiqlandi — endi guruh darslarini ko'rishingiz mumkin.",
            related_entity_type="enrollment",
            related_entity_id=enrollment.id,
        )

    await notifications_service.create_notification(
        session,
        user_id=payment.student_id,
        notification_type=NotificationType.payment_confirmed,
        title="To'lov tasdiqlandi",
        message=f"{payment.amount} so'm miqdoridagi to'lovingiz tasdiqlandi.",
        related_entity_type="payment",
        related_entity_id=payment.id,
    )
    await session.commit()
    await session.refresh(payment)
    return payment


async def reject_payment(
    session: AsyncSession, payment_id: uuid.UUID, moderator: User, reason: str
) -> Payment:
    """To'lovni rad etadi. Yozilish statusi O'ZGARMAYDI — student qayta to'lay oladi."""
    payment = await _get_pending_payment(session, payment_id)

    payment.status = PaymentStatus.rejected
    payment.confirmed_by = moderator.id
    payment.confirmed_at = datetime.now(UTC)
    payment.note = reason

    await notifications_service.create_notification(
        session,
        user_id=payment.student_id,
        notification_type=NotificationType.payment_rejected,
        title="To'lov rad etildi",
        message=f"Sabab: {reason}. Qayta to'lov yuborishingiz mumkin.",
        related_entity_type="payment",
        related_entity_id=payment.id,
    )
    await session.commit()
    await session.refresh(payment)
    return payment


# --- Ro'yxatlar --------------------------------------------------------------


async def list_my_payments(session: AsyncSession, student: User) -> list[Payment]:
    return await repository.list_for_student(session, student.id)


async def list_pending_payments(session: AsyncSession) -> list[Payment]:
    """Manager uchun — tasdiqlanishi kerak bo'lgan to'lovlar."""
    items, _, _ = await repository.list_payments(session, status=PaymentStatus.pending)
    return items


async def list_payments(
    session: AsyncSession,
    status: PaymentStatus | None = None,
    group_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    subject: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Payment], int, Decimal]:
    return await repository.list_payments(
        session,
        status=status,
        group_id=group_id,
        teacher_id=teacher_id,
        subject=subject,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


# --- Celery task uchun sinxron variant ---------------------------------------


def flag_overdue_installments_sync(session: Session) -> int:
    """Muddati o'tgan bo'laklarni overdue qiladi va bildirishnoma yuboradi.

    Kirish avtomatik yopilmaydi (MVP soddalashtirishi) — faqat belgilanadi.
    Nechta bo'lak overdue bo'lganini qaytaradi.
    """
    overdue_query = select(Installment).where(
        Installment.status == InstallmentStatus.pending,
        Installment.due_date < date.today(),
    )
    overdue_installments = list(session.scalars(overdue_query))

    for installment in overdue_installments:
        installment.status = InstallmentStatus.overdue
        plan = session.get(PaymentPlan, installment.payment_plan_id)
        enrollment = session.get(Enrollment, plan.enrollment_id)
        group = session.get(Group, enrollment.group_id)

        message = (
            f"{installment.sequence_number}-bo'lak ({installment.amount_due} so'm) "
            f"muddati o'tib ketdi."
        )
        notifications_service.create_notification_sync(
            session,
            user_id=enrollment.student_id,
            notification_type=NotificationType.installment_overdue,
            title="To'lov muddati o'tdi",
            message=message,
            related_entity_type="installment",
            related_entity_id=installment.id,
        )
        # Guruhni tasdiqlagan manager ham xabardor qilinadi.
        if group is not None and group.approved_by is not None:
            notifications_service.create_notification_sync(
                session,
                user_id=group.approved_by,
                notification_type=NotificationType.installment_overdue,
                title="O'quvchi to'lov muddatini o'tkazib yubordi",
                message=f"'{group.name}' guruhida {message}",
                related_entity_type="installment",
                related_entity_id=installment.id,
            )

    session.commit()
    return len(overdue_installments)


# --- Ichki yordamchi funksiyalar --------------------------------------------


async def _get_own_enrollment(
    session: AsyncSession, enrollment_id: uuid.UUID, student: User
) -> Enrollment:
    enrollment = await enrollments_repository.get_by_id(session, enrollment_id)
    if enrollment is None:
        raise NotFoundError("Yozilish topilmadi")
    if enrollment.student_id != student.id:
        raise PermissionDeniedError("Bu yozilish sizga tegishli emas")
    return enrollment


def _ensure_awaiting_payment(enrollment: Enrollment) -> None:
    """To'liq to'lov va yangi reja faqat to'lov kutayotgan yozilish uchun mumkin."""
    if enrollment.status != EnrollmentStatus.awaiting_payment:
        raise BusinessRuleError(
            "To'lov faqat 'to'lov kutilmoqda' holatidagi yozilish uchun mumkin "
            f"(joriy holat: {enrollment.status.value})"
        )


def _ensure_installment_can_be_paid(enrollment: Enrollment) -> None:
    """Bo'lak to'lovi awaiting_payment va active holatlarida ruxsat etiladi.

    Yakunlangan (cancelled/expired) yoki navbatdagi yozilish uchun to'lash mantiqsiz.
    """
    allowed = (EnrollmentStatus.awaiting_payment, EnrollmentStatus.active)
    if enrollment.status not in allowed:
        raise BusinessRuleError(
            "Bu yozilish uchun bo'lak to'lovi mumkin emas "
            f"(joriy holat: {enrollment.status.value})"
        )


def _ensure_amount_matches(amount: Decimal, expected: Decimal, label: str) -> None:
    if Decimal(amount) != Decimal(expected):
        raise InvalidDataError(f"To'lov summasi {label}ga teng bo'lishi kerak: {expected}")


async def _get_pending_payment(session: AsyncSession, payment_id: uuid.UUID) -> Payment:
    payment = await repository.get_payment(session, payment_id)
    if payment is None:
        raise NotFoundError("To'lov topilmadi")
    if payment.status != PaymentStatus.pending:
        raise BusinessRuleError("Bu to'lov allaqachon ko'rib chiqilgan")
    return payment


async def _get_course_price(session: AsyncSession, group_id: uuid.UUID) -> Decimal:
    group = await groups_repository.get_by_id(session, group_id)
    if group is None:
        raise NotFoundError("Guruh topilmadi")
    course = await courses_repository.get_by_id(session, group.course_id)
    if course is None:
        raise NotFoundError("Kurs topilmadi")
    return course.price


async def _mark_installment_paid(session: AsyncSession, installment_id: uuid.UUID) -> None:
    """Bo'lakni to'langan deb belgilaydi; oxirgisi bo'lsa rejani yakunlaydi."""
    installment = await repository.get_installment(session, installment_id)
    installment.status = InstallmentStatus.paid
    await session.flush()

    plan = await session.get(PaymentPlan, installment.payment_plan_id)
    await session.refresh(plan)
    all_paid = all(item.status == InstallmentStatus.paid for item in plan.installments)
    if all_paid:
        plan.status = PaymentPlanStatus.completed


def _split_amount(total: Decimal, parts: int) -> list[Decimal]:
    """Summani teng bo'laklarga bo'ladi; qoldiq oxirgi bo'lakka qo'shiladi.

    Bo'lak butun so'mga yaxlitlanadi (pastga), qoldiq esa oxirgi bo'lakka
    qo'shiladi. Masalan 500 000 ni 3 ga bo'lsak: 166 666 + 166 666 + 166 668.
    Shu sababli bo'laklar yig'indisi har doim aniq `total`ga teng bo'ladi va
    student tiyinli summa to'lashiga to'g'ri kelmaydi.
    """
    base_amount = (Decimal(total) / parts).quantize(Decimal("1"), rounding=ROUND_DOWN)
    amounts = [base_amount] * (parts - 1)
    amounts.append(Decimal(total) - base_amount * (parts - 1))
    return amounts
