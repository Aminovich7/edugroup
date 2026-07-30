"""Celery task'lari uchun SYNC DB sessiya (psycopg2 drayveri).

Nima uchun alohida sessiya kerak: Celery worker oddiy sinxron process bo'lib
ishlaydi va asyncio event loop'ga ega emas, shuning uchun ilovaning asyncpg
sessiyasini ishlata olmaydi. Model klasslari esa drayverdan mustaqil —
xuddi shu modellar ikkala sessiya bilan ham ishlaydi.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

sync_engine = create_engine(settings.sync_database_url, echo=False, pool_pre_ping=True)

sync_session_factory = sessionmaker(bind=sync_engine, class_=Session, expire_on_commit=False)


@contextmanager
def sync_session_scope() -> Generator[Session, None, None]:
    """Celery task'lari uchun sessiya konteksti: xato bo'lsa rollback qiladi."""
    session = sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
