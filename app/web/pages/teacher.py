"""Teacher sahifasi: kurs/guruh/dars yaratish, tahrirlash va o'quvchilar progressi."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Form, Request

from app.core.exceptions import AppError
from app.courses import service as courses_service
from app.courses.schemas import CourseCreateRequest, CourseUpdateRequest
from app.groups import service as groups_service
from app.groups.models import GroupStatus
from app.groups.schemas import GroupCreateRequest, GroupUpdateRequest
from app.lessons import repository as lessons_repository
from app.lessons import service as lessons_service
from app.lessons.schemas import LessonCreateRequest, LessonUpdateRequest
from app.notifications import service as notifications_service
from app.users.models import UserRole
from app.web.dependencies import CurrentWebUser, WebSession
from app.web.form_fields import FormText
from app.web.helpers import error_message, redirect_to, render

router = APIRouter()

TEACHER_DASHBOARD_URL = "/dashboard/teacher"


@router.get("/dashboard/teacher")
async def teacher_dashboard(
    request: Request, session: WebSession, current_user: CurrentWebUser
):
    """Kurslarim, guruhlarim, har bir guruhning o'quvchilari, navbati va progressi."""
    courses = await courses_service.list_mine(session, current_user)
    groups = await groups_service.list_mine(session, current_user)

    group_cards = []
    for group in groups:
        group_cards.append(
            {
                "group": group,
                "students": await groups_service.get_students(session, group.id, current_user),
                "waitlist": await groups_service.get_waitlist(session, group.id, current_user),
                "progress": await lessons_service.get_group_progress(
                    session, group.id, current_user
                ),
                "lessons": await lessons_repository.list_for_group(session, group.id),
            }
        )

    return await render(
        request,
        "dashboard/teacher.html",
        current_user=current_user,
        session=session,
        courses=courses,
        group_cards=group_cards,
        notifications=await notifications_service.list_my_notifications(session, current_user),
    )


# --- Yaratish formalari ------------------------------------------------------


@router.post("/web/courses")
async def create_course_submit(
    session: WebSession,
    current_user: CurrentWebUser,
    title: str = Form(...),
    subject: str = Form(...),
    price: Decimal = Form(...),
    description: FormText = None,
):
    try:
        await courses_service.create_course(
            session,
            CourseCreateRequest(
                title=title, subject=subject, price=price, description=description
            ),
            current_user,
        )
    except (AppError, ValueError) as error:
        return redirect_to(TEACHER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(TEACHER_DASHBOARD_URL, message="Kurs yaratildi (draft holatda)")


@router.post("/web/groups")
async def create_group_submit(
    session: WebSession,
    current_user: CurrentWebUser,
    course_id: uuid.UUID = Form(...),
    name: str = Form(...),
    capacity: int = Form(...),
    schedule: str = Form(...),
):
    try:
        await groups_service.create_group(
            session,
            GroupCreateRequest(
                course_id=course_id, name=name, capacity=capacity, schedule=schedule
            ),
            current_user,
        )
    except (AppError, ValueError) as error:
        return redirect_to(TEACHER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(
        TEACHER_DASHBOARD_URL, message="Guruh yaratildi — manager tasdiqlashini kuting"
    )


@router.post("/web/lessons")
async def create_lesson_submit(
    session: WebSession,
    current_user: CurrentWebUser,
    group_id: uuid.UUID = Form(...),
    title: str = Form(...),
    kinescope_video_id: str = Form(...),
    kinescope_url: str = Form(...),
    duration_seconds: int = Form(...),
    order_index: int = Form(default=1),
    description: FormText = None,
):
    try:
        await lessons_service.create_lesson(
            session,
            group_id,
            LessonCreateRequest(
                title=title,
                description=description,
                kinescope_video_id=kinescope_video_id,
                kinescope_url=kinescope_url,
                duration_seconds=duration_seconds,
                order_index=order_index,
            ),
            current_user,
        )
    except (AppError, ValueError) as error:
        return redirect_to(TEACHER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(TEACHER_DASHBOARD_URL, message="Dars qo'shildi")


# --- Tahrirlash formalari ----------------------------------------------------


@router.get("/web/courses/{course_id}/edit")
async def course_edit_page(
    course_id: uuid.UUID, request: Request, session: WebSession, current_user: CurrentWebUser
):
    course = await courses_service.get_course(session, course_id)
    return await render(
        request,
        "edit_form.html",
        current_user=current_user,
        session=session,
        entity_type="course",
        course=course,
    )


@router.post("/web/courses/{course_id}/edit")
async def course_edit_submit(
    course_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    title: str = Form(...),
    subject: str = Form(...),
    price: Decimal = Form(...),
    status: str = Form(...),
    description: FormText = None,
):
    try:
        await courses_service.update_course(
            session,
            course_id,
            CourseUpdateRequest(
                title=title,
                subject=subject,
                price=price,
                status=status,
                description=description,
            ),
            current_user,
        )
    except (AppError, ValueError) as error:
        return redirect_to(f"/web/courses/{course_id}/edit", error=error_message(error))
    return redirect_to(f"/courses/{course_id}", message="Kurs yangilandi")


@router.get("/web/groups/{group_id}/edit")
async def group_edit_page(
    group_id: uuid.UUID, request: Request, session: WebSession, current_user: CurrentWebUser
):
    group = await groups_service.get_group(session, group_id)
    groups_service.ensure_can_manage(group, current_user)
    return await render(
        request,
        "edit_form.html",
        current_user=current_user,
        session=session,
        entity_type="group",
        group=group,
        can_change_status=current_user.role in (UserRole.manager, UserRole.superadmin),
        status_options=[GroupStatus.closed.value, GroupStatus.archived.value],
    )


@router.post("/web/groups/{group_id}/edit")
async def group_edit_submit(
    group_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    name: str = Form(...),
    capacity: int = Form(...),
    schedule: str = Form(...),
    status: FormText = None,
):
    try:
        await groups_service.update_group(
            session,
            group_id,
            GroupUpdateRequest(
                name=name, capacity=capacity, schedule=schedule, status=status
            ),
            current_user,
        )
    except (AppError, ValueError) as error:
        return redirect_to(f"/web/groups/{group_id}/edit", error=error_message(error))
    return redirect_to(f"/groups/{group_id}", message="Guruh yangilandi")


@router.get("/web/lessons/{lesson_id}/edit")
async def lesson_edit_page(
    lesson_id: uuid.UUID, request: Request, session: WebSession, current_user: CurrentWebUser
):
    lesson = await lessons_service.get_lesson(session, lesson_id, current_user)
    return await render(
        request,
        "edit_form.html",
        current_user=current_user,
        session=session,
        entity_type="lesson",
        lesson=lesson,
    )


@router.post("/web/lessons/{lesson_id}/edit")
async def lesson_edit_submit(
    lesson_id: uuid.UUID,
    session: WebSession,
    current_user: CurrentWebUser,
    title: str = Form(...),
    kinescope_video_id: str = Form(...),
    kinescope_url: str = Form(...),
    duration_seconds: int = Form(...),
    order_index: int = Form(...),
    description: FormText = None,
):
    try:
        lesson = await lessons_service.update_lesson(
            session,
            lesson_id,
            LessonUpdateRequest(
                title=title,
                description=description,
                kinescope_video_id=kinescope_video_id,
                kinescope_url=kinescope_url,
                duration_seconds=duration_seconds,
                order_index=order_index,
            ),
            current_user,
        )
    except (AppError, ValueError) as error:
        return redirect_to(f"/web/lessons/{lesson_id}/edit", error=error_message(error))
    return redirect_to(f"/groups/{lesson.group_id}", message="Dars yangilandi")


# --- O'chirish (soft delete) -------------------------------------------------


@router.post("/web/courses/{course_id}/delete")
async def delete_course_submit(
    course_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    try:
        await courses_service.soft_delete_course(session, course_id, current_user)
    except AppError as error:
        return redirect_to(TEACHER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(TEACHER_DASHBOARD_URL, message="Kurs o'chirildi")


@router.post("/web/groups/{group_id}/delete")
async def delete_group_submit(
    group_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    try:
        await groups_service.soft_delete_group(session, group_id, current_user)
    except AppError as error:
        return redirect_to(TEACHER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(TEACHER_DASHBOARD_URL, message="Guruh o'chirildi")


@router.post("/web/lessons/{lesson_id}/delete")
async def delete_lesson_submit(
    lesson_id: uuid.UUID, session: WebSession, current_user: CurrentWebUser
):
    try:
        await lessons_service.soft_delete_lesson(session, lesson_id, current_user)
    except AppError as error:
        return redirect_to(TEACHER_DASHBOARD_URL, error=error_message(error))
    return redirect_to(TEACHER_DASHBOARD_URL, message="Dars o'chirildi")
