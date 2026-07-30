"""SQLAlchemy declarative Base.

Bu fayl ATAYLAB hech qanday model import qilmaydi. Aks holda aylanma import
yuzaga kelardi: `courses/models.py` -> `db/base.py` -> `groups/models.py` ->
`courses/models.py` (hali to'liq yuklanmagan) -> ImportError.

Barcha modellarni bir joyda ro'yxatdan o'tkazish kerak bo'lganda (Alembic,
testlarda `Base.metadata.create_all`) `app.db.all_models` import qilinadi.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
