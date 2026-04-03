"""
MediTutor AI - Prerequisite Checker Router
Detect knowledge gaps using user-owned documents and progress data.
"""

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import TopicProgress, get_db
from models import PrerequisiteRequest, PrerequisiteResponse
from routers.deps import get_owned_document, get_request_user_id, validate_request_user_id
from services.llm_service import llm_service
from services.vector_service import vector_service
from utils.cache import get_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prereq", tags=["Prerequisites"])
cache = get_cache()

PREREQ_SYSTEM = """You are an expert educational advisor.
Identify prerequisite knowledge required to understand a concept.
Respond ONLY with valid JSON."""


def _prereq_prompt(query: str, context: str, weak_topics: list[str]) -> str:
    weak_topics_display = ", ".join(weak_topics) if weak_topics else "None identified yet"
    return f"""A student is asking about: "{query}"

Relevant material from their textbook:
{context}

The student's currently weak topics are: {weak_topics_display}

Respond ONLY with JSON:
{{
  "missing_concepts": ["concept1", "concept2"],
  "prerequisite_topics": ["topic to study first", "topic to study second"],
  "study_recommendations": ["Recommendation 1", "Recommendation 2"]
}}"""


@router.post("/check", response_model=PrerequisiteResponse)
async def check_prerequisites(
    request: Request,
    prereq_request: PrerequisiteRequest,
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(request)
    validate_request_user_id(user_id, prereq_request.user_id)
    get_owned_document(db, user_id, prereq_request.document_id)

    weak_rows = db.query(TopicProgress).filter(
        TopicProgress.user_id == user_id,
        TopicProgress.document_id == prereq_request.document_id,
        TopicProgress.is_weak == True,
    ).all()
    weak_topics = [row.topic for row in weak_rows]

    cache_key = (
        "prereq:"
        + prereq_request.document_id
        + ":"
        + hashlib.sha256(prereq_request.query.strip().lower().encode("utf-8")).hexdigest()
    )
    cached = cache.get(user_id, cache_key)
    if cached and not weak_topics:
        return PrerequisiteResponse(**cached)

    try:
        chunks = await vector_service.search(
            user_id=user_id,
            doc_id=prereq_request.document_id,
            query=prereq_request.query,
            top_k=4,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    context = "\n\n".join(chunk["text"][:400] for chunk in chunks[:3])
    prompt = _prereq_prompt(prereq_request.query, context, weak_topics)

    try:
        raw, model_used = await llm_service.generate(
            prompt=prompt,
            system=PREREQ_SYSTEM,
            max_tokens=800,
            use_cache=False,
            user_id=user_id,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.splitlines()[1:-1])
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        payload = json.loads(cleaned[start:end]) if start != -1 and end > 0 else {}
        result = {
            "query": prereq_request.query,
            "missing_concepts": payload.get("missing_concepts", []),
            "prerequisite_topics": payload.get("prerequisite_topics", []),
            "study_recommendations": payload.get("study_recommendations", []),
            "weak_related_topics": weak_topics,
            "model_used": model_used,
        }
    except Exception as exc:
        logger.error("Prerequisite check error: %s", exc)
        result = {
            "query": prereq_request.query,
            "missing_concepts": [],
            "prerequisite_topics": [],
            "study_recommendations": ["Review foundational concepts before studying this topic."],
            "weak_related_topics": weak_topics,
            "model_used": "fallback",
        }

    cache.set(user_id, cache_key, result, ttl=1800)
    return PrerequisiteResponse(**result)
