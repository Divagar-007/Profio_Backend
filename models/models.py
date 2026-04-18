# models/models.py
# SQLAlchemy ORM models — defines all database tables and relationships

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, Table, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from database.db import Base


# ── Enumerations ──────────────────────────────────────────────────────────────

class ConnectionStatus(str, enum.Enum):
    pending  = "pending"
    accepted = "accepted"
    rejected = "rejected"


class NotificationType(str, enum.Enum):
    connection_request = "connection_request"
    connection_accepted = "connection_accepted"
    connection_rejected = "connection_rejected"
    new_message = "new_message"
    post_like = "post_like"
    post_comment = "post_comment"
    job_application = "job_application"


# ── Many-to-Many: Post Likes ───────────────────────────────────────────────────

post_likes = Table(
    "post_likes",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
)


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(120), nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    phone_number    = Column(String(20), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    bio             = Column(Text, nullable=True)

    skills          = Column(Text, nullable=True)          # Comma-separated list of skills
    role            = Column(String(120), nullable=True)   # e.g. "Software Engineer"
    profile_picture = Column(String(500), nullable=True)  # File path or URL
    banner_picture  = Column(String(500), nullable=True)  # File path or URL for cover photo
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    posts           = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    jobs            = relationship("Job",  back_populates="poster", cascade="all, delete-orphan")
    comments        = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    
    # FIXED: Added foreign_keys to specify which key to use for notifications
    notifications   = relationship(
        "Notification", 
        back_populates="recipient", 
        cascade="all, delete-orphan",
        foreign_keys="[Notification.recipient_id]"
    )

    # Connection relationships — handled via Connection model
    sent_connections     = relationship("Connection", foreign_keys="Connection.sender_id",   back_populates="sender")
    received_connections = relationship("Connection", foreign_keys="Connection.receiver_id", back_populates="receiver")

    # Messages
    sent_messages     = relationship("Message", foreign_keys="Message.sender_id",   back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")

    # Liked posts (many-to-many)
    liked_posts = relationship("Post", secondary=post_likes, back_populates="liked_by")


# ── Posts ─────────────────────────────────────────────────────────────────────

class Post(Base):
    __tablename__ = "posts"

    id         = Column(Integer, primary_key=True, index=True)
    content    = Column(Text, nullable=False)
    image_url  = Column(String(500), nullable=True)
    author_id  = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    author   = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    liked_by = relationship("User", secondary=post_likes, back_populates="liked_posts")


# ── Comments ──────────────────────────────────────────────────────────────────

class Comment(Base):
    __tablename__ = "comments"

    id         = Column(Integer, primary_key=True, index=True)
    content    = Column(Text, nullable=False)
    post_id    = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id  = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    post   = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")


# ── Jobs ──────────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String(255), nullable=False, index=True)
    description  = Column(Text, nullable=False)
    company      = Column(String(255), nullable=False)
    location     = Column(String(255), nullable=True)
    job_type     = Column(String(100), nullable=True)   # full-time, part-time, remote, etc.
    skills       = Column(Text, nullable=True)           # Comma-separated required skills
    role         = Column(String(120), nullable=True)    # Target role/position category
    salary_range = Column(String(100), nullable=True)
    poster_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    poster       = relationship("User", back_populates="jobs")
    applications = relationship("JobApplication", back_populates="job", cascade="all, delete-orphan")


# ── Job Applications ─────────────────────────────────────────────────────────

class JobApplication(Base):
    __tablename__ = "job_applications"

    id           = Column(Integer, primary_key=True, index=True)
    job_id       = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    applicant_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status           = Column(String(50), default="applied")  # applied, short-listed, etc.
    experience_years = Column(Integer, nullable=True)
    portfolio_link   = Column(String(500), nullable=True)
    note             = Column(Text, nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    job       = relationship("Job",  back_populates="applications")
    applicant = relationship("User")

class Connection(Base):
    __tablename__ = "connections"

    id          = Column(Integer, primary_key=True, index=True)
    sender_id   = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status      = Column(SAEnum(ConnectionStatus), default=ConnectionStatus.pending, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    sender   = relationship("User", foreign_keys=[sender_id],   back_populates="sent_connections")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_connections")


# ── Messages ──────────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id          = Column(Integer, primary_key=True, index=True)
    sender_id   = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content     = Column(Text, nullable=False)
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sender   = relationship("User", foreign_keys=[sender_id],   back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")


# ── Notifications ─────────────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id           = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    actor_id     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    type         = Column(SAEnum(NotificationType), nullable=False)
    message      = Column(String(500), nullable=False)
    reference_id = Column(Integer, nullable=True)   # ID of related object (post, connection, message)
    is_read      = Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="notifications")
    # Added actor relationship for completeness
    actor     = relationship("User", foreign_keys=[actor_id])