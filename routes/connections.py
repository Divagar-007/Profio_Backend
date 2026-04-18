# routes/connections.py
# Send, accept, reject connection requests and list connections

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List

from database.db import get_db
from models.models import Connection, ConnectionStatus, User, Notification, NotificationType
from schemas.schemas import ConnectionOut, ConnectionAction
from utils.auth import get_current_user

router = APIRouter(prefix="/api/connections", tags=["Connections"])


def _get_connection(db: Session, user_a: int, user_b: int) -> Connection | None:
    """Return the Connection row between two users (regardless of direction)."""
    return db.query(Connection).filter(
        (
            (Connection.sender_id == user_a) & (Connection.receiver_id == user_b)
        ) | (
            (Connection.sender_id == user_b) & (Connection.receiver_id == user_a)
        )
    ).first()


@router.post("/{user_id}", response_model=ConnectionOut, status_code=201)
def send_request(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a connection request to another user."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot connect to yourself")

    target = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = _get_connection(db, current_user.id, user_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Connection already exists (status: {existing.status})")

    conn = Connection(sender_id=current_user.id, receiver_id=user_id)
    db.add(conn)

    # Notify the receiver
    notif = Notification(
        recipient_id=user_id,
        actor_id=current_user.id,
        type=NotificationType.connection_request,
        message=f"{current_user.name} sent you a connection request",
        reference_id=current_user.id,
    )
    db.add(notif)
    db.commit()
    db.refresh(conn)

    return db.query(Connection).options(
        joinedload(Connection.sender), joinedload(Connection.receiver)
    ).filter(Connection.id == conn.id).first()


@router.put("/{connection_id}", response_model=ConnectionOut)
def respond_to_request(
    connection_id: int,
    payload: ConnectionAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept or reject an incoming connection request."""
    conn = db.query(Connection).options(
        joinedload(Connection.sender), joinedload(Connection.receiver)
    ).filter(Connection.id == connection_id).first()

    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    if conn.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your request to respond to")
    if conn.status != ConnectionStatus.pending:
        raise HTTPException(status_code=400, detail="Request already handled")

    if payload.action == "accept":
        conn.status = ConnectionStatus.accepted
        # Notify the original sender
        notif = Notification(
            recipient_id=conn.sender_id,
            actor_id=current_user.id,
            type=NotificationType.connection_accepted,
            message=f"{current_user.name} accepted your connection request",
            reference_id=current_user.id,
        )
        db.add(notif)
    elif payload.action == "reject":
        conn.status = ConnectionStatus.rejected
        # Notify the original sender
        notif = Notification(
            recipient_id=conn.sender_id,
            actor_id=current_user.id,
            type=NotificationType.connection_rejected,
            message=f"{current_user.name} declined your connection request",
            reference_id=current_user.id,
        )
        db.add(notif)
    else:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'reject'")

    db.commit()
    db.refresh(conn)
    return conn


@router.get("/", response_model=List[ConnectionOut])
def list_my_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all accepted connections for the current user."""
    connections = db.query(Connection).options(
        joinedload(Connection.sender), joinedload(Connection.receiver)
    ).filter(
        (
            (Connection.sender_id == current_user.id) |
            (Connection.receiver_id == current_user.id)
        ),
        Connection.status == ConnectionStatus.accepted,
    ).all()
    return connections


@router.get("/pending", response_model=List[ConnectionOut])
def pending_requests(
    direction: str = "incoming",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return pending connection requests (incoming by default)."""
    query = db.query(Connection).options(
        joinedload(Connection.sender), joinedload(Connection.receiver)
    ).filter(Connection.status == ConnectionStatus.pending)

    if direction == "outgoing":
        query = query.filter(Connection.sender_id == current_user.id)
    else:
        query = query.filter(Connection.receiver_id == current_user.id)

    return query.order_by(Connection.created_at.desc()).all()


@router.get("/status/{user_id}")
def connection_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the connection status between the current user and another user."""
    conn = _get_connection(db, current_user.id, user_id)
    if not conn:
        return {"status": "none"}
    return {
        "status": conn.status,
        "connection_id": conn.id,
        "is_sender": conn.sender_id == current_user.id,
    }


@router.get("/user/{user_id}", response_model=List[ConnectionOut])
def list_user_connections(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all accepted connections for a specific user."""
    # Check if target user exists and is active
    target = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
        
    connections = db.query(Connection).options(
        joinedload(Connection.sender), joinedload(Connection.receiver)
    ).filter(
        (
            (Connection.sender_id == user_id) |
            (Connection.receiver_id == user_id)
        ),
        Connection.status == ConnectionStatus.accepted,
    ).all()
    return connections
