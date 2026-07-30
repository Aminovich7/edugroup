"""Login, ro'yxatdan o'tish va chiqish sahifalari."""

from fastapi import APIRouter, Form, Request

from app.core.cookies import REFRESH_TOKEN_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.exceptions import AppError
from app.users import service as users_service
from app.users.schemas import StudentRegisterRequest, TeacherRegisterRequest
from app.web.dependencies import WebSession
from app.web.form_fields import FormDate, FormText
from app.web.helpers import dashboard_url_for, error_message, redirect_to, render

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    return await render(request, "login.html")


@router.post("/login")
async def login_submit(
    request: Request,
    session: WebSession,
    email: str = Form(...),
    password: str = Form(...),
):
    """Muvaffaqiyatli login: tokenlar httpOnly cookie'ga yoziladi."""
    try:
        user, access_token, refresh_token = await users_service.login(
            session,
            email=email,
            password=password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AppError as error:
        return redirect_to("/login", error=error_message(error))

    response = redirect_to(dashboard_url_for(user))
    set_auth_cookies(response, access_token, refresh_token)
    return response


@router.get("/register")
async def register_page(request: Request):
    return await render(request, "register.html")


@router.post("/register")
async def register_submit(
    request: Request,
    session: WebSession,
    role: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: FormText = None,
    birth_date: FormDate = None,
    specialization: FormText = None,
    experience_years: int = Form(default=0),
    bio: FormText = None,
):
    """Student yoki teacher sifatida ro'yxatdan o'tish — profil pending holatda bo'ladi."""
    try:
        if role == "teacher":
            await users_service.register_teacher(
                session,
                TeacherRegisterRequest(
                    full_name=full_name,
                    email=email,
                    password=password,
                    phone=phone,
                    bio=bio,
                    specialization=specialization,
                    experience_years=experience_years,
                ),
            )
        else:
            await users_service.register_student(
                session,
                StudentRegisterRequest(
                    full_name=full_name,
                    email=email,
                    password=password,
                    phone=phone,
                    birth_date=birth_date,
                ),
            )
    except (AppError, ValueError) as error:
        return redirect_to("/register", error=error_message(error))

    return redirect_to(
        "/login", message="Ro'yxatdan o'tdingiz. Profilingiz moderatsiyani kutmoqda."
    )


@router.post("/logout")
async def logout_submit(request: Request, session: WebSession):
    await users_service.logout(session, request.cookies.get(REFRESH_TOKEN_COOKIE))
    response = redirect_to("/", message="Tizimdan chiqdingiz")
    clear_auth_cookies(response)
    return response
