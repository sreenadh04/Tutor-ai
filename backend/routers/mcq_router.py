"""
MediTutor AI - MCQ Router
Generate and grade quizzes with user-scoped ownership checks.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import MCQuestion, get_db
from models import MCQItem, MCQRequest, MCQResponse, MCQResult, MCQSubmission
from routers.deps import get_owned_document, get_owned_session, get_request_user_id, validate_request_user_id
from services.mcq_service import mcq_service
from services.progress_service import progress_service

router = APIRouter(prefix="/mcq", tags=["MCQ"])


@router.post("/generate", response_model=MCQResponse)
async def generate_mcqs(
    request: Request,
    mcq_request: MCQRequest,
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(request)
    validate_request_user_id(user_id, mcq_request.user_id)
    get_owned_document(db, user_id, mcq_request.document_id)

    try:
        questions, model_used = await mcq_service.generate(
            user_id=user_id,
            doc_id=mcq_request.document_id,
            count=mcq_request.count,
            topic=mcq_request.topic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Generation failed: {exc}") from exc

    for question in questions:
        db.merge(
            MCQuestion(
                id=question["id"],
                document_id=mcq_request.document_id,
                user_id=user_id,
                question=question["question"],
                options=question["options"],
                correct_index=question["correct_index"],
                explanation=question["explanation"],
                topic=question.get("topic"),
            )
        )
    db.commit()

    return MCQResponse(
        questions=[MCQItem(**question) for question in questions],
        document_id=mcq_request.document_id,
        total_generated=len(questions),
        model_used=model_used,
        cached="(cached)" in model_used,
    )


@router.post("/submit", response_model=MCQResult)
async def submit_mcq_answers(
    request: Request,
    submission: MCQSubmission,
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(request)
    validate_request_user_id(user_id, submission.user_id)
    get_owned_document(db, user_id, submission.document_id)
    get_owned_session(db, user_id, submission.session_id)

    question_ids = [answer.question_id for answer in submission.answers]
    db_questions = db.query(MCQuestion).filter(
        MCQuestion.id.in_(question_ids),
        MCQuestion.document_id == submission.document_id,
        MCQuestion.user_id == user_id,
    ).all()

    questions_map = {
        question.id: {
            "question": question.question,
            "options": question.options,
            "correct_index": question.correct_index,
            "explanation": question.explanation,
            "topic": question.topic,
        }
        for question in db_questions
    }
    if len(questions_map) != len(question_ids):
        raise HTTPException(status_code=404, detail="One or more quiz questions were not found for this user.")

    result = mcq_service.grade_submission(questions_map, [answer.model_dump() for answer in submission.answers])
    progress_service.record_mcq_batch(
        db=db,
        session_id=submission.session_id,
        document_id=submission.document_id,
        user_id=user_id,
        results=result["feedback"],
    )
    return MCQResult(**result)
