"""Veb-sahifalar: ochiq sahifalar 200 qaytaradi, himoyalanganlari login'ga yo'naltiradi."""

from decimal import Decimal

from sqlalchemy import select

from app.enrollments.models import Enrollment, EnrollmentStatus
from app.users.models import UserStatus
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

COURSE_PRICE = Decimal("500000.00")


async def test_public_pages_render(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)

    for url in ["/", "/login", "/register", f"/courses/{course.id}", f"/groups/{group.id}"]:
        response = await client.get(url)
        assert response.status_code == 200, url
        assert "text/html" in response.headers["content-type"]


async def test_protected_pages_redirect_to_login(client):
    for url in ["/dashboard", "/profile", "/notifications"]:
        response = await client.get(url, follow_redirects=False)
        assert response.status_code == 303, url
        assert response.headers["location"] == "/login"


async def test_login_form_sets_cookie_and_redirects_to_dashboard(client, session):
    student = await create_student(session, email="web-login@test.uz")

    response = await client.post(
        "/login",
        data={"email": student.email, "password": DEFAULT_PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard/student"
    assert "access_token" in response.cookies


async def test_login_with_wrong_password_shows_error(client, session):
    student = await create_student(session, email="web-xato@test.uz")

    response = await client.post(
        "/login",
        data={"email": student.email, "password": "notogri"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?error=")


async def test_register_form_creates_user(client):
    response = await client.post(
        "/register",
        data={
            "role": "student",
            "full_name": "Web Student",
            "email": "web-register@test.uz",
            "password": DEFAULT_PASSWORD,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?message=")


async def test_each_role_dashboard_renders(client, session, login_as):
    manager = await create_manager(session)
    superadmin = await create_superadmin(session)
    teacher = await create_teacher(session)
    student = await create_student(session)

    for user in (student, teacher, manager, superadmin):
        login_as(user)
        response = await client.get(f"/dashboard/{user.role.value}")
        assert response.status_code == 200, user.role.value


async def test_student_enrolls_through_web_form(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)
    login_as(student)

    response = await client.post(
        "/web/enrollments", data={"group_id": str(group.id)}, follow_redirects=False
    )

    assert response.status_code == 303
    enrollment = await session.scalar(
        select(Enrollment).where(Enrollment.student_id == student.id)
    )
    assert enrollment is not None


async def test_web_form_error_is_shown_as_flash_message(client, session, login_as):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    await create_enrollment(session, student, group)
    login_as(student)

    # Ikkinchi marta yozilish — xato flash-xabar bilan qaytadi.
    response = await client.post(
        "/web/enrollments", data={"group_id": str(group.id)}, follow_redirects=False
    )

    assert response.status_code == 303
    assert "error=" in response.headers["location"]


async def test_profile_page_and_edit_form(client, session, login_as):
    student = await create_student(session, full_name="Eski Ism")
    login_as(student)

    page = await client.get("/profile")
    assert page.status_code == 200

    edit = await client.post(
        "/web/profile/edit", data={"full_name": "Yangi Ism"}, follow_redirects=False
    )
    assert edit.status_code == 303

    await session.refresh(student)
    assert student.full_name == "Yangi Ism"


async def test_manager_approves_user_through_web_form(client, session, login_as):
    manager = await create_manager(session)
    teacher = await create_teacher(session, status=UserStatus.pending)
    login_as(manager)

    response = await client.post(
        f"/web/manager/users/{teacher.id}/approve", follow_redirects=False
    )

    assert response.status_code == 303
    await session.refresh(teacher)
    assert teacher.status == UserStatus.approved


async def test_superadmin_manager_page_and_creation(client, session, login_as):
    superadmin = await create_superadmin(session)
    login_as(superadmin)

    page = await client.get("/web/superadmin/managers")
    assert page.status_code == 200

    create = await client.post(
        "/web/superadmin/managers",
        data={
            "full_name": "Web Manager",
            "email": "web-manager@test.uz",
            "password": DEFAULT_PASSWORD,
        },
        follow_redirects=False,
    )
    assert create.status_code == 303
    assert "message=" in create.headers["location"]


async def test_non_superadmin_cannot_open_manager_page(client, session, login_as):
    manager = await create_manager(session)
    login_as(manager)

    response = await client.get("/web/superadmin/managers", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/?error=")


async def test_report_pages_render(client, session, login_as):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    login_as(manager)

    group_report = await client.get(f"/reports/groups/{group.id}")
    teacher_report = await client.get(f"/reports/teachers/{teacher.id}")

    assert group_report.status_code == 200
    assert teacher_report.status_code == 200


async def test_notifications_page_and_mark_all_read(client, session, login_as):
    manager = await create_manager(session)
    teacher = await create_teacher(session, status=UserStatus.pending)
    login_as(manager)
    await client.post(f"/web/manager/users/{teacher.id}/approve", follow_redirects=False)

    client.cookies.clear()
    login_as(teacher)

    page = await client.get("/notifications")
    assert page.status_code == 200

    mark_all = await client.post("/web/notifications/read-all", follow_redirects=False)
    assert mark_all.status_code == 303
    assert "message=" in mark_all.headers["location"]


async def test_blocked_user_is_redirected_from_protected_page(client, session, login_as):
    """Bloklangan foydalanuvchi himoyalangan sahifaga kira olmaydi."""
    superadmin = await create_superadmin(session)
    student = await create_student(session)
    login_as(superadmin)
    await client.post(f"/web/superadmin/users/{student.id}/block", follow_redirects=False)

    client.cookies.clear()
    login_as(student)

    response = await client.get("/notifications", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_unknown_group_returns_html_404(client, login_as, session):
    student = await create_student(session)
    login_as(student)

    response = await client.get("/groups/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]


async def test_logout_clears_session(client, session, login_as):
    student = await create_student(session)
    login_as(student)

    response = await client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/?message=")
