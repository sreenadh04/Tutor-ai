"""
MediTutor AI - Progress Router
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db, Document
from models import ProgressResponse, SessionCreate, SessionResponse
from services.progress_service import progress_service
from datetime import datetime

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.post("/session/start", response_model=SessionResponse)
def start_session(request: SessionCreate, db: Session = Depends(get_db)):
    """Start a new study session."""
    doc = db.query(Document).filter(Document.id == request.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    session_id = progress_service.create_session(db, request.document_id, request.student_id)
    return SessionResponse(
        session_id=session_id,
        document_id=request.document_id,
        started_at=datetime.utcnow(),
    )


@router.post("/session/{session_id}/end")
def end_session(session_id: str, db: Session = Depends(get_db)):
    """End a study session."""
    progress_service.end_session(db, session_id)
    return {"message": "Session ended", "session_id": session_id}


@router.get("/{document_id}", response_model=ProgressResponse)
def get_progress(
    document_id: str,
    student_id: str = "default_student",
    db: Session = Depends(get_db),
):
    """Get full progress report for a student on a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    data = progress_service.get_progress(db, document_id, student_id)
    return ProgressResponse(**data)
