"""Testlar uchun tayyor obyektlar yaratuvchi yordamchi funksiyalar."""

import itertools
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.courses.models import Course, CourseStatus
from app.enrollments.models import Enrollment, EnrollmentStatus
from app.groups.models import Group, GroupStatus
from app.lessons.models import Lesson
from app.users.models import StudentProfile, TeacherProfile, User, UserRole, UserStatus

_email_counter = itertools.count(1)

DEFAULT_PASSWORD = "parol12345"


async def create_user(
    session: AsyncSession,
    role: UserRole,
    status: UserStatus = UserStatus.approved,
    full_name: str = "Test Foydalanuvchi",
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
    is_active: bool = True,
) -> User:
    user = User(
        full_name=full_name,
        email=email or f"user{next(_email_counter)}@test.uz",
        hashed_password=hash_password(password),
        role=role,
        status=status,
        is_active=is_active,
    )
    session.add(user)
    await session.flush()

    if role == UserRole.teacher:
        session.add(TeacherProfile(user_id=user.id, specialization="Matematika"))
    elif role == UserRole.student:
        session.add(StudentProfile(user_id=user.id))

    await session.commit()
    await session.refresh(user)
    return user


async def create_student(session: AsyncSession, **kwargs) -> User:
    return await create_user(session, UserRole.student, **kwargs)


async def create_teacher(session: AsyncSession, **kwargs) -> User:
    return await create_user(session, UserRole.teacher, **kwargs)


async def create_manager(session: AsyncSession, **kwargs) -> User:
    return await create_user(session, UserRole.manager, **kwargs)


async def create_superadmin(session: AsyncSession, **kwargs) -> User:
    return await create_user(session, UserRole.superadmin, **kwargs)


async def create_course(
    session: AsyncSession,
    teacher: User,
    title: str = "Ingliz tili — Elementary",
    subject: str = "Ingliz tili",
    price: Decimal = Decimal("500000.00"),
    status: CourseStatus = CourseStatus.active,
) -> Course:
    course = Course(
        teacher_id=teacher.id,
        title=title,
        subject=subject,
        price=price,
        status=status,
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


async def create_group(
    session: AsyncSession,
    course: Course,
    teacher: User,
    name: str = "Guruh A",
    capacity: int = 10,
    schedule: str = "Dush, Chor 18:00",
    status: GroupStatus = GroupStatus.active,
    approved_by: User | None = None,
) -> Group:
    group = Group(
        course_id=course.id,
        teacher_id=teacher.id,
        name=name,
        capacity=capacity,
        schedule=schedule,
        status=status,
        approved_by=approved_by.id if approved_by else None,
        approved_at=datetime.now(UTC) if approved_by else None,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def create_lesson(
    session: AsyncSession,
    group: Group,
    title: str = "1-dars: Tanishuv",
    duration_seconds: int = 420,
    order_index: int = 1,
) -> Lesson:
    lesson = Lesson(
        group_id=group.id,
        title=title,
        kinescope_video_id="abc123",
        kinescope_url="https://kinescope.io/abc123",
        duration_seconds=duration_seconds,
        order_index=order_index,
    )
    session.add(lesson)
    await session.commit()
    await session.refresh(lesson)
    return lesson


async def create_enrollment(
    session: AsyncSession,
    student: User,
    group: Group,
    status: EnrollmentStatus = EnrollmentStatus.awaiting_payment,
    waitlist_position: int | None = None,
    requested_at: datetime | None = None,
) -> Enrollment:
    enrollment = Enrollment(
        student_id=student.id,
        group_id=group.id,
        status=status,
        requested_at=requested_at or datetime.now(UTC),
        waitlist_position=waitlist_position,
        activated_at=datetime.now(UTC) if status == EnrollmentStatus.active else None,
    )
    session.add(enrollment)
    await session.commit()
    await session.refresh(enrollment)
    return enrollment
