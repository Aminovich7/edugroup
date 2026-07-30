"""Foydalanuvchi biznes-logikasi: ro'yxatdan o'tish, login, token rotatsiyasi,
moderatsiya va superadmin boshqaruvi.

Har bir service funksiyasi bitta biznes-amalni bajaradi va oxirida commit qiladi —
ya'ni bitta amal = bitta tranzaksiya. Shu sababli bildirishnoma yozuvi ham
asosiy o'zgarish bilan birga, atomik saqlanadi.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessRuleError,
    NotAuthenticatedError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.notifications import service as notifications_service
from app.notifications.models import NotificationType
from app.users import repository
from app.users.models import RefreshToken, StudentProfile, TeacherProfile, User, UserRole, UserStatus
from app.users.schemas import (
    ManagerCreateRequest,
    ProfileUpdateRequest,
    StudentRegisterRequest,
    TeacherRegisterRequest,
)


# --- Ro'yxatdan o'tish -------------------------------------------------------


async def register_student(session: AsyncSession, data: StudentRegisterRequest) -> User:
    """Student ro'yxatdan o'tadi va manager tasdig'ini kutadi (status=pending)."""
    await _ensure_email_is_free(session, data.email)

    user = User(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        hashed_password=hash_password(data.password),
        role=UserRole.student,
        status=UserStatus.pending,
    )
    session.add(user)
    await session.flush()

    session.add(StudentProfile(user_id=user.id, birth_date=data.birth_date))
    await session.commit()
    await session.refresh(user)
    return user


async def register_teacher(session: AsyncSession, data: TeacherRegisterRequest) -> User:
    """Teacher ro'yxatdan o'tadi va manager tasdig'ini kutadi (status=pending)."""
    await _ensure_email_is_free(session, data.email)

    user = User(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        hashed_password=hash_password(data.password),
        role=UserRole.teacher,
        status=UserStatus.pending,
    )
    session.add(user)
    await session.flush()

    session.add(
        TeacherProfile(
            user_id=user.id,
            bio=data.bio,
            specialization=data.specialization,
            experience_years=data.experience_years,
        )
    )
    await session.commit()
    await session.refresh(user)
    return user


# --- Login / token oqimi -----------------------------------------------------


async def login(
    session: AsyncSession,
    email: str,
    password: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[User, str, str]:
    """Email/parolni tekshiradi va (foydalanuvchi, access, refresh) qaytaradi."""
    user = await repository.get_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise NotAuthenticatedError("Email yoki parol noto'g'ri")
    _ensure_user_is_not_blocked(user)

    access_token = create_access_token(user.id, user.role.value)
    refresh_token = await _issue_refresh_token(session, user.id, user_agent, ip_address)
    await session.commit()
    return user, access_token, refresh_token


async def refresh_token_pair(
    session: AsyncSession,
    refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[User, str, str]:
    """Refresh tokenni rotatsiya qiladi: eskisi bekor qilinib, yangisi beriladi.

    Agar allaqachon bekor qilingan token qayta ishlatilsa — bu token o'g'irlangan
    degan belgi, shuning uchun foydalanuvchining BARCHA tokenlari bekor qilinadi.
    """
    payload = decode_token(refresh_token, REFRESH_TOKEN_TYPE)
    if payload is None:
        raise NotAuthenticatedError("Refresh token yaroqsiz yoki muddati o'tgan")

    token_hash = hash_refresh_token(refresh_token)
    stored_token = await repository.get_refresh_token(session, token_hash)
    if stored_token is None:
        raise NotAuthenticatedError("Refresh token topilmadi")

    if stored_token.revoked:
        await repository.revoke_all_refresh_tokens(session, stored_token.user_id)
        await session.commit()
        raise NotAuthenticatedError(
            "Refresh token qayta ishlatildi — barcha sessiyalar yopildi, qayta kiring"
        )

    user = await repository.get_by_id(session, stored_token.user_id)
    if user is None:
        raise NotAuthenticatedError("Foydalanuvchi topilmadi")
    _ensure_user_is_not_blocked(user)

    new_refresh_token = await _issue_refresh_token(session, user.id, user_agent, ip_address)
    stored_token.revoked = True
    stored_token.replaced_by_token_hash = hash_refresh_token(new_refresh_token)

    access_token = create_access_token(user.id, user.role.value)
    await session.commit()
    return user, access_token, new_refresh_token


async def logout(session: AsyncSession, refresh_token: str | None) -> None:
    """Joriy refresh tokenni bekor qiladi. Token yo'q bo'lsa ham xato bermaydi."""
    if not refresh_token:
        return
    stored_token = await repository.get_refresh_token(session, hash_refresh_token(refresh_token))
    if stored_token is not None:
        stored_token.revoked = True
        await session.commit()


# --- Profil ------------------------------------------------------------------


async def get_profile(session: AsyncSession, current_user: User) -> User:
    """Joriy foydalanuvchi profili (teacher/student profili bilan birga)."""
    user = await repository.get_by_id(session, current_user.id)
    if user is None:
        raise NotFoundError("Foydalanuvchi topilmadi")
    return user


async def update_profile(
    session: AsyncSession, current_user: User, data: ProfileUpdateRequest
) -> User:
    """Faqat yuborilgan maydonlarni yangilaydi (rolga mos profil maydonlari bilan)."""
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.phone is not None:
        current_user.phone = data.phone

    if current_user.role == UserRole.teacher:
        profile = await repository.get_teacher_profile(session, current_user.id)
        if profile is not None:
            if data.bio is not None:
                profile.bio = data.bio
            if data.specialization is not None:
                profile.specialization = data.specialization
            if data.experience_years is not None:
                profile.experience_years = data.experience_years

    if current_user.role == UserRole.student:
        profile = await repository.get_student_profile(session, current_user.id)
        if profile is not None and data.birth_date is not None:
            profile.birth_date = data.birth_date

    await session.commit()
    await session.refresh(current_user)
    return current_user


# --- Manager moderatsiyasi ---------------------------------------------------


async def list_users(
    session: AsyncSession,
    role: UserRole | None = None,
    status: UserStatus | None = None,
) -> list[User]:
    return await repository.list_users(session, role=role, status=status)


async def approve_user(session: AsyncSession, user_id: uuid.UUID, moderator: User) -> User:
    """Manager student yoki teacher profilini tasdiqlaydi."""
    user = await _get_moderatable_user(session, user_id)

    user.status = UserStatus.approved
    await _set_profile_approval(session, user, moderator.id)
    await notifications_service.create_notification(
        session,
        user_id=user.id,
        notification_type=NotificationType.profile_approved,
        title="Profilingiz tasdiqlandi",
        message="Endi platformadan to'liq foydalanishingiz mumkin.",
        related_entity_type="user",
        related_entity_id=user.id,
    )
    await session.commit()
    await session.refresh(user)
    return user


async def reject_user(
    session: AsyncSession, user_id: uuid.UUID, moderator: User, reason: str
) -> User:
    """Manager profilni sabab bilan rad etadi."""
    user = await _get_moderatable_user(session, user_id)

    user.status = UserStatus.rejected
    await notifications_service.create_notification(
        session,
        user_id=user.id,
        notification_type=NotificationType.profile_rejected,
        title="Profilingiz rad etildi",
        message=f"Sabab: {reason}",
        related_entity_type="user",
        related_entity_id=user.id,
    )
    await session.commit()
    await session.refresh(user)
    return user


# --- Superadmin: manager yaratish va blokirovka (TZ 6.11) --------------------


async def create_manager(session: AsyncSession, data: ManagerCreateRequest) -> User:
    """Manager akkaunti faqat superadmin orqali yaratiladi — moderatsiyasiz."""
    await _ensure_email_is_free(session, data.email)

    manager = User(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        hashed_password=hash_password(data.password),
        role=UserRole.manager,
        status=UserStatus.approved,
        is_active=True,
    )
    session.add(manager)
    await session.commit()
    await session.refresh(manager)
    return manager


async def list_managers(session: AsyncSession) -> list[User]:
    return await repository.list_users(session, role=UserRole.manager)


async def block_user(session: AsyncSession, user_id: uuid.UUID, superadmin: User) -> User:
    """Foydalanuvchini bloklaydi va uning barcha sessiyalarini yopadi."""
    if user_id == superadmin.id:
        raise BusinessRuleError("O'zingizni bloklay olmaysiz")

    user = await repository.get_by_id(session, user_id)
    if user is None:
        raise NotFoundError("Foydalanuvchi topilmadi")
    if user.role == UserRole.superadmin:
        raise BusinessRuleError("Superadminni bloklab bo'lmaydi")

    user.status = UserStatus.blocked
    user.is_active = False
    await repository.revoke_all_refresh_tokens(session, user.id)
    await notifications_service.create_notification(
        session,
        user_id=user.id,
        notification_type=NotificationType.account_blocked,
        title="Akkaunt bloklandi",
        message="Akkauntingiz administrator tomonidan bloklandi.",
        related_entity_type="user",
        related_entity_id=user.id,
    )
    await session.commit()
    await session.refresh(user)
    return user


async def unblock_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """Blokdan chiqaradi — status yana approved bo'ladi."""
    user = await repository.get_by_id(session, user_id)
    if user is None:
        raise NotFoundError("Foydalanuvchi topilmadi")
    if user.status != UserStatus.blocked:
        raise BusinessRuleError("Bu foydalanuvchi bloklanmagan")

    user.status = UserStatus.approved
    user.is_active = True
    await notifications_service.create_notification(
        session,
        user_id=user.id,
        notification_type=NotificationType.account_unblocked,
        title="Akkaunt blokdan chiqarildi",
        message="Akkauntingiz qayta faollashtirildi.",
        related_entity_type="user",
        related_entity_id=user.id,
    )
    await session.commit()
    await session.refresh(user)
    return user


# --- Ichki yordamchi funksiyalar --------------------------------------------


async def _ensure_email_is_free(session: AsyncSession, email: str) -> None:
    if await repository.get_by_email(session, email) is not None:
        raise BusinessRuleError("Bu email allaqachon ro'yxatdan o'tgan")


def _ensure_user_is_not_blocked(user: User) -> None:
    if user.status == UserStatus.blocked or not user.is_active:
        raise PermissionDeniedError("Akkaunt bloklangan")


async def _get_moderatable_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """Moderatsiya faqat student va teacher uchun mantiqiy."""
    user = await repository.get_by_id(session, user_id)
    if user is None:
        raise NotFoundError("Foydalanuvchi topilmadi")
    if user.role not in (UserRole.student, UserRole.teacher):
        raise BusinessRuleError("Faqat student va teacher profillari moderatsiya qilinadi")
    return user


async def _set_profile_approval(
    session: AsyncSession, user: User, moderator_id: uuid.UUID
) -> None:
    profile = (
        await repository.get_teacher_profile(session, user.id)
        if user.role == UserRole.teacher
        else await repository.get_student_profile(session, user.id)
    )
    if profile is not None:
        profile.approved_by = moderator_id
        profile.approved_at = datetime.now(UTC)


async def _issue_refresh_token(
    session: AsyncSession,
    user_id: uuid.UUID,
    user_agent: str | None,
    ip_address: str | None,
) -> str:
    """Yangi refresh token yaratadi va uning hash'ini bazaga yozadi."""
    token, expires_at = create_refresh_token(user_id)
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            issued_at=datetime.now(UTC),
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    await session.flush()
    return token
