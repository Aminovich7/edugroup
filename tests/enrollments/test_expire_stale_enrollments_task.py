"""Celery task: muddati o'tgan yozilishlar expired bo'ladi va navbat ko'tariladi.

Task mantiqi oddiy funksiya bo'lgani uchun broker ko'tarilmaydi — funksiya
sinxron sessiya bilan to'g'ridan-to'g'ri chaqiriladi.
"""

from datetime import UTC, datetime, timedelta

from app.enrollments.models import Enrollment, EnrollmentStatus
from app.enrollments.service import expire_stale_enrollments_sync
from app.notifications.models import Notification, NotificationType
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_student,
    create_teacher,
)

EXPIRY_HOURS = 72


async def test_stale_enrollment_becomes_expired(session, sync_session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)

    old_request_time = datetime.now(UTC) - timedelta(hours=EXPIRY_HOURS + 1)
    enrollment = await create_enrollment(
        session, student, group, requested_at=old_request_time
    )

    expired_count = expire_stale_enrollments_sync(sync_session, EXPIRY_HOURS)

    assert expired_count == 1
    assert sync_session.get(Enrollment, enrollment.id).status == EnrollmentStatus.expired


async def test_fresh_enrollment_is_not_touched(session, sync_session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    expired_count = expire_stale_enrollments_sync(sync_session, EXPIRY_HOURS)

    assert expired_count == 0
    assert (
        sync_session.get(Enrollment, enrollment.id).status
        == EnrollmentStatus.awaiting_payment
    )


async def test_expiry_promotes_next_waitlisted_student(session, sync_session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=1)

    stale_student = await create_student(session)
    stale_enrollment = await create_enrollment(
        session,
        stale_student,
        group,
        requested_at=datetime.now(UTC) - timedelta(hours=EXPIRY_HOURS + 1),
    )

    waiting_student = await create_student(session)
    waiting_enrollment = await create_enrollment(
        session, waiting_student, group, status=EnrollmentStatus.waitlisted, waitlist_position=1
    )

    expire_stale_enrollments_sync(sync_session, EXPIRY_HOURS)

    assert sync_session.get(Enrollment, stale_enrollment.id).status == EnrollmentStatus.expired
    promoted = sync_session.get(Enrollment, waiting_enrollment.id)
    assert promoted.status == EnrollmentStatus.awaiting_payment
    assert promoted.waitlist_position is None


async def test_expiry_creates_notification(session, sync_session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)
    await create_enrollment(
        session,
        student,
        group,
        requested_at=datetime.now(UTC) - timedelta(hours=EXPIRY_HOURS + 1),
    )

    expire_stale_enrollments_sync(sync_session, EXPIRY_HOURS)

    notifications = (
        sync_session.query(Notification)
        .filter(Notification.user_id == student.id)
        .all()
    )
    types = [notification.type for notification in notifications]
    assert NotificationType.enrollment_expired in types
