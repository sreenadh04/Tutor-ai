"""
MediTutor AI - Q&A Router
RAG question answering with source citations and document ownership checks.
"""

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from config import MAX_CONTEXT_LENGTH, TOP_K_CHUNKS
from database import get_db
from models import QARequest, QAResponse, SourceChunk
from routers.deps import get_owned_document, get_request_user_id, validate_request_user_id
from services.llm_service import llm_service
from services.progress_service import progress_service
from services.vector_service import vector_service
from utils.cache import get_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/qa", tags=["Q&A"])
cache = get_cache()

QA_SYSTEM_PROMPT = """You are MediTutor AI, an expert educational assistant.
Answer questions accurately and clearly based on the provided study material.
Always base your answer on the given context. If the context doesn't contain enough
information, say so clearly. Be concise but thorough."""


def _build_qa_prompt(question: str, chunks: list[dict]) -> str:
    parts = []
    total = 0
    for index, chunk in enumerate(chunks, 1):
        text = chunk["text"]
        if total + len(text) > MAX_CONTEXT_LENGTH:
            break
        parts.append(f"[Source {index} - Page {chunk.get('page_number', '?')}]:\n{text}")
        total += len(text)
    return (
        "Answer the following question using ONLY the context provided below.\n"
        'If the context does not contain the answer, say "The provided material does not cover this topic."\n\n'
        f"QUESTION: {question}\n\n"
        f"CONTEXT:\n{chr(10).join(parts)}"
    )


def _question_cache_key(document_id: str, question: str) -> str:
    digest = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()
    return f"qa:{document_id}:{digest}"


@router.post("/ask", response_model=QAResponse)
async def ask_question(request: Request, qa_request: QARequest, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    validate_request_user_id(user_id, qa_request.user_id)
    get_owned_document(db, user_id, qa_request.document_id)

    cache_key = _question_cache_key(qa_request.document_id, qa_request.question)
    cached = cache.get(user_id, cache_key)
    if cached:
        return QAResponse(**cached, cached=True)

    try:
        chunks = await vector_service.search(
            user_id=user_id,
            doc_id=qa_request.document_id,
            query=qa_request.question,
            top_k=TOP_K_CHUNKS,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not chunks:
        raise HTTPException(status_code=422, detail="No relevant content found for this question.")

    prompt = _build_qa_prompt(qa_request.question, chunks)
    try:
        answer, model_used = await llm_service.generate(
            prompt=prompt,
            system=QA_SYSTEM_PROMPT,
            use_cache=False,
            user_id=user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}") from exc

    sources = [
        SourceChunk(
            text=chunk["text"][:300] + ("..." if len(chunk["text"]) > 300 else ""),
            page_number=chunk.get("page_number"),
            chunk_index=chunk.get("chunk_index", index),
            relevance_score=chunk.get("relevance_score", 0.0),
        )
        for index, chunk in enumerate(chunks[:5])
    ]
    result = {
        "answer": answer,
        "sources": [source.model_dump() for source in sources],
        "model_used": model_used,
    }
    cache.set(user_id, cache_key, result)

    if qa_request.session_id:
        try:
            progress_service.record_attempt(
                db=db,
                session_id=qa_request.session_id,
                user_id=user_id,
                question_text=qa_request.question,
                question_type="qa",
                topic=None,
                user_answer=None,
                correct_answer=None,
                is_correct=None,
                score=0.0,
            )
        except Exception as exc:
            logger.warning("Failed to record QA attempt: %s", exc)

    return QAResponse(**result)


@router.post("/ask/batch")
async def ask_batch(request: Request, questions: list[str], document_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    get_owned_document(db, user_id, document_id)

    results = []
    for question in questions:
        try:
            chunks = await vector_service.search(
                user_id=user_id,
                doc_id=document_id,
                query=question,
                top_k=TOP_K_CHUNKS,
            )
            if not chunks:
                results.append({"question": question, "answer": "No relevant content found.", "sources": []})
                continue
            answer, model_used = await llm_service.generate(
                prompt=_build_qa_prompt(question, chunks),
                system=QA_SYSTEM_PROMPT,
                user_id=user_id,
            )
            results.append(
                {
                    "question": question,
                    "answer": answer,
                    "model_used": model_used,
                    "sources_count": len(chunks),
                }
            )
        except Exception as exc:
            results.append({"question": question, "answer": f"Error: {exc}", "sources": []})
    return {"results": results, "total": len(results)}


@router.get("/suggestions/{document_id}")
async def get_suggested_questions(
    request: Request,
    document_id: str,
    limit: int = 5,
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(request)
    get_owned_document(db, user_id, document_id)

    try:
        chunks = await vector_service.search(
            user_id=user_id,
            doc_id=document_id,
            query="key concepts main topics important information",
            top_k=10,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not generate suggestions: {exc}") from exc

    if not chunks:
        return {"suggestions": ["What is the main topic of this document?"]}

    suggestion_prompt = (
        f"Based on this document content, generate {limit} good study questions.\n"
        "Return ONLY a JSON array of strings.\n\n"
        + "\n\n".join(chunk["text"][:500] for chunk in chunks[:5])
    )

    try:
        raw, _model = await llm_service.generate(
            prompt=suggestion_prompt,
            system="You generate concise study questions.",
            max_tokens=300,
            user_id=user_id,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.splitlines()[1:-1])
        suggestions = json.loads(cleaned)
        if not isinstance(suggestions, list):
            raise ValueError("Invalid suggestions payload")
        return {"suggestions": suggestions[:limit]}
    except Exception:
        return {
            "suggestions": [
                "What are the main topics covered?",
                "Can you summarize the key points?",
                "What are the important definitions?",
                "Explain the core concepts in simple terms.",
            ][:limit]
        }
