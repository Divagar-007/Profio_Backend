# routes/users.py
# User profile read, update, search, and profile-picture upload

import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database.db import get_db
from models.models import User, Connection, ConnectionStatus
from schemas.schemas import UserOut, UserUpdate, UserSummary
from utils.auth import get_current_user
from utils.cloudinary import upload_image, delete_image


router = APIRouter(prefix="/api/users", tags=["Users"])





# ── Current user ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's full profile."""
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update editable profile fields for the authenticated user."""
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=UserOut)
def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload / replace profile picture.
    Accepts JPEG and PNG only. Stores file on disk and saves path in DB.
    """
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WEBP images are allowed")

    # Save image locally
    try:
        image_url = upload_image(file.file, folder="avatars")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    # Delete old avatar if it exists locally
    if current_user.profile_picture:
        delete_image(current_user.profile_picture)

    current_user.profile_picture = image_url

    db.commit()
    db.refresh(current_user)
    return current_user



@router.post("/me/banner", response_model=UserOut)
def upload_banner(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload / replace banner (cover) picture.
    Accepts JPEG and PNG only. Stores file on disk and saves path in DB.
    """
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WEBP images are allowed")

    # Save image locally
    try:
        image_url = upload_image(file.file, folder="banners")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    # Delete old banner if it exists locally
    if current_user.banner_picture:
        delete_image(current_user.banner_picture)

    current_user.banner_picture = image_url

    db.commit()
    db.refresh(current_user)
    return current_user




# ── Public profiles ───────────────────────────────────────────────────────────

@router.get("/search", response_model=List[UserSummary])
def search_users(
    q: Optional[str]    = Query(None, description="Search by name, skills, or role"),
    skill: Optional[str] = Query(None),
    role: Optional[str]  = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search users by free-text query (searches name, skills, role),
    or filter explicitly by skill or role.
    """
    query = db.query(User).filter(User.is_active == True)

    if q:
        like = f"%{q}%"
        query = query.filter(
            User.name.ilike(like) |
            User.skills.ilike(like) |
            User.role.ilike(like)
        )
    if skill:
        query = query.filter(User.skills.ilike(f"%{skill}%"))
    if role:
        query = query.filter(User.role.ilike(f"%{role}%"))

    users = query.order_by(User.name).limit(50).all()

    if not users:
        return []

    # Efficiently fetch connection status for the returned users
    user_ids = [u.id for u in users]
    conns = db.query(Connection).filter(
        (
            (Connection.sender_id == current_user.id) & Connection.receiver_id.in_(user_ids)
        ) | (
            (Connection.receiver_id == current_user.id) & Connection.sender_id.in_(user_ids)
        )
    ).all()

    conn_map = {}
    for c in conns:
        other_id = c.receiver_id if c.sender_id == current_user.id else c.sender_id
        # Use value if it's an enum, otherwise the status itself
        status_val = c.status.value if hasattr(c.status, 'value') else str(c.status)
        conn_map[other_id] = status_val

    # Construct explicit results to ensure serialization of virtual fields
    results = []
    for u in users:
        # Get status and ensure it's a string if it exists
        raw_status = conn_map.get(u.id, None)
        status_str = str(raw_status) if raw_status else None
        
        results.append({
            "id": int(u.id),
            "name": str(u.name),
            "role": str(u.role) if u.role else None,
            "profile_picture": str(u.profile_picture) if u.profile_picture else None,
            "connection_status": status_str
        })

    return results


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Return a user's public profile by ID."""
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Mutual connections ────────────────────────────────────────────────────────

@router.get("/{user_id}/mutual", response_model=List[UserSummary])
def mutual_connections(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return users who are connected to both the current user and the target user."""

    def accepted_ids(uid: int) -> set:
        """Return a set of user IDs that are accepted connections of `uid`."""
        rows = db.query(Connection).filter(
            (
                (Connection.sender_id == uid) |
                (Connection.receiver_id == uid)
            ),
            Connection.status == ConnectionStatus.accepted,
        ).all()
        ids = set()
        for c in rows:
            ids.add(c.receiver_id if c.sender_id == uid else c.sender_id)
        return ids

    my_conns     = accepted_ids(current_user.id)
    their_conns  = accepted_ids(user_id)
    mutual_ids   = my_conns & their_conns

    if not mutual_ids:
        return []

    return db.query(User).filter(User.id.in_(mutual_ids)).all()
