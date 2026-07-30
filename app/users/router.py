"""JSON API: /auth va /users endpointlari."""

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.core.cookies import REFRESH_TOKEN_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.dependencies import CurrentUser, SessionDep
from app.core.exceptions import NotAuthenticatedError
from app.core.rate_limit import AUTH_RATE_LIMIT, limiter
from app.users import service
from app.users.schemas import (
    LoginRequest,
    ProfileUpdateRequest,
    StudentRegisterRequest,
    TeacherRegisterRequest,
    TokenPairResponse,
    UserDetailResponse,
    UserResponse,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


class RefreshRequest(BaseModel):
    """Refresh token body'da yoki cookie'da kelishi mumkin."""

    refresh_token: str | None = None


@auth_router.post(
    "/register/student", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(AUTH_RATE_LIMIT)
async def register_student(request: Request, data: StudentRegisterRequest, session: SessionDep):
    return await service.register_student(session, data)


@auth_router.post(
    "/register/teacher", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(AUTH_RATE_LIMIT)
async def register_teacher(request: Request, data: TeacherRegisterRequest, session: SessionDep):
    return await service.register_teacher(session, data)


@auth_router.post("/login", response_model=TokenPairResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def login(request: Request, response: Response, data: LoginRequest, session: SessionDep):
    _, access_token, refresh_token = await service.login(
        session,
        email=data.email,
        password=data.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    set_auth_cookies(response, access_token, refresh_token)
    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


@auth_router.post("/refresh", response_model=TokenPairResponse)
async def refresh(request: Request, response: Response, data: RefreshRequest, session: SessionDep):
    token = data.refresh_token or request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not token:
        raise NotAuthenticatedError("Refresh token yuborilmadi")

    _, access_token, new_refresh_token = await service.refresh_token_pair(
        session,
        refresh_token=token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    set_auth_cookies(response, access_token, new_refresh_token)
    return TokenPairResponse(access_token=access_token, refresh_token=new_refresh_token)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    session: SessionDep,
    data: RefreshRequest | None = None,
):
    token = (data.refresh_token if data else None) or request.cookies.get(REFRESH_TOKEN_COOKIE)
    await service.logout(session, token)
    clear_auth_cookies(response)


@users_router.get("/me", response_model=UserDetailResponse)
async def get_me(current_user: CurrentUser, session: SessionDep):
    return await service.get_profile(session, current_user)


@users_router.patch("/me", response_model=UserDetailResponse)
async def update_me(data: ProfileUpdateRequest, current_user: CurrentUser, session: SessionDep):
    return await service.update_profile(session, current_user, data)
