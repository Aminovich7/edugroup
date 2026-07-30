"""FastAPI ilovasi: JSON API va Jinja2 SSR sahifalar bitta ilovada.

JSON API `/api` prefiksi ostida turadi, veb-sahifalar esa ildizdan boshlanadi
(`/`, `/login`, `/dashboard`, ...). Ikkalasi bir xil `service.py` funksiyalarini
chaqiradi — biznes-logika hech qayerda takrorlanmaydi.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi.middleware import SlowAPIMiddleware

from app.audit.router import router as audit_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import limiter
from app.courses.router import router as courses_router
from app.db.session import async_session_factory
from app.enrollments.router import router as enrollments_router
from app.groups.router import router as groups_router
from app.lessons.router import group_lessons_router, router as lessons_router
from app.manager.router import router as manager_router
from app.notifications.router import router as notifications_router
from app.payments.router import plan_router as payment_plan_router, router as payments_router
from app.reports.router import router as reports_router
from app.superadmin.router import router as superadmin_router
from app.templating import templates
from app.users.bootstrap import create_first_superadmin
from app.users.router import auth_router, users_router
from app.web.router import router as web_router

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ilova ishga tushganda birinchi superadmin akkaunti tayyorlanadi."""
    async with async_session_factory() as session:
        await create_first_superadmin(session)
    yield


app = FastAPI(title=settings.project_name, version="2.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")
register_exception_handlers(app, templates)

# JSON API — tashqi klientlar va testlar uchun.
for api_router in (
    auth_router,
    users_router,
    courses_router,
    groups_router,
    lessons_router,
    group_lessons_router,
    enrollments_router,
    payments_router,
    payment_plan_router,
    notifications_router,
    audit_router,
    manager_router,
    superadmin_router,
    reports_router,
):
    app.include_router(api_router, prefix=API_PREFIX)

# Jinja2 SSR sahifalar.
app.include_router(web_router)


@app.get("/health", tags=["service"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
