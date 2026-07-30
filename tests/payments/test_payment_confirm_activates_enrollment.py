"""To'liq end-to-end oqim (TZ 12-bo'lim):

register → manager approve → teacher kurs/guruh yaratadi → manager guruhni
tasdiqlaydi → student yoziladi → to'lov yaratadi → manager tasdiqlaydi →
enrollment active bo'ladi → student Kinescope havolasini oladi.
"""

from decimal import Decimal

from app.enrollments.models import EnrollmentStatus
from app.payments.models import PaymentStatus
from app.users.models import UserStatus
from tests.conftest import auth_headers
from tests.factories import (
    DEFAULT_PASSWORD,
    create_course,
    create_enrollment,
    create_group,
    create_manager,
    create_student,
    create_superadmin,
    create_teacher,
)

COURSE_PRICE = "500000.00"
LESSON = {
    "title": "1-dars",
    "kinescope_video_id": "abc123",
    "kinescope_url": "https://kinescope.io/abc123",
    "duration_seconds": 420,
    "order_index": 1,
}


async def test_full_flow_from_registration_to_watching_lesson(client, session):
    manager = await create_manager(session)

    # 1. Ro'yxatdan o'tish
    student_response = await client.post(
        "/api/auth/register/student",
        json={"full_name": "Ali Valiyev", "email": "oqim-student@test.uz", "password": DEFAULT_PASSWORD},
    )
    teacher_response = await client.post(
        "/api/auth/register/teacher",
        json={"full_name": "Dilnoza", "email": "oqim-teacher@test.uz", "password": DEFAULT_PASSWORD},
    )
    student_id = student_response.json()["id"]
    teacher_id = teacher_response.json()["id"]

    # 2. Manager ikkalasini ham tasdiqlaydi
    await client.post(f"/api/manager/users/{student_id}/approve", headers=auth_headers(manager))
    await client.post(f"/api/manager/users/{teacher_id}/approve", headers=auth_headers(manager))

    student_login = await client.post(
        "/api/auth/login", json={"email": "oqim-student@test.uz", "password": DEFAULT_PASSWORD}
    )
    teacher_login = await client.post(
        "/api/auth/login", json={"email": "oqim-teacher@test.uz", "password": DEFAULT_PASSWORD}
    )
    student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}
    teacher_headers = {"Authorization": f"Bearer {teacher_login.json()['access_token']}"}

    # 3. Teacher kurs va guruh yaratadi
    course = await client.post(
        "/api/courses",
        json={"title": "Ingliz tili", "subject": "Ingliz tili", "price": COURSE_PRICE},
        headers=teacher_headers,
    )
    group = await client.post(
        "/api/groups",
        json={
            "course_id": course.json()["id"],
            "name": "Guruh A",
            "capacity": 5,
            "schedule": "Dush, Chor 18:00",
        },
        headers=teacher_headers,
    )
    group_id = group.json()["id"]

    # 4. Manager guruhni tasdiqlaydi (draft -> active)
    assign = await client.post(
        f"/api/manager/groups/{group_id}/assign-teacher", json={}, headers=auth_headers(manager)
    )
    assert assign.json()["status"] == "active"

    lesson = await client.post(
        f"/api/groups/{group_id}/lessons", json=LESSON, headers=teacher_headers
    )
    lesson_id = lesson.json()["id"]

    # 5. Student yoziladi
    enrollment = await client.post(
        "/api/enrollments", json={"group_id": group_id}, headers=student_headers
    )
    enrollment_id = enrollment.json()["id"]
    assert enrollment.json()["status"] == EnrollmentStatus.awaiting_payment.value

    # To'lovdan oldin video yopiq
    blocked = await client.get(f"/api/lessons/{lesson_id}", headers=student_headers)
    assert blocked.status_code == 403

    # 6. Student to'lov yaratadi
    payment = await client.post(
        "/api/payments",
        json={"enrollment_id": enrollment_id, "amount": COURSE_PRICE},
        headers=student_headers,
    )
    payment_id = payment.json()["id"]

    # 7. Manager tasdiqlaydi
    confirm = await client.post(
        f"/api/payments/{payment_id}/confirm", headers=auth_headers(manager)
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == PaymentStatus.confirmed.value

    # 8. Enrollment active bo'ldi va video ochildi
    my_enrollments = await client.get("/api/enrollments/me", headers=student_headers)
    assert my_enrollments.json()[0]["status"] == EnrollmentStatus.active.value

    opened = await client.get(f"/api/lessons/{lesson_id}", headers=student_headers)
    assert opened.status_code == 200
    assert opened.json()["kinescope_url"] == LESSON["kinescope_url"]

    # 9. Darsni ko'rilgan deb belgilash
    progress = await client.post(
        f"/api/lessons/{lesson_id}/progress", headers=student_headers
    )
    assert progress.status_code == 201

    # 10. Teacher progressni ko'radi
    teacher_progress = await client.get(
        f"/api/groups/{group_id}/progress", headers=teacher_headers
    )
    assert teacher_progress.json()[0]["watched_lessons"] == 1

    # 11. Superadmin hisobotda daromadni ko'radi
    superadmin = await create_superadmin(session)
    overview = await client.get("/api/reports/overview", headers=auth_headers(superadmin))
    assert Decimal(overview.json()["total_revenue"]) == Decimal(COURSE_PRICE)


async def test_confirming_payment_twice_returns_400(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=Decimal(COURSE_PRICE))
    group = await create_group(session, course, teacher)
    student = await create_student(session, status=UserStatus.approved)
    enrollment = await create_enrollment(session, student, group)

    payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": COURSE_PRICE},
        headers=auth_headers(student),
    )
    payment_id = payment.json()["id"]

    first = await client.post(
        f"/api/payments/{payment_id}/confirm", headers=auth_headers(manager)
    )
    second = await client.post(
        f"/api/payments/{payment_id}/confirm", headers=auth_headers(manager)
    )

    assert first.status_code == 200
    assert second.status_code == 400


async def test_student_cannot_confirm_payment(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=Decimal(COURSE_PRICE))
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": COURSE_PRICE},
        headers=auth_headers(student),
    )

    response = await client.post(
        f"/api/payments/{payment.json()['id']}/confirm", headers=auth_headers(student)
    )

    assert response.status_code == 403
