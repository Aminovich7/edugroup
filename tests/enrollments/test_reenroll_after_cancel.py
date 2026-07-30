"""Partial unique index tekshiruvi: bekor qilingandan keyin qayta yozilish mumkin.

Bu — v1.0'dagi bugning qaytmasligini kafolatlaydigan test. Agar
unique_constraint(student_id, group_id) oddiy jadval-darajasida bo'lganda,
bekor qilingan yozuv o'sha juftlikni abadiy band qilib qo'yardi va student
o'sha guruhga hech qachon qayta yozila olmasdi.
"""

from sqlalchemy import select

from app.enrollments.models import Enrollment, EnrollmentStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_student,
    create_teacher,
)


async def test_student_can_reenroll_after_cancelling(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)

    first = await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(student)
    )
    assert first.status_code == 201

    await client.request(
        "DELETE",
        f"/api/enrollments/{first.json()['id']}",
        headers=auth_headers(student),
    )

    second = await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(student)
    )

    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]


async def test_student_can_reenroll_after_expiry(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)
    await create_enrollment(session, student, group, status=EnrollmentStatus.expired)

    response = await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(student)
    )

    assert response.status_code == 201


async def test_old_enrollment_stays_in_history(client, session):
    """Bekor qilingan yozuv o'chirilmaydi — u tarix sifatida saqlanib qoladi."""
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)

    first = await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(student)
    )
    await client.request(
        "DELETE", f"/api/enrollments/{first.json()['id']}", headers=auth_headers(student)
    )
    await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(student)
    )

    rows = list(
        await session.scalars(
            select(Enrollment).where(
                Enrollment.student_id == student.id, Enrollment.group_id == group.id
            )
        )
    )
    statuses = sorted(row.status.value for row in rows)
    assert statuses == ["awaiting_payment", "cancelled"]
