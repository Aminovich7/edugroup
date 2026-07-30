"""Har bir muhim hodisa uchun bildirishnoma yaratilishi tekshiriladi."""

from decimal import Decimal

from sqlalchemy import select

from app.enrollments.models import EnrollmentStatus
from app.groups.models import GroupStatus
from app.notifications.models import Notification, NotificationType
from app.users.models import UserStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_lesson,
    create_manager,
    create_student,
    create_superadmin,
    create_teacher,
)

COURSE_PRICE = Decimal("500000.00")


async def _notification_types_for(session, user_id) -> list[NotificationType]:
    rows = await session.scalars(
        select(Notification).where(Notification.user_id == user_id)
    )
    return [row.type for row in rows]


async def test_approve_creates_notification(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session, status=UserStatus.pending)

    await client.post(
        f"/api/manager/users/{teacher.id}/approve", headers=auth_headers(manager)
    )

    assert NotificationType.profile_approved in await _notification_types_for(
        session, teacher.id
    )


async def test_reject_creates_notification(client, session):
    manager = await create_manager(session)
    student = await create_student(session, status=UserStatus.pending)

    await client.post(
        f"/api/manager/users/{student.id}/reject",
        json={"reason": "Ma'lumot yetarli emas"},
        headers=auth_headers(manager),
    )

    assert NotificationType.profile_rejected in await _notification_types_for(
        session, student.id
    )


async def test_group_assignment_notifies_teacher(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.draft)

    await client.post(
        f"/api/manager/groups/{group.id}/assign-teacher", json={}, headers=auth_headers(manager)
    )

    assert NotificationType.group_assigned in await _notification_types_for(
        session, teacher.id
    )


async def test_payment_confirm_creates_two_notifications(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )
    await client.post(
        f"/api/payments/{payment.json()['id']}/confirm", headers=auth_headers(manager)
    )

    types = await _notification_types_for(session, student.id)
    assert NotificationType.payment_confirmed in types
    assert NotificationType.enrollment_activated in types


async def test_payment_reject_creates_notification(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )
    await client.post(
        f"/api/payments/{payment.json()['id']}/reject",
        json={"reason": "Chek yo'q"},
        headers=auth_headers(manager),
    )

    assert NotificationType.payment_rejected in await _notification_types_for(
        session, student.id
    )


async def test_waitlist_promotion_creates_notification(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=1)

    seated_student = await create_student(session)
    seated_enrollment = await create_enrollment(
        session, seated_student, group, status=EnrollmentStatus.active
    )
    waiting_student = await create_student(session)
    await create_enrollment(
        session, waiting_student, group, status=EnrollmentStatus.waitlisted, waitlist_position=1
    )

    await client.request(
        "DELETE",
        f"/api/enrollments/{seated_enrollment.id}",
        headers=auth_headers(seated_student),
    )

    assert NotificationType.waitlist_promoted in await _notification_types_for(
        session, waiting_student.id
    )


async def test_new_lesson_notifies_active_students(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    active_student = await create_student(session)
    awaiting_student = await create_student(session)
    await create_enrollment(session, active_student, group, status=EnrollmentStatus.active)
    await create_enrollment(
        session, awaiting_student, group, status=EnrollmentStatus.awaiting_payment
    )

    await client.post(
        f"/api/groups/{group.id}/lessons",
        json={
            "title": "Yangi dars",
            "kinescope_video_id": "xyz789",
            "kinescope_url": "https://kinescope.io/xyz789",
            "duration_seconds": 400,
            "order_index": 1,
        },
        headers=auth_headers(teacher),
    )

    assert NotificationType.lesson_added in await _notification_types_for(
        session, active_student.id
    )
    # To'lov qilmagan student darsdan xabar olmaydi.
    assert NotificationType.lesson_added not in await _notification_types_for(
        session, awaiting_student.id
    )


async def test_block_and_unblock_create_notifications(client, session):
    superadmin = await create_superadmin(session)
    student = await create_student(session)

    await client.post(
        f"/api/superadmin/users/{student.id}/block", headers=auth_headers(superadmin)
    )
    await client.post(
        f"/api/superadmin/users/{student.id}/unblock", headers=auth_headers(superadmin)
    )

    types = await _notification_types_for(session, student.id)
    assert NotificationType.account_blocked in types
    assert NotificationType.account_unblocked in types


async def test_user_reads_and_marks_notifications(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session, status=UserStatus.pending)
    await client.post(
        f"/api/manager/users/{teacher.id}/approve", headers=auth_headers(manager)
    )

    listing = await client.get("/api/notifications", headers=auth_headers(teacher))
    assert listing.status_code == 200
    notification_id = listing.json()[0]["id"]

    mark = await client.post(
        f"/api/notifications/{notification_id}/read", headers=auth_headers(teacher)
    )
    assert mark.status_code == 200
    assert mark.json()["is_read"] is True


async def test_user_cannot_read_someone_elses_notification(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session, status=UserStatus.pending)
    stranger = await create_student(session)
    await client.post(
        f"/api/manager/users/{teacher.id}/approve", headers=auth_headers(manager)
    )

    listing = await client.get("/api/notifications", headers=auth_headers(teacher))
    notification_id = listing.json()[0]["id"]

    response = await client.post(
        f"/api/notifications/{notification_id}/read", headers=auth_headers(stranger)
    )

    assert response.status_code == 403


async def test_mark_all_read(client, session):
    superadmin = await create_superadmin(session)
    student = await create_student(session)
    await client.post(
        f"/api/superadmin/users/{student.id}/block", headers=auth_headers(superadmin)
    )
    await client.post(
        f"/api/superadmin/users/{student.id}/unblock", headers=auth_headers(superadmin)
    )

    response = await client.post(
        "/api/notifications/read-all", headers=auth_headers(student)
    )

    assert response.status_code == 200
    assert response.json()["updated_count"] == 2

    unread = await client.get(
        "/api/notifications?is_read=false", headers=auth_headers(student)
    )
    assert unread.json() == []
