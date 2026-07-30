"""Celery ilovasi va periodic task jadvali.

Celery bu loyihada faqat ikkita ishga ishlatiladi — ikkalasi ham vaqtga bog'liq
va bitta HTTP so'rov ichida bajarib bo'lmaydi:
  1) muddati o'tgan yozilishlarni bekor qilish (har soatda),
  2) muddati o'tgan to'lov bo'laklarini belgilash (kuniga bir marta).

Bildirishnoma va audit yozuvlari ATAYLAB Celery'ga chiqarilmagan — ular
oddiy DB yozuvi bo'lib, asosiy amal bilan bir tranzaksiyada saqlanishi kerak.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "edugroup",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.enrollments.tasks", "app.payments.tasks"],
)

celery_app.conf.timezone = "UTC"


def _parse_cron(expression: str) -> crontab:
    """"0 3 * * *" ko'rinishidagi qatorni Celery crontab jadvaliga o'giradi."""
    minute, hour, day_of_month, month_of_year, day_of_week = expression.split()
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


celery_app.conf.beat_schedule = {
    "expire-stale-enrollments": {
        "task": "app.enrollments.tasks.expire_stale_enrollments",
        "schedule": float(settings.enrollment_expiry_check_interval_seconds),
    },
    "flag-overdue-installments": {
        "task": "app.payments.tasks.flag_overdue_installments",
        "schedule": _parse_cron(settings.overdue_installment_check_cron),
    },
}
