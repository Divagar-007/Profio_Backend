# routes/posts.py
# CRUD for posts, likes, and comments

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import os, shutil, uuid

from database.db import get_db
from models.models import Post, Comment, User, Notification, NotificationType
from schemas.schemas import PostCreate, PostOut, CommentCreate, CommentOut
from utils.auth import get_current_user
from utils.cloudinary import upload_image, delete_image


router = APIRouter(prefix="/api/posts", tags=["Posts"])





def _build_post_out(post: Post, current_user_id: int) -> dict:
    """Helper to serialise a Post ORM object into PostOut-compatible dict."""
    return {
        "id": post.id,
        "content": post.content,
        "image_url": post.image_url,
        "author": post.author,
        "likes_count": len(post.liked_by),
        "comments": post.comments,
        "created_at": post.created_at,
        "liked_by_me": any(u.id == current_user_id for u in post.liked_by),
    }


# ── Feed ──────────────────────────────────────────────────────────────────────

@router.get("/feed", response_model=List[PostOut])
def get_feed(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all posts ordered by newest first (global feed)."""
    posts = (
        db.query(Post)
        .options(
            joinedload(Post.author),
            joinedload(Post.liked_by),
            joinedload(Post.comments).joinedload(Comment.author),
        )
        .order_by(Post.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_build_post_out(p, current_user.id) for p in posts]


@router.get("/{post_id}", response_model=PostOut)
def get_single_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single post with all its relationships."""
    post = (
        db.query(Post)
        .options(
            joinedload(Post.author),
            joinedload(Post.liked_by),
            joinedload(Post.comments).joinedload(Comment.author),
        )
        .filter(Post.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return _build_post_out(post, current_user.id)


# ── Create post ───────────────────────────────────────────────────────────────

@router.post("/", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new text post."""
    post = Post(content=payload.content, author_id=current_user.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    # Reload with relationships
    post = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.liked_by),
        joinedload(Post.comments).joinedload(Comment.author),
    ).filter(Post.id == post.id).first()
    return _build_post_out(post, current_user.id)


@router.post("/{post_id}/image")
def upload_post_image(
    post_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach an image to an existing post (must be the author)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your post")

    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Invalid image format")

    # Save image locally
    try:
        image_url = upload_image(file.file, folder="posts")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    # Delete old post image if it exists locally
    if post.image_url:
        delete_image(post.image_url)

    post.image_url = image_url
    db.commit()
    return _build_post_out(post, current_user.id)



# ── Like / Unlike ─────────────────────────────────────────────────────────────

@router.post("/{post_id}/like")
def toggle_like(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle like on a post. Returns current liked state."""
    post = db.query(Post).options(joinedload(Post.liked_by)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    already_liked = any(u.id == current_user.id for u in post.liked_by)

    if already_liked:
        post.liked_by = [u for u in post.liked_by if u.id != current_user.id]
        liked = False
    else:
        post.liked_by.append(current_user)
        liked = True

        # Notify post author (skip self-like)
        if post.author_id != current_user.id:
            notif = Notification(
                recipient_id=post.author_id,
                actor_id=current_user.id,
                type=NotificationType.post_like,
                message=f"{current_user.name} liked your post",
                reference_id=post_id,
            )
            db.add(notif)

    db.commit()
    return {"liked": liked, "likes_count": len(post.liked_by)}


# ── Comments ──────────────────────────────────────────────────────────────────

@router.post("/{post_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    post_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to a post."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comment = Comment(content=payload.content, post_id=post_id, author_id=current_user.id)
    db.add(comment)

    # Notify post author (skip self-comment)
    if post.author_id != current_user.id:
        notif = Notification(
            recipient_id=post.author_id,
            actor_id=current_user.id,
            type=NotificationType.post_comment,
            message=f"{current_user.name} commented on your post",
            reference_id=post_id,
        )
        db.add(notif)

    db.commit()
    db.refresh(comment)
    # Reload with author
    comment = db.query(Comment).options(joinedload(Comment.author)).filter(Comment.id == comment.id).first()
    return comment


@router.get("/{post_id}/comments", response_model=List[CommentOut])
def get_comments(post_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Return all comments for a post."""
    return (
        db.query(Comment)
        .options(joinedload(Comment.author))
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )


# ── Delete post ───────────────────────────────────────────────────────────────

@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a post (author only)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your post")
    db.delete(post)
    db.commit()


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a comment (author only)."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your comment")
    db.delete(comment)
    db.commit()

