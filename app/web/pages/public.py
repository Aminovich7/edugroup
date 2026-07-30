"""Ommaviy sahifalar: bosh sahifa (katalog), kurs va guruh tafsilotlari."""

import uuid

from fastapi import APIRouter, Request

from app.courses import service as courses_service
from app.enrollments import repository as enrollments_repository
from app.enrollments import service as enrollments_service
from app.groups import service as groups_service
from app.lessons import repository as lessons_repository
from app.users.models import UserRole
from app.web.dependencies import OptionalWebUser, WebSession
from app.web.form_fields import QueryDecimal, QueryText, QueryUuid
from app.web.helpers import render

router = APIRouter()


@router.get("/")
async def home_page(
    request: Request,
    session: WebSession,
    current_user: OptionalWebUser,
    subject: QueryText = None,
    max_price: QueryDecimal = None,
    teacher_id: QueryUuid = None,
):
    """Katalog: faol kurslar va guruhlar, fan/narx/teacher bo'yicha filtr bilan."""
    courses = await courses_service.list_active(session, subject=subject, teacher_id=teacher_id)
    if max_price is not None:
        courses = [course for course in courses if course.price <= max_price]

    course_ids = {course.id for course in courses}
    groups = await groups_service.list_active(session, subject=subject, teacher_id=teacher_id)
    group_cards = [
        {"group": group, "seats": await groups_service.get_seat_info(session, group)}
        for group in groups
        if not course_ids or group.course_id in course_ids
    ]

    return await render(
        request,
        "home.html",
        current_user=current_user,
        session=session,
        courses=courses,
        group_cards=group_cards,
        filters={"subject": subject or "", "max_price": max_price or "", "teacher_id": teacher_id or ""},
    )


@router.get("/courses/{course_id}")
async def course_detail_page(
    course_id: uuid.UUID,
    request: Request,
    session: WebSession,
    current_user: OptionalWebUser,
):
    course = await courses_service.get_course(session, course_id)
    groups = await groups_service.list_active(session, course_id=course_id)

    return await render(
        request,
        "post_detail.html",
        current_user=current_user,
        session=session,
        entity_type="course",
        course=course,
        groups=groups,
        can_edit=_can_edit_course(course, current_user),
    )


@router.get("/groups/{group_id}")
async def group_detail_page(
    group_id: uuid.UUID,
    request: Request,
    session: WebSession,
    current_user: OptionalWebUser,
):
    """Guruh sahifasi: to'lov qilgan student darslarni va video pleyerni ko'radi."""
    group = await groups_service.get_group(session, group_id)
    course = await courses_service.get_course(session, group.course_id)
    seats = await groups_service.get_seat_info(session, group)

    my_enrollment = None
    if current_user is not None and current_user.role == UserRole.student:
        my_enrollment = await enrollments_repository.get_open_enrollment(
            session, current_user.id, group_id
        )

    can_watch = False
    if current_user is not None:
        can_watch = await _can_watch_lessons(session, group, current_user)

    lessons = await lessons_repository.list_for_group(session, group_id) if can_watch else []
    watched_lesson_ids = set()
    if can_watch and current_user.role == UserRole.student:
        progress_records = await lessons_repository.list_progress_for_student(
            session, current_user.id
        )
        watched_lesson_ids = {record.lesson_id for record in progress_records if record.watched}

    return await render(
        request,
        "post_detail.html",
        current_user=current_user,
        session=session,
        entity_type="group",
        group=group,
        course=course,
        seats=seats,
        lessons=lessons,
        watched_lesson_ids=watched_lesson_ids,
        my_enrollment=my_enrollment,
        can_watch=can_watch,
        can_edit=_can_manage_group(group, current_user),
    )


def _can_edit_course(course, user) -> bool:
    if user is None:
        return False
    if user.role in (UserRole.manager, UserRole.superadmin):
        return True
    return user.role == UserRole.teacher and course.teacher_id == user.id


def _can_manage_group(group, user) -> bool:
    if user is None:
        return False
    if user.role in (UserRole.manager, UserRole.superadmin):
        return True
    return user.role == UserRole.teacher and group.teacher_id == user.id


async def _can_watch_lessons(session, group, user) -> bool:
    """Videoni faqat to'lovi tasdiqlangan student, guruh teacher'i va staff ko'radi."""
    if _can_manage_group(group, user):
        return True
    if user.role != UserRole.student:
        return False
    enrollment = await enrollments_service.get_active_enrollment(session, user.id, group.id)
    return enrollment is not None
