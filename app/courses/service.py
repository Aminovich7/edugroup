"""Kurs biznes-logikasi.

Kurs `draft` holatda yaratiladi; teacher uni tayyor bo'lgach `active` qiladi
(PATCH orqali) va shundan keyin kurs ommaviy katalogda ko'rinadi.
O'chirish jismoniy emas — `deleted_at` to'ldiriladi va AuditLog yoziladi.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.audit.models import AuditAction, AuditEntityType
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.courses import repository
from app.courses.models import Course, CourseStatus
from app.courses.schemas import CourseCreateRequest, CourseUpdateRequest
from app.users.models import User, UserRole, UserStatus

EDITABLE_FIELDS = ("title", "description", "subject", "price", "status")


async def create_course(
    session: AsyncSession, data: CourseCreateRequest, teacher: User
) -> Course:
    """Faqat tasdiqlangan (approved) teacher kurs yarata oladi."""
    if teacher.status != UserStatus.approved:
        raise PermissionDeniedError("Kurs yaratish uchun profilingiz tasdiqlangan bo'lishi kerak")

    course = Course(
        teacher_id=teacher.id,
        title=data.title,
        description=data.description,
        subject=data.subject,
        price=data.price,
        status=CourseStatus.draft,
    )
    session.add(course)
    await session.flush()

    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.course,
        entity_id=course.id,
        action=AuditAction.create,
        actor_id=teacher.id,
    )
    await session.commit()
    await session.refresh(course)
    return course


async def list_active(
    session: AsyncSession, subject: str | None = None, teacher_id: uuid.UUID | None = None
) -> list[Course]:
    """Ommaviy katalog uchun — faqat active va o'chirilmagan kurslar."""
    return await repository.list_courses(
        session, subject=subject, teacher_id=teacher_id, status=CourseStatus.active
    )


async def list_mine(session: AsyncSession, teacher: User) -> list[Course]:
    return await repository.list_courses(session, teacher_id=teacher.id)


async def list_courses(
    session: AsyncSession,
    subject: str | None = None,
    teacher_id: uuid.UUID | None = None,
    status: CourseStatus | None = None,
    include_deleted: bool = False,
) -> list[Course]:
    return await repository.list_courses(
        session,
        subject=subject,
        teacher_id=teacher_id,
        status=status,
        include_deleted=include_deleted,
    )


async def get_course(session: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await repository.get_by_id(session, course_id)
    if course is None or course.is_deleted:
        raise NotFoundError("Kurs topilmadi")
    return course


async def update_course(
    session: AsyncSession, course_id: uuid.UUID, data: CourseUpdateRequest, current_user: User
) -> Course:
    """Kursni tahrirlash — teacher (faqat o'ziniki), manager yoki superadmin."""
    course = await get_course(session, course_id)
    _ensure_can_edit(course, current_user)

    before = {field: getattr(course, field) for field in EDITABLE_FIELDS}
    # exclude_none: forma bo'sh qoldirgan maydon "o'zgartirilmaydi" degani.
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(course, field, value)
    after = {field: getattr(course, field) for field in EDITABLE_FIELDS}

    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.course,
        entity_id=course.id,
        action=AuditAction.update,
        actor_id=current_user.id,
        changes=audit_service.build_changes(before, after),
    )
    await session.commit()
    await session.refresh(course)
    return course


async def soft_delete_course(
    session: AsyncSession, course_id: uuid.UUID, current_user: User
) -> Course:
    """Kursni o'chiradi — yozuv bazada qoladi, faqat deleted_at to'ldiriladi."""
    course = await get_course(session, course_id)

    if current_user.role == UserRole.teacher:
        if course.teacher_id != current_user.id:
            raise PermissionDeniedError("Bu kurs sizga tegishli emas")
        if course.status != CourseStatus.draft:
            raise BusinessRuleError("Teacher faqat draft holatidagi kursni o'chira oladi")
    elif current_user.role != UserRole.superadmin:
        raise PermissionDeniedError()

    course.deleted_at = datetime.now(UTC)
    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.course,
        entity_id=course.id,
        action=AuditAction.delete,
        actor_id=current_user.id,
    )
    await session.commit()
    await session.refresh(course)
    return course


async def restore_course(
    session: AsyncSession, course_id: uuid.UUID, superadmin: User
) -> Course:
    """O'chirilgan kursni tiklaydi (faqat superadmin)."""
    course = await repository.get_by_id(session, course_id)
    if course is None:
        raise NotFoundError("Kurs topilmadi")
    if not course.is_deleted:
        raise BusinessRuleError("Bu kurs o'chirilmagan")

    course.deleted_at = None
    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.course,
        entity_id=course.id,
        action=AuditAction.restore,
        actor_id=superadmin.id,
    )
    await session.commit()
    await session.refresh(course)
    return course


def _ensure_can_edit(course: Course, current_user: User) -> None:
    if current_user.role in (UserRole.manager, UserRole.superadmin):
        return
    if current_user.role == UserRole.teacher and course.teacher_id == current_user.id:
        return
    raise PermissionDeniedError("Bu kursni tahrirlash huquqingiz yo'q")
