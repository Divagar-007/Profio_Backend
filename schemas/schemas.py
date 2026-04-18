# schemas/schemas.py
# Pydantic v2 request/response models for API validation and serialisation

from __future__ import annotations
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from models.models import ConnectionStatus, NotificationType


# ── Token ─────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone_number: str
    password: str
    role: Optional[str] = None


    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str]      = None
    bio: Optional[str]       = None
    skills: Optional[str]    = None   # Comma-separated
    role: Optional[str]      = None
    phone_number: Optional[str] = None



class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone_number: Optional[str]
    bio: Optional[str]
    skills: Optional[str]
    role: Optional[str]
    profile_picture: Optional[str]
    banner_picture: Optional[str] = None

    created_at: datetime

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    """Lightweight user info returned in lists/connections."""
    id: int
    name: str
    role: Optional[str]
    profile_picture: Optional[str]
    banner_picture: Optional[str] = None
    connection_status: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Post ──────────────────────────────────────────────────────────────────────

class PostCreate(BaseModel):
    content: str


class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    content: str
    author: UserSummary
    created_at: datetime

    model_config = {"from_attributes": True}


class PostOut(BaseModel):
    id: int
    content: str
    image_url: Optional[str]
    author: UserSummary
    likes_count: int = 0
    comments: List[CommentOut] = []
    created_at: datetime
    liked_by_me: bool = False

    model_config = {"from_attributes": True}


# ── Job ───────────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    title: str
    description: str
    company: str
    location: Optional[str]   = None
    job_type: Optional[str]   = None
    skills: Optional[str]     = None   # Comma-separated required skills
    role: Optional[str]       = None
    salary_range: Optional[str] = None


class JobApplicationCreate(BaseModel):
    experience_years: Optional[int] = None
    portfolio_link: Optional[str]   = None
    note: Optional[str]             = None


class JobApplicationOut(BaseModel):
    id: int
    job_id: int
    applicant: UserSummary
    status: str
    experience_years: Optional[int]
    portfolio_link: Optional[str]
    note: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    title: str
    description: str
    company: str
    location: Optional[str]
    job_type: Optional[str]
    skills: Optional[str]
    role: Optional[str]
    salary_range: Optional[str]
    poster: UserSummary
    is_active: bool
    created_at: datetime
    applied_by_me: bool = False
    applications_count: int = 0

    model_config = {"from_attributes": True}


# ── Connection ────────────────────────────────────────────────────────────────

class ConnectionOut(BaseModel):
    id: int
    sender: UserSummary
    receiver: UserSummary
    status: ConnectionStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectionAction(BaseModel):
    action: str   # "accept" | "reject"


# ── Message ───────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    receiver_id: int
    content: str


class MessageOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Notification ──────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: int
    type: NotificationType
    message: str
    reference_id: Optional[int]
    is_read: bool
    actor_id: Optional[int]
    actor: Optional[UserSummary] = None
    created_at: datetime

    model_config = {"from_attributes": True}
