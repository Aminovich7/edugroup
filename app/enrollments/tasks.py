"""Celery task: muddati o'tgan yozilishlarni bekor qilish.

Task'ning o'zi juda yupqa — butun mantiq `service.expire_stale_enrollments_sync()`
ichida va u oddiy `Session` qabul qiladi. Shu sababli testda brokerni ko'tarmasdan,
funksiyani to'g'ridan-to'g'ri chaqirib tekshirish mumkin.
"""

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.sync_session import sync_session_factory
from app.enrollments.service import expire_stale_enrollments_sync


@celery_app.task(name="app.enrollments.tasks.expire_stale_enrollments")
def expire_stale_enrollments() -> int:
    """Har soatda ishga tushadi. Nechta yozilish expired bo'lganini qaytaradi."""
    session = sync_session_factory()
    try:
        return expire_stale_enrollments_sync(
            session, settings.enrollment_request_expiry_hours
        )
    finally:
        session.close()
