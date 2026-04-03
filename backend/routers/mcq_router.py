"""
MediTutor AI - MCQ Router
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db, Document, MCQuestion
from models import MCQRequest, MCQResponse, MCQItem, MCQSubmission, MCQResult
from services.mcq_service import mcq_service
from services.progress_service import progress_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcq", tags=["MCQ"])


@router.post("/generate", response_model=MCQResponse)
async def generate_mcqs(
    request: MCQRequest,
    db: Session = Depends(get_db),
):
    """Generate MCQ quiz questions from a document."""
    doc = db.query(Document).filter(Document.id == request.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        questions, model_used = await mcq_service.generate(
            doc_id=request.document_id,
            count=request.count,
            topic=request.topic,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Generation failed: {str(e)}")

    # Persist to DB
    for q in questions:
        mcq = MCQuestion(
            id=q["id"],
            document_id=request.document_id,
            question=q["question"],
            options=q["options"],
            correct_index=q["correct_index"],
            explanation=q["explanation"],
            topic=q.get("topic"),
        )
        db.merge(mcq)
    db.commit()

    cached = "(cached)" in model_used
    return MCQResponse(
        questions=[MCQItem(**q) for q in questions],
        document_id=request.document_id,
        total_generated=len(questions),
        model_used=model_used,
        cached=cached,
    )


@router.post("/submit", response_model=MCQResult)
async def submit_mcq_answers(
    submission: MCQSubmission,
    db: Session = Depends(get_db),
):
    """Submit quiz answers and get graded results with explanations."""
    # Load questions from DB
    question_ids = [a["question_id"] for a in submission.answers]
    db_questions = db.query(MCQuestion).filter(
        MCQuestion.id.in_(question_ids)
    ).all()

    questions_map = {
        q.id: {
            "question": q.question,
            "options": q.options,
            "correct_index": q.correct_index,
            "explanation": q.explanation,
            "topic": q.topic,
        }
        for q in db_questions
    }

    result = mcq_service.grade_submission(questions_map, submission.answers)

    # Record in progress tracker
    progress_service.record_mcq_batch(
        db=db,
        session_id=submission.session_id,
        document_id=submission.document_id,
        results=result["feedback"],
    )

    return MCQResult(**result)
