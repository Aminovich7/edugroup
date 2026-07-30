"""Guruh biznes-logikasi.

Guruh `draft` holatda yaratiladi va faqat manager `assign_teacher()` orqali
uni `active` qilgandan keyin katalogda ko'rinadi hamda yozilish ochiladi.
Keyinchalik manager guruhni `closed` (yangi yozilish yo'q) yoki `archived`
(butunlay yashirin) qilishi mumkin.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.audit.models import AuditAction, AuditEntityType
from app.core.exceptions import (
    BusinessRuleError,
    InvalidDataError,
    NotFoundError,
    PermissionDeniedError,
)
from app.courses import repository as courses_repository
from app.enrollments import repository as enrollments_repository
from app.enrollments.models import Enrollment, EnrollmentStatus
from app.groups import repository
from app.groups.models import Group, GroupStatus
from app.groups.schemas import GroupCreateRequest, GroupUpdateRequest
from app.notifications import service as notifications_service
from app.notifications.models import NotificationType
from app.users import repository as users_repository
from app.users.models import User, UserRole, UserStatus

EDITABLE_FIELDS = ("name", "capacity", "schedule", "status")

# Guruh holatining ruxsat etilgan o'tishlari.
# draft -> active o'tishi bu yerda yo'q: u faqat assign_teacher() orqali bo'ladi.
ALLOWED_STATUS_TRANSITIONS = {
    GroupStatus.active: (GroupStatus.closed, GroupStatus.archived),
    GroupStatus.closed: (GroupStatus.archived,),
}


async def create_group(session: AsyncSession, data: GroupCreateRequest, teacher: User) -> Group:
    """Teacher o'z kursi ichida guruh yaratadi — guruh draft holatda bo'ladi."""
    if teacher.status != UserStatus.approved:
        raise PermissionDeniedError("Guruh yaratish uchun profilingiz tasdiqlangan bo'lishi kerak")

    course = await courses_repository.get_by_id(session, data.course_id)
    if course is None or course.is_deleted:
        raise NotFoundError("Kurs topilmadi")
    if course.teacher_id != teacher.id:
        raise PermissionDeniedError("Bu kurs sizga tegishli emas")

    group = Group(
        course_id=course.id,
        teacher_id=teacher.id,
        name=data.name,
        capacity=data.capacity,
        schedule=data.schedule,
        status=GroupStatus.draft,
    )
    session.add(group)
    await session.flush()

    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.group,
        entity_id=group.id,
        action=AuditAction.create,
        actor_id=teacher.id,
    )
    await session.commit()
    await session.refresh(group)
    return group


async def list_active(
    session: AsyncSession,
    subject: str | None = None,
    teacher_id: uuid.UUID | None = None,
    course_id: uuid.UUID | None = None,
) -> list[Group]:
    """Ommaviy katalog — faqat active guruhlar (closed/archived ko'rinmaydi)."""
    return await repository.list_groups(
        session,
        subject=subject,
        teacher_id=teacher_id,
        course_id=course_id,
        status=GroupStatus.active,
    )


async def list_mine(session: AsyncSession, teacher: User) -> list[Group]:
    return await repository.list_groups(session, teacher_id=teacher.id)


async def list_groups(
    session: AsyncSession,
    status: GroupStatus | None = None,
    teacher_id: uuid.UUID | None = None,
    course_id: uuid.UUID | None = None,
    include_deleted: bool = False,
) -> list[Group]:
    """Manager/superadmin uchun — barcha guruhlar, filtrlar bilan."""
    return await repository.list_groups(
        session,
        status=status,
        teacher_id=teacher_id,
        course_id=course_id,
        include_deleted=include_deleted,
    )


async def get_group(session: AsyncSession, group_id: uuid.UUID) -> Group:
    group = await repository.get_by_id(session, group_id)
    if group is None or group.is_deleted:
        raise NotFoundError("Guruh topilmadi")
    return group


async def get_seat_info(session: AsyncSession, group: Group) -> dict[str, int]:
    """Katalogda ko'rsatish uchun: band joylar, bo'sh joylar va navbat uzunligi."""
    occupied_seats = await enrollments_repository.count_occupied_seats(session, group.id)
    waitlist = await enrollments_repository.list_waitlist(session, group.id)
    return {
        "occupied_seats": occupied_seats,
        "free_seats": max(group.capacity - occupied_seats, 0),
        "waitlist_count": len(waitlist),
    }


async def update_group(
    session: AsyncSession, group_id: uuid.UUID, data: GroupUpdateRequest, current_user: User
) -> Group:
    """Guruhni tahrirlash. Statusni faqat manager/superadmin o'zgartira oladi."""
    group = await get_group(session, group_id)
    ensure_can_manage(group, current_user)

    # exclude_none: forma to'ldirilmagan maydonni ham yuboradi — uni "o'zgartirmaslik"
    # deb qabul qilamiz, aks holda NOT NULL ustunga None yozilib qolardi.
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if "status" in fields:
        await _apply_status_change(session, group, fields.pop("status"), current_user)
    if "capacity" in fields:
        await _ensure_capacity_fits_existing_students(session, group, fields["capacity"])

    before = {field: getattr(group, field) for field in EDITABLE_FIELDS}
    for field, value in fields.items():
        setattr(group, field, value)
    after = {field: getattr(group, field) for field in EDITABLE_FIELDS}

    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.group,
        entity_id=group.id,
        action=AuditAction.update,
        actor_id=current_user.id,
        changes=audit_service.build_changes(before, after),
    )
    await session.commit()
    await session.refresh(group)
    return group


async def assign_teacher(
    session: AsyncSession,
    group_id: uuid.UUID,
    moderator: User,
    teacher_id: uuid.UUID | None = None,
) -> Group:
    """Guruhni tasdiqlaydi (draft -> active) va kerak bo'lsa teacher'ni almashtiradi.

    Bitta endpoint ikkala ishni ham bajaradi: tasdiqlash va qayta biriktirish.
    """
    group = await get_group(session, group_id)

    if teacher_id is not None and teacher_id != group.teacher_id:
        teacher = await users_repository.get_by_id(session, teacher_id)
        if teacher is None or teacher.role != UserRole.teacher:
            raise NotFoundError("Teacher topilmadi")
        if teacher.status != UserStatus.approved:
            raise BusinessRuleError("Faqat tasdiqlangan teacher biriktirilishi mumkin")
        group.teacher_id = teacher.id

    group.status = GroupStatus.active
    group.approved_by = moderator.id
    group.approved_at = datetime.now(UTC)

    await notifications_service.create_notification(
        session,
        user_id=group.teacher_id,
        notification_type=NotificationType.group_assigned,
        title="Guruh sizga biriktirildi",
        message=f"'{group.name}' guruhi tasdiqlandi va sizga biriktirildi.",
        related_entity_type="group",
        related_entity_id=group.id,
    )
    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.group,
        entity_id=group.id,
        action=AuditAction.update,
        actor_id=moderator.id,
        changes={"status": {"old": GroupStatus.draft.value, "new": GroupStatus.active.value}},
    )
    await session.commit()
    await session.refresh(group)
    return group


async def soft_delete_group(
    session: AsyncSession, group_id: uuid.UUID, current_user: User
) -> Group:
    group = await get_group(session, group_id)

    if current_user.role == UserRole.teacher:
        if group.teacher_id != current_user.id:
            raise PermissionDeniedError("Bu guruh sizga tegishli emas")
        if group.status != GroupStatus.draft:
            raise BusinessRuleError("Teacher faqat draft holatidagi guruhni o'chira oladi")
    elif current_user.role != UserRole.superadmin:
        raise PermissionDeniedError()

    group.deleted_at = datetime.now(UTC)
    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.group,
        entity_id=group.id,
        action=AuditAction.delete,
        actor_id=current_user.id,
    )
    await session.commit()
    await session.refresh(group)
    return group


async def restore_group(session: AsyncSession, group_id: uuid.UUID, superadmin: User) -> Group:
    group = await repository.get_by_id(session, group_id)
    if group is None:
        raise NotFoundError("Guruh topilmadi")
    if not group.is_deleted:
        raise BusinessRuleError("Bu guruh o'chirilmagan")

    group.deleted_at = None
    await audit_service.log_change(
        session,
        entity_type=AuditEntityType.group,
        entity_id=group.id,
        action=AuditAction.restore,
        actor_id=superadmin.id,
    )
    await session.commit()
    await session.refresh(group)
    return group


async def get_students(
    session: AsyncSession, group_id: uuid.UUID, viewer: User
) -> list[Enrollment]:
    """Guruhdagi o'quvchilar ro'yxati — teacher (o'ziniki), manager, superadmin."""
    group = await get_group(session, group_id)
    ensure_can_manage(group, viewer)
    return await enrollments_repository.list_for_group(
        session, group_id, statuses=(EnrollmentStatus.awaiting_payment, EnrollmentStatus.active)
    )


async def get_waitlist(
    session: AsyncSession, group_id: uuid.UUID, viewer: User
) -> list[Enrollment]:
    """Guruh navbati — teacher (o'ziniki), manager, superadmin ko'ra oladi."""
    group = await get_group(session, group_id)
    ensure_can_manage(group, viewer)
    return await enrollments_repository.list_waitlist(session, group_id)


def ensure_can_manage(group: Group, user: User) -> None:
    """Guruhni boshqarish huquqi: o'z guruhi bo'lgan teacher, manager yoki superadmin."""
    if user.role in (UserRole.manager, UserRole.superadmin):
        return
    if user.role == UserRole.teacher and group.teacher_id == user.id:
        return
    raise PermissionDeniedError("Bu guruhni boshqarish huquqingiz yo'q")


async def _apply_status_change(
    session: AsyncSession, group: Group, new_status: GroupStatus, current_user: User
) -> None:
    if current_user.role not in (UserRole.manager, UserRole.superadmin):
        raise PermissionDeniedError("Guruh holatini faqat manager yoki superadmin o'zgartiradi")
    if new_status == group.status:
        return
    allowed = ALLOWED_STATUS_TRANSITIONS.get(group.status, ())
    if new_status not in allowed:
        raise BusinessRuleError(
            f"'{group.status.value}' holatidan '{new_status.value}' holatiga o'tib bo'lmaydi"
        )
    group.status = new_status


async def _ensure_capacity_fits_existing_students(
    session: AsyncSession, group: Group, new_capacity: int
) -> None:
    """Sig'imni mavjud studentlar sonidan pastga tushirishga yo'l qo'yilmaydi."""
    occupied_seats = await enrollments_repository.count_occupied_seats(session, group.id)
    if new_capacity < occupied_seats:
        raise InvalidDataError(
            f"Sig'im {new_capacity} bo'la olmaydi — guruhda allaqachon {occupied_seats} o'quvchi bor"
        )
