"""Veb-formalar: har bir POST forma-handleri Post/Redirect/Get bo'yicha ishlaydi."""

from decimal import Decimal

from sqlalchemy import select

from app.courses.models import Course, CourseStatus
from app.enrollments.models import EnrollmentStatus
from app.groups.models import Group, GroupStatus
from app.lessons.models import Lesson
from app.notifications.models import Notification
from app.payments.models import Payment, PaymentPlan, PaymentStatus
from app.users.models import UserStatus
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
LESSON_FORM = {
    "title": "Web dars",
    "kinescope_video_id": "web123",
    "kinescope_url": "https://kinescope.io/web123",
    "duration_seconds": "400",
    "order_index": "1",
}


def _redirects_with_message(response) -> bool:
    return response.status_code == 303 and "message=" in response.headers["location"]


# --- Teacher formalari -------------------------------------------------------


async def test_teacher_creates_course_group_and_lesson(client, session, login_as):
    teacher = await create_teacher(session)
    login_as(teacher)

    course_response = await client.post(
        "/web/courses",
        data={"title": "Web kursi", "subject": "Fizika", "price": "300000"},
        follow_redirects=False,
    )
    assert _redirects_with_message(course_response)

    course = await session.scalar(select(Course))
    group_response = await client.post(
        "/web/groups",
        data={
            "course_id": str(course.id),
            "name": "Web guruh",
            "capacity": "10",
            "schedule": "Dush 18:00",
        },
        follow_redirects=False,
    )
    assert _redirects_with_message(group_response)

    group = await session.scalar(select(Group))
    lesson_response = await client.post(
        "/web/lessons",
        data={**LESSON_FORM, "group_id": str(group.id)},
        follow_redirects=False,
    )
    assert _redirects_with_message(lesson_response)

    lesson = await session.scalar(select(Lesson))
    assert lesson.title == "Web dars"


async def test_teacher_edit_pages_render_and_save(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    lesson = await create_lesson(session, group)
    login_as(teacher)

    for url in [
        f"/web/courses/{course.id}/edit",
        f"/web/groups/{group.id}/edit",
        f"/web/lessons/{lesson.id}/edit",
    ]:
        assert (await client.get(url)).status_code == 200, url

    course_edit = await client.post(
        f"/web/courses/{course.id}/edit",
        data={
            "title": "Tahrirlangan kurs",
            "subject": "Fizika",
            "price": "700000",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert _redirects_with_message(course_edit)

    group_edit = await client.post(
        f"/web/groups/{group.id}/edit",
        data={"name": "Tahrirlangan guruh", "capacity": "12", "schedule": "Sesh 10:00"},
        follow_redirects=False,
    )
    assert _redirects_with_message(group_edit)

    lesson_edit = await client.post(
        f"/web/lessons/{lesson.id}/edit",
        data={**LESSON_FORM, "title": "Tahrirlangan dars"},
        follow_redirects=False,
    )
    assert _redirects_with_message(lesson_edit)

    await session.refresh(course)
    await session.refresh(group)
    await session.refresh(lesson)
    assert course.title == "Tahrirlangan kurs"
    assert group.name == "Tahrirlangan guruh"
    assert lesson.title == "Tahrirlangan dars"


async def test_teacher_deletes_lesson_group_and_course(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, status=CourseStatus.draft)
    group = await create_group(session, course, teacher, status=GroupStatus.draft)
    lesson = await create_lesson(session, group)
    login_as(teacher)

    for url in [
        f"/web/lessons/{lesson.id}/delete",
        f"/web/groups/{group.id}/delete",
        f"/web/courses/{course.id}/delete",
    ]:
        assert _redirects_with_message(await client.post(url, follow_redirects=False)), url

    await session.refresh(course)
    assert course.deleted_at is not None


async def test_teacher_form_error_becomes_flash_error(client, session, login_as):
    """Tasdiqlanmagan teacher kurs yarata olmaydi — xato flash-xabarda ko'rinadi."""
    teacher = await create_teacher(session, status=UserStatus.pending)
    login_as(teacher)

    response = await client.post(
        "/web/courses",
        data={"title": "Ruxsatsiz kurs", "subject": "Fizika", "price": "300000"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "error=" in response.headers["location"]


# --- Student formalari -------------------------------------------------------


async def test_student_pays_in_full_through_web_form(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    login_as(student)

    response = await client.post(
        "/web/payments",
        data={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        follow_redirects=False,
    )

    assert _redirects_with_message(response)
    payment = await session.scalar(select(Payment))
    assert payment.status == PaymentStatus.pending


async def test_student_creates_payment_plan_through_web_form(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    login_as(student)

    response = await client.post(
        f"/web/enrollments/{enrollment.id}/payment-plan",
        data={"installments_count": "2"},
        follow_redirects=False,
    )

    assert _redirects_with_message(response)
    plan = await session.scalar(select(PaymentPlan))
    assert plan.installments_count == 2


async def test_student_cancels_enrollment_through_web_form(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    login_as(student)

    response = await client.post(
        f"/web/enrollments/{enrollment.id}/cancel", follow_redirects=False
    )

    assert _redirects_with_message(response)
    await session.refresh(enrollment)
    assert enrollment.status == EnrollmentStatus.cancelled


async def test_student_marks_lesson_watched_through_web_form(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    lesson = await create_lesson(session, group)
    student = await create_student(session)
    await create_enrollment(session, student, group, status=EnrollmentStatus.active)
    login_as(student)

    response = await client.post(
        f"/web/lessons/{lesson.id}/progress",
        data={"next_url": "/dashboard/student"},
        follow_redirects=False,
    )

    assert _redirects_with_message(response)


# --- Manager formalari -------------------------------------------------------


async def test_manager_rejects_user_through_web_form(client, session, login_as):
    manager = await create_manager(session)
    student = await create_student(session, status=UserStatus.pending)
    login_as(manager)

    response = await client.post(
        f"/web/manager/users/{student.id}/reject",
        data={"reason": "Hujjatlar yetarli emas"},
        follow_redirects=False,
    )

    assert _redirects_with_message(response)
    await session.refresh(student)
    assert student.status == UserStatus.rejected


async def test_manager_assigns_teacher_through_web_form(client, session, login_as):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.draft)
    login_as(manager)

    response = await client.post(
        f"/web/manager/groups/{group.id}/assign-teacher",
        data={"teacher_id": ""},
        follow_redirects=False,
    )

    assert _redirects_with_message(response)
    await session.refresh(group)
    assert group.status == GroupStatus.active


async def test_manager_confirms_and_rejects_payments_through_web_forms(
    client, session, login_as
):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)

    first_student = await create_student(session)
    first_enrollment = await create_enrollment(session, first_student, group)
    login_as(first_student)
    await client.post(
        "/web/payments",
        data={"enrollment_id": str(first_enrollment.id), "amount": str(COURSE_PRICE)},
        follow_redirects=False,
    )

    second_student = await create_student(session)
    second_enrollment = await create_enrollment(session, second_student, group)
    client.cookies.clear()
    login_as(second_student)
    await client.post(
        "/web/payments",
        data={"enrollment_id": str(second_enrollment.id), "amount": str(COURSE_PRICE)},
        follow_redirects=False,
    )

    payments = list(await session.scalars(select(Payment)))
    client.cookies.clear()
    login_as(manager)

    confirm = await client.post(
        f"/web/manager/payments/{payments[0].id}/confirm", follow_redirects=False
    )
    reject = await client.post(
        f"/web/manager/payments/{payments[1].id}/reject",
        data={"reason": "Chek noaniq"},
        follow_redirects=False,
    )

    assert _redirects_with_message(confirm)
    assert _redirects_with_message(reject)


async def test_manager_cancels_enrollment_with_reason(client, session, login_as):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    login_as(manager)

    without_reason = await client.post(
        f"/web/enrollments/{enrollment.id}/cancel",
        data={"next_url": "/dashboard/manager"},
        follow_redirects=False,
    )
    assert "error=" in without_reason.headers["location"]

    with_reason = await client.post(
        f"/web/enrollments/{enrollment.id}/cancel",
        data={"reason": "Guruh qayta tuzildi", "next_url": "/dashboard/manager"},
        follow_redirects=False,
    )
    assert _redirects_with_message(with_reason)


# --- Superadmin formalari ----------------------------------------------------


async def test_superadmin_blocks_and_unblocks_through_web_forms(client, session, login_as):
    superadmin = await create_superadmin(session)
    student = await create_student(session)
    login_as(superadmin)

    block = await client.post(
        f"/web/superadmin/users/{student.id}/block", follow_redirects=False
    )
    assert _redirects_with_message(block)
    await session.refresh(student)
    assert student.status == UserStatus.blocked

    unblock = await client.post(
        f"/web/superadmin/users/{student.id}/unblock", follow_redirects=False
    )
    assert _redirects_with_message(unblock)
    await session.refresh(student)
    assert student.status == UserStatus.approved


async def test_superadmin_restores_deleted_records(client, session, login_as):
    teacher = await create_teacher(session)
    superadmin = await create_superadmin(session)
    course = await create_course(session, teacher, status=CourseStatus.draft)
    group = await create_group(session, course, teacher, status=GroupStatus.draft)
    lesson = await create_lesson(session, group)

    login_as(teacher)
    await client.post(f"/web/lessons/{lesson.id}/delete", follow_redirects=False)
    await client.post(f"/web/groups/{group.id}/delete", follow_redirects=False)
    await client.post(f"/web/courses/{course.id}/delete", follow_redirects=False)

    client.cookies.clear()
    login_as(superadmin)
    for url in [
        f"/web/courses/{course.id}/restore",
        f"/web/groups/{group.id}/restore",
        f"/web/lessons/{lesson.id}/restore",
    ]:
        assert _redirects_with_message(await client.post(url, follow_redirects=False)), url

    await session.refresh(course)
    assert course.deleted_at is None


async def test_non_superadmin_cannot_restore(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, status=CourseStatus.draft)
    login_as(teacher)
    await client.post(f"/web/courses/{course.id}/delete", follow_redirects=False)

    response = await client.post(
        f"/web/courses/{course.id}/restore", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/?error=")


async def test_superadmin_dashboard_filters_render(client, session, login_as):
    superadmin = await create_superadmin(session)
    login_as(superadmin)

    response = await client.get(
        "/dashboard/superadmin?date_from=2026-01-01&date_to=2026-12-31&entity_type=course"
    )

    assert response.status_code == 200


async def test_manager_dashboard_enrollment_filter_renders(client, session, login_as):
    manager = await create_manager(session)
    login_as(manager)

    response = await client.get("/dashboard/manager?enrollment_status=active")

    assert response.status_code == 200


async def test_home_page_filters_render(client, session):
    teacher = await create_teacher(session)
    await create_course(session, teacher, price=COURSE_PRICE)

    response = await client.get("/?subject=Ingliz&max_price=1000000")

    assert response.status_code == 200


async def test_notification_read_form(client, session, login_as):
    manager = await create_manager(session)
    teacher = await create_teacher(session, status=UserStatus.pending)
    login_as(manager)
    await client.post(f"/web/manager/users/{teacher.id}/approve", follow_redirects=False)

    client.cookies.clear()
    login_as(teacher)
    page = await client.get("/notifications")
    assert page.status_code == 200

    notification = await session.scalar(select(Notification))
    response = await client.post(
        f"/web/notifications/{notification.id}/read", follow_redirects=False
    )

    assert response.status_code == 303
