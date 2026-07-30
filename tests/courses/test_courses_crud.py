"""Kurs CRUD: yaratish, ro'yxat, tahrirlash, soft delete va tiklash."""

from app.courses.models import CourseStatus
from app.users.models import UserStatus
from tests.conftest import auth_headers
from tests.factories import create_course, create_student, create_superadmin, create_teacher


async def test_approved_teacher_creates_draft_course(client, session):
    teacher = await create_teacher(session)

    response = await client.post(
        "/api/courses",
        json={"title": "Matematika asoslari", "subject": "Matematika", "price": "300000.00"},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 201
    assert response.json()["status"] == CourseStatus.draft.value


async def test_pending_teacher_cannot_create_course(client, session):
    teacher = await create_teacher(session, status=UserStatus.pending)

    response = await client.post(
        "/api/courses",
        json={"title": "Matematika", "subject": "Matematika", "price": "300000.00"},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 403


async def test_student_cannot_create_course(client, session):
    student = await create_student(session)

    response = await client.post(
        "/api/courses",
        json={"title": "Matematika", "subject": "Matematika", "price": "300000.00"},
        headers=auth_headers(student),
    )

    assert response.status_code == 403


async def test_public_list_shows_only_active_courses(client, session):
    teacher = await create_teacher(session)
    await create_course(session, teacher, title="Faol kurs", status=CourseStatus.active)
    await create_course(session, teacher, title="Qoralama", status=CourseStatus.draft)

    response = await client.get("/api/courses")

    assert response.status_code == 200
    titles = [course["title"] for course in response.json()]
    assert titles == ["Faol kurs"]


async def test_teacher_updates_own_course(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)

    response = await client.patch(
        f"/api/courses/{course.id}",
        json={"title": "Yangilangan nom"},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Yangilangan nom"


async def test_teacher_cannot_update_other_course(client, session):
    owner = await create_teacher(session)
    stranger = await create_teacher(session)
    course = await create_course(session, owner)

    response = await client.patch(
        f"/api/courses/{course.id}",
        json={"title": "O'g'irlangan"},
        headers=auth_headers(stranger),
    )

    assert response.status_code == 403


async def test_delete_is_soft_and_restore_works(client, session):
    teacher = await create_teacher(session)
    superadmin = await create_superadmin(session)
    course = await create_course(session, teacher, status=CourseStatus.draft)

    delete_response = await client.delete(
        f"/api/courses/{course.id}", headers=auth_headers(teacher)
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_at"] is not None

    # O'chirilgan kurs endi ko'rinmaydi.
    get_response = await client.get(f"/api/courses/{course.id}")
    assert get_response.status_code == 404

    restore_response = await client.post(
        f"/api/courses/{course.id}/restore", headers=auth_headers(superadmin)
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["deleted_at"] is None


async def test_teacher_cannot_delete_active_course(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, status=CourseStatus.active)

    response = await client.delete(f"/api/courses/{course.id}", headers=auth_headers(teacher))

    assert response.status_code == 400
