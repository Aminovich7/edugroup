"""Barcha veb-sahifa routerlarini bitta routerga yig'adi."""

from fastapi import APIRouter

from app.web.pages import account, auth, manager, public, student, superadmin, teacher

router = APIRouter(include_in_schema=False)

for page_router in (
    public.router,
    auth.router,
    account.router,
    student.router,
    teacher.router,
    manager.router,
    superadmin.router,
):
    router.include_router(page_router)
