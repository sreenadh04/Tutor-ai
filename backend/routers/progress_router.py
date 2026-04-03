"""
MediTutor AI - Progress Router
Endpoints for user-scoped study sessions and progress reporting.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import ProgressResponse, SessionCreate, SessionResponse
from routers.deps import get_owned_document, get_request_user_id, validate_request_user_id
from services.progress_service import progress_service

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.post("/session/start", response_model=SessionResponse)
def start_session(request: Request, payload: SessionCreate, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    validate_request_user_id(user_id, payload.user_id)
    get_owned_document(db, user_id, payload.document_id)
    try:
        session_id = progress_service.create_session(db, payload.document_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionResponse(session_id=session_id, document_id=payload.document_id, started_at=datetime.utcnow())


@router.post("/session/{session_id}/end")
def end_session(request: Request, session_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    try:
        progress_service.end_session(db, session_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Session ended", "session_id": session_id}


@router.get("/{document_id}", response_model=ProgressResponse)
def get_progress(request: Request, document_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    get_owned_document(db, user_id, document_id)
    try:
        data = progress_service.get_progress(db, document_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProgressResponse(**data)
