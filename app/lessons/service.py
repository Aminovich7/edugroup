"""Dars biznes-logikasi.

Video havolasi faqat kirish huquqiga ega foydalanuvchiga qaytariladi:
- student — shu guruhda active yozilishi bo'lsa (ya'ni to'lovi tasdiqlangan),
- teacher — o'z guruhi bo'lsa,
- manager va superadmin — barchasiga.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.audit.models import AuditAction, AuditEntityType
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.enrollments import repository as enrollments_repository
from app.enrollments.models import EnrollmentStatus
from app.enrollments.service import get_active_enrollment
from app.groups import repository as groups_repository
from app.groups.models import Group
from app.lessons import repository
from app.lessons.models import Lesson, LessonProgress
from app.lessons.schemas import LessonCreateRequest, LessonUpdateRequest, StudentProgressRow
from app.notifications import service as notifications_service
from app.notifications.models import NotificationType
from app.users import repository as users_repository
from app.users.models import User, UserRole

EDITABLE_FIELDS = (
    "title",
    "description",
    "kinescope_video_id",
    "kinescope_url",
    "duration_seconds",
    "order_index",
)


async def create_lesson(
    session: AsyncSession, group_id: uuid.UUID, data: LessonCreateRequest, teacher: User
) -> Lesson:
    """Teacher o'z guruhiga dars qo'shadi va guruh o'quvchilariga xabar boradi."""
    group = await _get_group(session, group_id)
    _ensure_can_manage_lessons(group, teacher)

    lesson = Lesson(
        group_id=group_id,
        title=data.title,
        description=data.description,
        kinescope_video_id=data.kinescope_video_id,
        kinescope_url=data.kinescope_url,
        duration_seconds=data.duration_seconds,
        order_index=data.order_index,
    )
    session.add(lesson)
    await session.flush()

    await _notify_group_students(session, group, lesson)
    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.lesson,
        entity_id=lesson.id,
        action=AuditAction.create,
        actor_id=teacher.id,
    )
    await session.commit()
    await session.refresh(lesson)
    return lesson


async def list_for_group(
    session: AsyncSession, group_id: uuid.UUID, viewer: User
) -> list[Lesson]:
    """Guruh darslari ro'yxati — faqat kirish huquqi borlar uchun."""
    group = await _get_group(session, group_id)
    await ensure_can_view_lessons(session, group, viewer)
    return await repository.list_for_group(session, group_id)


async def get_lesson(session: AsyncSession, lesson_id: uuid.UUID, viewer: User) -> Lesson:
    lesson = await repository.get_by_id(session, lesson_id)
    if lesson is None or lesson.is_deleted:
        raise NotFoundError("Dars topilmadi")

    group = await _get_group(session, lesson.group_id)
    await ensure_can_view_lessons(session, group, viewer)
    return lesson


async def update_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, data: LessonUpdateRequest, current_user: User
) -> Lesson:
    lesson = await _get_editable_lesson(session, lesson_id, current_user)

    before = {field: getattr(lesson, field) for field in EDITABLE_FIELDS}
    # exclude_none: forma bo'sh qoldirgan maydon "o'zgartirilmaydi" degani.
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(lesson, field, value)
    after = {field: getattr(lesson, field) for field in EDITABLE_FIELDS}

    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.lesson,
        entity_id=lesson.id,
        action=AuditAction.update,
        actor_id=current_user.id,
        changes=audit_service.build_changes(before, after),
    )
    await session.commit()
    await session.refresh(lesson)
    return lesson


async def soft_delete_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, current_user: User
) -> Lesson:
    lesson = await _get_editable_lesson(session, lesson_id, current_user)

    lesson.deleted_at = datetime.now(UTC)
    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.lesson,
        entity_id=lesson.id,
        action=AuditAction.delete,
        actor_id=current_user.id,
    )
    await session.commit()
    await session.refresh(lesson)
    return lesson


async def restore_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, superadmin: User
) -> Lesson:
    lesson = await repository.get_by_id(session, lesson_id)
    if lesson is None:
        raise NotFoundError("Dars topilmadi")
    if not lesson.is_deleted:
        raise BusinessRuleError("Bu dars o'chirilmagan")

    lesson.deleted_at = None
    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.lesson,
        entity_id=lesson.id,
        action=AuditAction.restore,
        actor_id=superadmin.id,
    )
    await session.commit()
    await session.refresh(lesson)
    return lesson


# --- Progress ----------------------------------------------------------------


async def mark_watched(
    session: AsyncSession, lesson_id: uuid.UUID, student: User
) -> LessonProgress:
    """Student darsni "tomosha qildim" deb belgilaydi."""
    lesson = await repository.get_by_id(session, lesson_id)
    if lesson is None or lesson.is_deleted:
        raise NotFoundError("Dars topilmadi")

    enrollment = await get_active_enrollment(session, student.id, lesson.group_id)
    if enrollment is None:
        raise PermissionDeniedError("Bu darsni ko'rish huquqingiz yo'q")

    progress = await repository.get_progress(session, student.id, lesson_id)
    if progress is None:
        progress = LessonProgress(student_id=student.id, lesson_id=lesson_id)
        session.add(progress)

    progress.watched = True
    progress.watched_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(progress)
    return progress


async def list_progress_for_student(
    session: AsyncSession, student: User
) -> list[LessonProgress]:
    return await repository.list_progress_for_student(session, student.id)


async def get_group_progress(
    session: AsyncSession, group_id: uuid.UUID, viewer: User
) -> list[StudentProgressRow]:
    """Guruhdagi har bir o'quvchi nechta darsni ko'rganini jadval qilib qaytaradi."""
    group = await _get_group(session, group_id)
    _ensure_can_manage_lessons(group, viewer)

    lessons = await repository.list_for_group(session, group_id)
    lesson_ids = [lesson.id for lesson in lessons]
    watched_records = await repository.list_progress_for_lessons(session, lesson_ids)

    watched_count_by_student: dict[uuid.UUID, int] = {}
    for record in watched_records:
        watched_count_by_student[record.student_id] = (
            watched_count_by_student.get(record.student_id, 0) + 1
        )

    enrollments = await enrollments_repository.list_for_group(
        session, group_id, statuses=(EnrollmentStatus.active,)
    )

    rows = []
    for enrollment in enrollments:
        student = await users_repository.get_by_id(session, enrollment.student_id)
        rows.append(
            StudentProgressRow(
                student_id=enrollment.student_id,
                student_name=student.full_name if student else "—",
                watched_lessons=watched_count_by_student.get(enrollment.student_id, 0),
                total_lessons=len(lessons),
            )
        )
    return rows


# --- Kirish huquqi -----------------------------------------------------------


async def ensure_can_view_lessons(session: AsyncSession, group: Group, viewer: User) -> None:
    """Video kontentga kirish huquqini tekshiradi."""
    if viewer.role in (UserRole.manager, UserRole.superadmin):
        return
    if viewer.role == UserRole.teacher and group.teacher_id == viewer.id:
        return
    if viewer.role == UserRole.student:
        enrollment = await get_active_enrollment(session, viewer.id, group.id)
        if enrollment is not None:
            return
    raise PermissionDeniedError("Darslarni ko'rish uchun guruhga yozilib, to'lov qiling")


# --- Ichki yordamchi funksiyalar --------------------------------------------


async def _get_group(session: AsyncSession, group_id: uuid.UUID) -> Group:
    group = await groups_repository.get_by_id(session, group_id)
    if group is None or group.is_deleted:
        raise NotFoundError("Guruh topilmadi")
    return group


def _ensure_can_manage_lessons(group: Group, user: User) -> None:
    if user.role in (UserRole.manager, UserRole.superadmin):
        return
    if user.role == UserRole.teacher and group.teacher_id == user.id:
        return
    raise PermissionDeniedError("Bu guruh darslarini boshqarish huquqingiz yo'q")


async def _get_editable_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, current_user: User
) -> Lesson:
    lesson = await repository.get_by_id(session, lesson_id)
    if lesson is None or lesson.is_deleted:
        raise NotFoundError("Dars topilmadi")
    group = await _get_group(session, lesson.group_id)
    _ensure_can_manage_lessons(group, current_user)
    return lesson


async def _notify_group_students(
    session: AsyncSession, group: Group, lesson: Lesson
) -> None:
    """Yangi dars qo'shilganda guruhning barcha active o'quvchilariga xabar."""
    enrollments = await enrollments_repository.list_for_group(
        session, group.id, statuses=(EnrollmentStatus.active,)
    )
    for enrollment in enrollments:
        await notifications_service.create_notification(
            session,
            user_id=enrollment.student_id,
            notification_type=NotificationType.lesson_added,
            title="Yangi dars qo'shildi",
            message=f"'{group.name}' guruhiga '{lesson.title}' darsi qo'shildi.",
            related_entity_type="lesson",
            related_entity_id=lesson.id,
        )
