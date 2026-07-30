"""Profilni ko'rish va tahrirlash."""

from tests.conftest import auth_headers
from tests.factories import create_student, create_teacher


async def test_get_me_returns_profile(client, session):
    student = await create_student(session, full_name="Ali Valiyev")

    response = await client.get("/api/users/me", headers=auth_headers(student))

    assert response.status_code == 200
    assert response.json()["full_name"] == "Ali Valiyev"


async def test_get_me_without_token_returns_401(client):
    response = await client.get("/api/users/me")
    assert response.status_code == 401


async def test_update_profile_changes_name_and_phone(client, session):
    student = await create_student(session)

    response = await client.patch(
        "/api/users/me",
        json={"full_name": "Yangi Ism", "phone": "+998901112233"},
        headers=auth_headers(student),
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Yangi Ism"
    assert response.json()["phone"] == "+998901112233"


async def test_teacher_can_update_specialization(client, session):
    teacher = await create_teacher(session)

    response = await client.patch(
        "/api/users/me",
        json={"specialization": "Fizika", "experience_years": 12},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 200
    assert response.json()["teacher_profile"]["specialization"] == "Fizika"
    assert response.json()["teacher_profile"]["experience_years"] == 12
