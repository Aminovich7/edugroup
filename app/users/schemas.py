"""Foydalanuvchi moduli uchun so'rov/javob sxemalari (Pydantic v2)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.users.models import UserRole, UserStatus


class StudentRegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=100)
    birth_date: date | None = None


class TeacherRegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=100)
    bio: str | None = None
    specialization: str | None = Field(default=None, max_length=100)
    experience_years: int = Field(default=0, ge=0, le=70)


class ManagerCreateRequest(BaseModel):
    """Superadmin manager akkauntini shu sxema orqali yaratadi (TZ 6.11)."""

    full_name: str = Field(min_length=3, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ProfileUpdateRequest(BaseModel):
    """PATCH /users/me — faqat yuborilgan maydonlar o'zgaradi."""

    full_name: str | None = Field(default=None, min_length=3, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    bio: str | None = None
    specialization: str | None = Field(default=None, max_length=100)
    experience_years: int | None = Field(default=None, ge=0, le=70)
    birth_date: date | None = None


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TeacherProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bio: str | None
    specialization: str | None
    experience_years: int
    approved_at: datetime | None


class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    birth_date: date | None
    approved_at: datetime | None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str | None
    role: UserRole
    status: UserStatus
    is_active: bool
    created_at: datetime


class UserDetailResponse(UserResponse):
    """Profil ma'lumotlari bilan birga to'liq foydalanuvchi."""

    teacher_profile: TeacherProfileResponse | None = None
    student_profile: StudentProfileResponse | None = None
