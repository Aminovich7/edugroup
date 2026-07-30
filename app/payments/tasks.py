"""Celery task: muddati o'tgan to'lov bo'laklarini belgilash.

Nima uchun periodic task, har so'rovda tekshirish emas: muddat o'tishi vaqtga
bog'liq hodisa. Agar buni har so'rovda tekshirsak, hech kim tizimga kirmagan
kunlarda bo'laklar umuman belgilanmay qolardi va bildirishnoma ham bormasdi.
"""

from app.core.celery_app import celery_app
from app.db.sync_session import sync_session_factory
from app.payments.service import flag_overdue_installments_sync


@celery_app.task(name="app.payments.tasks.flag_overdue_installments")
def flag_overdue_installments() -> int:
    """Kuniga bir marta ishga tushadi. Nechta bo'lak overdue bo'lganini qaytaradi."""
    session = sync_session_factory()
    try:
        return flag_overdue_installments_sync(session)
    finally:
        session.close()
