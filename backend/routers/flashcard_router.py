"""
MediTutor AI - Flashcard Router
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from database import get_db, Document, Flashcard
from models import FlashcardRequest, FlashcardResponse, FlashcardItem
from services.flashcard_service import flashcard_service
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


@router.post("/generate", response_model=FlashcardResponse)
async def generate_flashcards(
    request: FlashcardRequest,
    db: Session = Depends(get_db),
):
    """Generate flashcards for a document or specific topic."""
    doc = db.query(Document).filter(Document.id == request.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        cards, model_used = await flashcard_service.generate(
            doc_id=request.document_id,
            count=request.count,
            topic=request.topic,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Generation failed: {str(e)}")

    # Save to DB
    for card in cards:
        fc = Flashcard(
            id=card["id"],
            document_id=request.document_id,
            question=card["question"],
            answer=card["answer"],
            topic=card.get("topic"),
            difficulty=card.get("difficulty", "medium"),
        )
        db.merge(fc)
    db.commit()

    cached = "(cached)" in model_used
    return FlashcardResponse(
        flashcards=[FlashcardItem(**c) for c in cards],
        document_id=request.document_id,
        total_generated=len(cards),
        model_used=model_used,
        cached=cached,
    )


@router.get("/export/{doc_id}")
async def export_flashcards_csv(doc_id: str, db: Session = Depends(get_db)):
    """Export saved flashcards as Anki-compatible CSV."""
    cards = db.query(Flashcard).filter(Flashcard.document_id == doc_id).all()
    if not cards:
        raise HTTPException(status_code=404, detail="No flashcards found for this document.")
    
    card_dicts = [{"question": c.question, "answer": c.answer, "topic": c.topic or "General",
                   "difficulty": c.difficulty} for c in cards]
    csv_content = flashcard_service.to_anki_csv(card_dicts)
    
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=flashcards_{doc_id[:8]}.csv"}
    )
