"""Ilova sozlamalari — barchasi .env faylidan o'qiladi."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_name: str = "EduGroup"

    # Ma'lumotlar bazasi.
    # database_url — FastAPI uchun async (asyncpg) ulanish.
    # sync_database_url — Celery task'lari va Alembic uchun sync (psycopg2) ulanish.
    database_url: str = "postgresql+asyncpg://edugroup:edugroup@db:5432/edugroup"
    sync_database_url: str = "postgresql+psycopg2://edugroup:edugroup@db:5432/edugroup"

    # JWT
    secret_key: str = "bu-kalitni-productionda-albatta-almashtiring"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Cookie — token brauzerda faqat httpOnly cookie ichida saqlanadi
    cookie_secure: bool = False

    # Redis — Celery broker/backend va rate-limit storage
    redis_url: str = "redis://redis:6379/0"

    # Fon vazifalar
    enrollment_request_expiry_hours: int = 72
    enrollment_expiry_check_interval_seconds: int = 3600
    overdue_installment_check_cron: str = "0 3 * * *"

    # Rate limit
    auth_rate_limit: str = "5/minute"

    # Ilova birinchi marta ishga tushganda yaratiladigan superadmin
    first_superadmin_email: str = "admin@edugroup.uz"
    first_superadmin_password: str = "admin12345"


@lru_cache
def get_settings() -> Settings:
    """Sozlamalar bir marta o'qiladi va keshlanadi."""
    return Settings()


settings = get_settings()
