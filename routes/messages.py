# routes/messages.py
# REST endpoints for chat history + WebSocket for real-time messaging

import json
from typing import Dict, List, Set
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from database.db import get_db, SessionLocal
from models.models import Message, Connection, ConnectionStatus, Notification, NotificationType, User
from schemas.schemas import MessageOut
from utils.auth import get_current_user, decode_token

router = APIRouter(prefix="/api/messages", tags=["Messages"])


# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    """
    Tracks active WebSocket connections keyed by user_id.
    Supports sending messages to specific users.
    """

    def __init__(self):
        # user_id → set of active WebSocket connections
        self.active: Dict[int, Set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, user_id: int):
        await ws.accept()
        self.active.setdefault(user_id, set()).add(ws)

    def disconnect(self, ws: WebSocket, user_id: int):
        sockets = self.active.get(user_id, set())
        sockets.discard(ws)
        if not sockets:
            self.active.pop(user_id, None)

    async def send_to(self, user_id: int, payload: dict):
        """Send a JSON payload to all active connections of a user."""
        for ws in list(self.active.get(user_id, [])):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                pass  # Stale socket — ignore


manager = ConnectionManager()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    """
    Real-time chat WebSocket.
    Auth: pass JWT as ?token=<jwt> query param.
    Client sends: {"receiver_id": <int>, "content": "<text>"}
    Server broadcasts message to sender and receiver.
    """
    user_id = decode_token(token)
    if not user_id:
        await ws.close(code=4001)
        return

    await manager.connect(ws, user_id)
    db: Session = SessionLocal()

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
                receiver_id = int(data["receiver_id"])
                content     = str(data["content"]).strip()
            except (KeyError, ValueError, TypeError):
                await ws.send_text(json.dumps({"error": "Invalid message format"}))
                continue

            if not content:
                continue

            # Verify users are connected
            conn = db.query(Connection).filter(
                (
                    (Connection.sender_id == user_id) &
                    (Connection.receiver_id == receiver_id)
                ) | (
                    (Connection.sender_id == receiver_id) &
                    (Connection.receiver_id == user_id)
                ),
                Connection.status == ConnectionStatus.accepted,
            ).first()

            if not conn:
                await ws.send_text(json.dumps({"error": "You are not connected with this user"}))
                continue

            # Persist message
            msg = Message(sender_id=user_id, receiver_id=receiver_id, content=content)
            db.add(msg)

            # Create notification for receiver
            sender = db.query(User).filter(User.id == user_id).first()
            notif = Notification(
                recipient_id=receiver_id,
                actor_id=user_id,
                type=NotificationType.new_message,
                message=f"New message from {sender.name if sender else 'someone'}",
                reference_id=user_id,
            )
            db.add(notif)
            db.commit()
            db.refresh(msg)

            # Build payload to broadcast
            payload = {
                "type": "message",
                "id": msg.id,
                "sender_id": user_id,
                "receiver_id": receiver_id,
                "content": content,
                "created_at": msg.created_at.isoformat(),
            }

            # Echo to sender and deliver to receiver
            await manager.send_to(user_id,    payload)
            await manager.send_to(receiver_id, payload)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws, user_id)
        db.close()


from schemas.schemas import MessageOut, MessageCreate

@router.post("/", response_model=MessageOut)
async def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to another user via REST. 
    Useful for 'Share Post' functionality.
    """
    receiver_id = payload.receiver_id
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    # Verify users are connected (accepted status)
    conn = db.query(Connection).filter(
        (
            (Connection.sender_id == current_user.id) &
            (Connection.receiver_id == receiver_id)
        ) | (
            (Connection.sender_id == receiver_id) &
            (Connection.receiver_id == current_user.id)
        ),
        Connection.status == ConnectionStatus.accepted,
    ).first()

    if not conn:
        raise HTTPException(status_code=403, detail="You are not connected with this user")

    msg = Message(sender_id=current_user.id, receiver_id=receiver_id, content=content)
    db.add(msg)

    # Create notification for receiver
    notif = Notification(
        recipient_id=receiver_id,
        actor_id=current_user.id,
        type=NotificationType.new_message,
        message=f"New message from {current_user.name}",
        reference_id=current_user.id,
    )
    db.add(notif)
    db.commit()
    db.refresh(msg)

    # Broadcast via WebSocket for real-time delivery
    payload_dict = {
        "type": "message",
        "id": msg.id,
        "sender_id": current_user.id,
        "receiver_id": receiver_id,
        "content": content,
        "created_at": msg.created_at.isoformat(),
    }
    await manager.send_to(receiver_id, payload_dict)
    await manager.send_to(current_user.id, payload_dict)

    return msg


@router.get("/{user_id}", response_model=List[MessageOut])
def get_chat_history(
    user_id: int,
    skip: int  = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the message history between the current user and another user,
    ordered oldest-first. Also marks unread messages as read.
    """
    messages = (
        db.query(Message)
        .filter(
            (
                (Message.sender_id == current_user.id) &
                (Message.receiver_id == user_id)
            ) | (
                (Message.sender_id == user_id) &
                (Message.receiver_id == current_user.id)
            )
        )
        .order_by(Message.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Mark incoming messages as read
    for m in messages:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.commit()

    return messages


@router.get("/", response_model=List[dict])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return a summary of all conversations (one per unique chat partner),
    including the latest message and unread count.
    """
    # Get all messages involving the current user
    all_msgs = db.query(Message).filter(
        (Message.sender_id == current_user.id) |
        (Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.desc()).all()

    # Group by chat partner
    seen: set = set()
    conversations = []

    for msg in all_msgs:
        partner_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        if partner_id in seen:
            continue
        seen.add(partner_id)

        partner = db.query(User).filter(User.id == partner_id).first()
        unread = db.query(Message).filter(
            Message.sender_id == partner_id,
            Message.receiver_id == current_user.id,
            Message.is_read == False,
        ).count()

        conversations.append({
            "partner_id": partner_id,
            "partner_name": partner.name if partner else "Unknown",
            "partner_avatar": partner.profile_picture if partner else None,
            "last_message": msg.content,
            "last_message_at": msg.created_at.isoformat(),
            "unread_count": unread,
        })

    return conversations


@router.delete("/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a sent message."""
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this message")
        
    db.delete(msg)
    db.commit()
    return {"detail": "Message deleted"}
