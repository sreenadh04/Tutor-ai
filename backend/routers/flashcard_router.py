"""
MediTutor AI - Flashcard Router
Generate, manage, and export flashcards with user ownership checks.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from database import Flashcard, get_db
from models import FlashcardItem, FlashcardRequest, FlashcardResponse
from routers.deps import get_owned_document, get_request_user_id, validate_request_user_id
from services.flashcard_service import flashcard_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


def _get_owned_flashcard(db: Session, user_id: str, flashcard_id: str) -> Flashcard:
    flashcard = db.query(Flashcard).filter(
        Flashcard.id == flashcard_id,
        Flashcard.user_id == user_id,
    ).first()
    if not flashcard:
        raise HTTPException(status_code=404, detail="Flashcard not found or you do not have access to it.")
    return flashcard


@router.post("/generate", response_model=FlashcardResponse)
async def generate_flashcards(
    request: Request,
    flashcard_request: FlashcardRequest,
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(request)
    validate_request_user_id(user_id, flashcard_request.user_id)
    get_owned_document(db, user_id, flashcard_request.document_id)

    try:
        cards, model_used = await flashcard_service.generate(
            user_id=user_id,
            doc_id=flashcard_request.document_id,
            count=flashcard_request.count,
            topic=flashcard_request.topic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Generation failed: {exc}") from exc

    for card in cards:
        db.merge(
            Flashcard(
                id=card["id"],
                document_id=flashcard_request.document_id,
                user_id=user_id,
                question=card["question"],
                answer=card["answer"],
                topic=card.get("topic"),
                difficulty=card.get("difficulty", "medium"),
            )
        )
    db.commit()

    cached = "(cached)" in model_used
    return FlashcardResponse(
        flashcards=[FlashcardItem(**card) for card in cards],
        document_id=flashcard_request.document_id,
        total_generated=len(cards),
        model_used=model_used,
        cached=cached,
    )


@router.get("/list/{doc_id}")
async def list_flashcards(
    request: Request,
    doc_id: str,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(request)
    get_owned_document(db, user_id, doc_id)
    flashcards = db.query(Flashcard).filter(
        Flashcard.document_id == doc_id,
        Flashcard.user_id == user_id,
    ).offset(offset).limit(limit).all()
    total = db.query(Flashcard).filter(
        Flashcard.document_id == doc_id,
        Flashcard.user_id == user_id,
    ).count()
    return {
        "flashcards": [
            {
                "id": flashcard.id,
                "question": flashcard.question,
                "answer": flashcard.answer,
                "topic": flashcard.topic,
                "difficulty": flashcard.difficulty,
                "review_count": flashcard.review_count,
                "last_reviewed": flashcard.last_reviewed.isoformat() if flashcard.last_reviewed else None,
            }
            for flashcard in flashcards
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{flashcard_id}")
async def get_flashcard(request: Request, flashcard_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    flashcard = _get_owned_flashcard(db, user_id, flashcard_id)
    return {
        "id": flashcard.id,
        "question": flashcard.question,
        "answer": flashcard.answer,
        "topic": flashcard.topic,
        "difficulty": flashcard.difficulty,
        "review_count": flashcard.review_count,
        "last_reviewed": flashcard.last_reviewed,
        "created_at": flashcard.created_at,
    }


@router.post("/{flashcard_id}/review")
async def review_flashcard(
    request: Request,
    flashcard_id: str,
    difficulty: str,
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(request)
    if difficulty not in {"easy", "medium", "hard"}:
        raise HTTPException(status_code=400, detail="Difficulty must be easy, medium, or hard.")

    flashcard = _get_owned_flashcard(db, user_id, flashcard_id)
    flashcard.review_count += 1
    flashcard.last_reviewed = datetime.utcnow()

    if difficulty == "easy" and flashcard.difficulty == "hard":
        flashcard.difficulty = "medium"
    elif difficulty == "easy" and flashcard.difficulty == "medium":
        flashcard.difficulty = "easy"
    elif difficulty == "hard" and flashcard.difficulty == "easy":
        flashcard.difficulty = "medium"
    elif difficulty == "hard" and flashcard.difficulty == "medium":
        flashcard.difficulty = "hard"

    db.commit()
    return {
        "message": "Review recorded",
        "flashcard_id": flashcard_id,
        "difficulty": flashcard.difficulty,
        "review_count": flashcard.review_count,
        "last_reviewed": flashcard.last_reviewed.isoformat(),
    }


@router.get("/export/{doc_id}")
async def export_flashcards_csv(request: Request, doc_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    get_owned_document(db, user_id, doc_id)

    cards = db.query(Flashcard).filter(
        Flashcard.document_id == doc_id,
        Flashcard.user_id == user_id,
    ).all()
    if not cards:
        raise HTTPException(status_code=404, detail="No flashcards found for this document.")

    csv_content = flashcard_service.to_anki_csv(
        [
            {
                "question": card.question,
                "answer": card.answer,
                "topic": card.topic or "General",
                "difficulty": card.difficulty,
            }
            for card in cards
        ]
    )
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=flashcards_{doc_id[:8]}.csv"},
    )


@router.delete("/{flashcard_id}")
async def delete_flashcard(request: Request, flashcard_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    flashcard = _get_owned_flashcard(db, user_id, flashcard_id)
    db.delete(flashcard)
    db.commit()
    return {"message": "Flashcard deleted", "flashcard_id": flashcard_id}
