"""Ilova birinchi marta ishga tushganda kerak bo'ladigan boshlang'ich ma'lumot.

Superadmin ro'yxatdan o'ta olmaydi va uni hech kim yarata olmaydi, shuning uchun
birinchi akkaunt .env dagi qiymatlar asosida shu yerda yaratiladi.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.users import repository
from app.users.models import User, UserRole, UserStatus


async def create_first_superadmin(session: AsyncSession) -> User | None:
    """Superadmin allaqachon mavjud bo'lsa — hech nima qilmaydi."""
    existing = await repository.get_by_email(session, settings.first_superadmin_email)
    if existing is not None:
        return existing

    superadmin = User(
        full_name="Superadmin",
        email=settings.first_superadmin_email,
        hashed_password=hash_password(settings.first_superadmin_password),
        role=UserRole.superadmin,
        status=UserStatus.approved,
        is_active=True,
    )
    session.add(superadmin)
    await session.commit()
    await session.refresh(superadmin)
    return superadmin
