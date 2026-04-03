"""
MediTutor AI - Q&A Router
RAG-based question answering with source citations.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import QARequest, QAResponse, SourceChunk
from services.vector_service import vector_service
from services.llm_service import llm_service
from services.progress_service import progress_service
from config import MAX_CONTEXT_LENGTH, TOP_K_CHUNKS
from utils.cache import CacheManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/qa", tags=["Q&A"])
cache = CacheManager()


QA_SYSTEM_PROMPT = """You are MediTutor AI, an expert educational assistant.
Answer questions accurately and clearly based on the provided study material.
Always base your answer on the given context. If the context doesn't contain enough
information, say so clearly. Be concise but thorough."""


def _build_qa_prompt(question: str, chunks: list) -> str:
    context_parts = []
    total = 0
    for i, chunk in enumerate(chunks, 1):
        text = chunk["text"]
        page = chunk.get("page_number", "?")
        if total + len(text) > MAX_CONTEXT_LENGTH:
            break
        context_parts.append(f"[Source {i} - Page {page}]:\n{text}")
        total += len(text)

    context = "\n\n".join(context_parts)
    return f"""Answer the following question using ONLY the context provided below.
If the context doesn't contain the answer, say "The provided material doesn't cover this topic."

QUESTION: {question}

CONTEXT:
{context}

Provide a clear, well-structured answer. Reference source numbers where relevant (e.g., "According to Source 1...").
"""


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    db: Session = Depends(get_db),
):
    """
    RAG-based Q&A with source citations.
    Retrieves relevant chunks and generates a grounded answer.
    """
    # Check cache
    cache_key = f"qa:{request.document_id}:{hash(request.question)}"
    cached = cache.get(cache_key)
    if cached:
        return QAResponse(**cached, cached=True)

    # Retrieve relevant chunks
    try:
        chunks = vector_service.search(
            request.document_id,
            request.question,
            top_k=TOP_K_CHUNKS,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No relevant content found. Try rephrasing your question."
        )

    # Build prompt and generate answer
    prompt = _build_qa_prompt(request.question, chunks)
    try:
        answer, model_used = await llm_service.generate(
            prompt=prompt,
            system=QA_SYSTEM_PROMPT,
            use_cache=False,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {str(e)}")

    # Build source list
    sources = [
        SourceChunk(
            text=c["text"][:300] + ("..." if len(c["text"]) > 300 else ""),
            page_number=c.get("page_number"),
            chunk_index=c.get("chunk_index", i),
            relevance_score=c.get("relevance_score", 0.0),
        )
        for i, c in enumerate(chunks)
    ]

    result = {
        "answer": answer,
        "sources": [s.dict() for s in sources],
        "model_used": model_used,
        "cached": False,
    }
    cache.set(cache_key, result)

    # Record attempt if session provided
    if request.session_id:
        try:
            progress_service.record_attempt(
                db=db,
                session_id=request.session_id,
                question_text=request.question,
                question_type="qa",
                topic=None,
                user_answer=None,
                correct_answer=None,
                is_correct=None,
                score=0.0,
            )
        except Exception:
            pass  # Don't fail the request if tracking fails

    return QAResponse(**result)
