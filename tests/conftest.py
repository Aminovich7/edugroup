"""Testlar uchun umumiy fixture'lar.

Testlar alohida `edugroup_test` bazasida ishlaydi. Service qatlami har bir
amaldan keyin commit qilgani uchun "tranzaksiyani rollback qilish" usuli mos
kelmaydi — shuning uchun har bir testdan keyin jadvallar TRUNCATE qilinadi.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.all_models import Base
from app.db.session import get_session
from app.main import app
from app.users.models import User

TEST_DATABASE_NAME = "edugroup_test"

async_test_url = settings.database_url.rsplit("/", 1)[0] + f"/{TEST_DATABASE_NAME}"
sync_test_url = settings.sync_database_url.rsplit("/", 1)[0] + f"/{TEST_DATABASE_NAME}"

# NullPool: har bir test o'z event loop'ida ishlaydi, shuning uchun ulanishlar
# testlar orasida saqlanmasligi kerak (aks holda asyncpg "another operation is
# in progress" xatosini beradi).
test_engine = create_async_engine(async_test_url, poolclass=NullPool)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    """Test bazasini yaratadi va sxemani o'rnatadi."""
    _create_test_database_if_missing()

    sync_engine = create_engine(sync_test_url)
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)
    with sync_engine.begin() as connection:
        # Partial unique index modelda e'lon qilingan, lekin uni bu yerda ham
        # aniq yaratamiz — testlar aynan shu xatti-harakatni tekshiradi.
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_enrollment_active_per_group "
                "ON enrollments (student_id, group_id) "
                "WHERE status IN ('awaiting_payment', 'waitlisted', 'active')"
            )
        )
    yield
    sync_engine.dispose()


@pytest.fixture(autouse=True)
def disable_rate_limit():
    """Rate limit odatiy testlarga xalaqit bermasligi uchun o'chiriladi.

    Uni maxsus tekshiradigan test (test_rate_limit_login.py) o'zi qayta yoqadi.
    """
    limiter.enabled = False
    yield
    limiter.enabled = False


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Har bir testga toza sessiya; test tugagach jadvallar tozalanadi."""
    async with test_session_factory() as test_session:
        yield test_session

    async with test_engine.begin() as connection:
        table_names = ", ".join(table.name for table in reversed(Base.metadata.sorted_tables))
        await connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def sync_session():
    """Celery task'lari xuddi shunday sinxron sessiya bilan ishlaydi."""
    engine = create_engine(sync_test_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    test_session = session_factory()
    yield test_session
    test_session.close()
    engine.dispose()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Ilovaga to'g'ridan-to'g'ri murojaat qiladigan HTTP klient (server ko'tarilmaydi)."""

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(user: User) -> dict[str, str]:
    """Berilgan foydalanuvchi nomidan JSON API ga murojaat qilish uchun header."""
    token = create_access_token(user.id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def login_as(client: AsyncClient):
    """Web sahifalar uchun: cookie'ga access token qo'yadi."""

    def _login_as(user: User) -> None:
        client.cookies.set("access_token", create_access_token(user.id, user.role.value))

    return _login_as


def _create_test_database_if_missing() -> None:
    admin_engine = create_engine(settings.sync_database_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DATABASE_NAME},
        ).scalar()
        if not exists:
            connection.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))
    admin_engine.dispose()
