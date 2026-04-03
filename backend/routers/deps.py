"""
Shared router dependencies for authenticated user access.
"""

from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from database import Document, StudySession


def get_request_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header required.")
    return user_id


def validate_request_user_id(request_user_id: str, payload_user_id: str | None):
    if payload_user_id and payload_user_id != request_user_id:
        raise HTTPException(status_code=403, detail="user_id in request body does not match authenticated user.")


def normalize_user_id(raw_user_id: str) -> str:
    try:
        return str(UUID(raw_user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-User-ID format. Expected UUID.") from exc


def get_owned_document(db: Session, user_id: str, document_id: str) -> Document:
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == user_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or you do not have access to it.")
    return document


def get_owned_session(db: Session, user_id: str, session_id: str) -> StudySession:
    session = db.query(StudySession).filter(
        StudySession.id == session_id,
        StudySession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or you do not have access to it.")
    return session
