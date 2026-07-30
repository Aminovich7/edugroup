"""Celery task: muddati o'tgan bo'laklarni overdue qiladi va bildirishnoma yuboradi."""

from datetime import date, timedelta
from decimal import Decimal

from app.notifications.models import Notification, NotificationType
from app.payments.models import Installment, InstallmentStatus, PaymentPlan, PaymentPlanStatus
from app.payments.service import flag_overdue_installments_sync
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_manager,
    create_student,
    create_teacher,
)


async def _create_plan_with_installment(session, due_date: date, manager=None):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=Decimal("400000.00"))
    group = await create_group(session, course, teacher, approved_by=manager)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    plan = PaymentPlan(
        enrollment_id=enrollment.id,
        total_amount=Decimal("400000.00"),
        installments_count=2,
        status=PaymentPlanStatus.active,
    )
    session.add(plan)
    await session.flush()

    installment = Installment(
        payment_plan_id=plan.id,
        sequence_number=1,
        amount_due=Decimal("200000.00"),
        due_date=due_date,
        status=InstallmentStatus.pending,
    )
    session.add(installment)
    await session.commit()
    await session.refresh(installment)
    return student, installment


async def test_overdue_installment_is_flagged(session, sync_session):
    yesterday = date.today() - timedelta(days=1)
    _, installment = await _create_plan_with_installment(session, due_date=yesterday)

    flagged_count = flag_overdue_installments_sync(sync_session)

    assert flagged_count == 1
    assert sync_session.get(Installment, installment.id).status == InstallmentStatus.overdue


async def test_future_installment_is_not_flagged(session, sync_session):
    tomorrow = date.today() + timedelta(days=1)
    _, installment = await _create_plan_with_installment(session, due_date=tomorrow)

    flagged_count = flag_overdue_installments_sync(sync_session)

    assert flagged_count == 0
    assert sync_session.get(Installment, installment.id).status == InstallmentStatus.pending


async def test_student_gets_overdue_notification(session, sync_session):
    yesterday = date.today() - timedelta(days=1)
    student, _ = await _create_plan_with_installment(session, due_date=yesterday)

    flag_overdue_installments_sync(sync_session)

    notifications = (
        sync_session.query(Notification)
        .filter(
            Notification.user_id == student.id,
            Notification.type == NotificationType.installment_overdue,
        )
        .all()
    )
    assert len(notifications) == 1


async def test_group_manager_also_gets_notification(session, sync_session):
    manager = await create_manager(session)
    yesterday = date.today() - timedelta(days=1)
    await _create_plan_with_installment(session, due_date=yesterday, manager=manager)

    flag_overdue_installments_sync(sync_session)

    notifications = (
        sync_session.query(Notification)
        .filter(
            Notification.user_id == manager.id,
            Notification.type == NotificationType.installment_overdue,
        )
        .all()
    )
    assert len(notifications) == 1
