"""Audit log: o'chirish jismoniy emas va har bir amal tarixga yoziladi."""

from sqlalchemy import select

from app.audit.models import AuditAction, AuditEntityType, AuditLog
from app.courses.models import Course, CourseStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_group,
    create_lesson,
    create_manager,
    create_superadmin,
    create_teacher,
)


async def _audit_actions_for(session, entity_id) -> list[AuditAction]:
    rows = await session.scalars(select(AuditLog).where(AuditLog.entity_id == entity_id))
    return [row.action for row in rows]


async def test_delete_keeps_row_and_writes_audit_log(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, status=CourseStatus.draft)

    await client.delete(f"/api/courses/{course.id}", headers=auth_headers(teacher))

    stored_course = await session.get(Course, course.id)
    await session.refresh(stored_course)
    # Yozuv bazada qoladi, faqat deleted_at to'ldiriladi.
    assert stored_course is not None
    assert stored_course.deleted_at is not None

    assert AuditAction.delete in await _audit_actions_for(session, course.id)


async def test_create_update_delete_restore_are_all_logged(client, session):
    teacher = await create_teacher(session)
    superadmin = await create_superadmin(session)

    created = await client.post(
        "/api/courses",
        json={"title": "Audit kursi", "subject": "Fizika", "price": "200000.00"},
        headers=auth_headers(teacher),
    )
    course_id = created.json()["id"]

    await client.patch(
        f"/api/courses/{course_id}",
        json={"title": "Yangi nom"},
        headers=auth_headers(teacher),
    )
    await client.delete(f"/api/courses/{course_id}", headers=auth_headers(teacher))
    await client.post(
        f"/api/courses/{course_id}/restore", headers=auth_headers(superadmin)
    )

    actions = await _audit_actions_for(session, course_id)
    assert set(actions) == {
        AuditAction.create,
        AuditAction.update,
        AuditAction.delete,
        AuditAction.restore,
    }


async def test_update_stores_field_diff(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, title="Eski nom")

    await client.patch(
        f"/api/courses/{course.id}",
        json={"title": "Yangi nom"},
        headers=auth_headers(teacher),
    )

    log_entry = await session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == course.id, AuditLog.action == AuditAction.update
        )
    )
    assert log_entry.changes["title"] == {"old": "Eski nom", "new": "Yangi nom"}


async def test_lesson_and_group_deletes_are_logged(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status="draft")
    lesson = await create_lesson(session, group)

    await client.delete(f"/api/lessons/{lesson.id}", headers=auth_headers(teacher))
    await client.delete(f"/api/groups/{group.id}", headers=auth_headers(teacher))

    lesson_logs = await session.scalars(
        select(AuditLog).where(AuditLog.entity_type == AuditEntityType.lesson)
    )
    group_logs = await session.scalars(
        select(AuditLog).where(AuditLog.entity_type == AuditEntityType.group)
    )
    assert AuditAction.delete in [row.action for row in lesson_logs]
    assert AuditAction.delete in [row.action for row in group_logs]


async def test_only_superadmin_can_read_audit_logs(client, session):
    superadmin = await create_superadmin(session)
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    await create_course(session, teacher)

    allowed = await client.get("/api/audit-logs", headers=auth_headers(superadmin))
    forbidden = await client.get("/api/audit-logs", headers=auth_headers(manager))

    assert allowed.status_code == 200
    assert forbidden.status_code == 403


async def test_audit_logs_can_be_filtered_by_entity_type(client, session):
    superadmin = await create_superadmin(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    await create_group(session, course, teacher)

    await client.post(
        "/api/courses",
        json={"title": "Filtr kursi", "subject": "Kimyo", "price": "100000.00"},
        headers=auth_headers(teacher),
    )

    response = await client.get(
        "/api/audit-logs?entity_type=course", headers=auth_headers(superadmin)
    )

    assert response.status_code == 200
    assert response.json()["total_count"] == 1
