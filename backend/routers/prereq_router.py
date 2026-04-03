"""
MediTutor AI - Prerequisite Checker Router
Detects knowledge gaps and suggests what to study first.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db, Document, TopicProgress
from models import PrerequisiteRequest, PrerequisiteResponse
from services.llm_service import llm_service
from services.vector_service import vector_service
from services.progress_service import progress_service
from utils.cache import CacheManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prereq", tags=["Prerequisites"])
cache = CacheManager()


PREREQ_SYSTEM = """You are an expert educational advisor.
Identify prerequisite knowledge required to understand a concept.
Respond ONLY with valid JSON."""


def _prereq_prompt(query: str, context: str, weak_topics: list) -> str:
    weak_str = ", ".join(weak_topics) if weak_topics else "None identified yet"
    return f"""A student is asking about: "{query}"

Relevant material from their textbook:
{context}

The student's currently weak topics are: {weak_str}

Analyze what prerequisite knowledge is needed to understand this query.
Respond ONLY with this JSON:
{{
  "missing_concepts": ["concept1", "concept2"],
  "prerequisite_topics": ["topic to study first", "topic to study second"],
  "study_recommendations": ["Recommendation 1", "Recommendation 2"],
  "study_order": ["Step 1: Study X", "Step 2: Then study Y", "Step 3: Now tackle the query"]
}}"""


@router.post("/check", response_model=PrerequisiteResponse)
async def check_prerequisites(
    request: PrerequisiteRequest,
    db: Session = Depends(get_db),
):
    """
    Detect missing prerequisite concepts for a student's query.
    Combines LLM analysis with the student's known weak topics.
    """
    doc = db.query(Document).filter(Document.id == request.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Cache key
    cache_key = f"prereq:{request.document_id}:{hash(request.query)}"
    cached = cache.get(cache_key)

    # Get student's weak topics from DB
    weak_rows = db.query(TopicProgress).filter(
        TopicProgress.student_id == request.student_id,
        TopicProgress.document_id == request.document_id,
        TopicProgress.is_weak == True,
    ).all()
    weak_topics = [r.topic for r in weak_rows]

    if cached and not weak_topics:
        return PrerequisiteResponse(**cached)

    # Get relevant context from vector store
    try:
        chunks = vector_service.search(request.document_id, request.query, top_k=4)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    context = "\n\n".join([c["text"][:400] for c in chunks[:3]])
    prompt = _prereq_prompt(request.query, context, weak_topics)

    try:
        import json
        raw, model_used = await llm_service.generate(
            prompt=prompt,
            system=PREREQ_SYSTEM,
            max_tokens=800,
            use_cache=False,
        )

        # Parse JSON
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])
        
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end]) if start != -1 else {}

        result = {
            "query": request.query,
            "missing_concepts": data.get("missing_concepts", []),
            "prerequisite_topics": data.get("prerequisite_topics", []),
            "study_recommendations": data.get("study_recommendations", data.get("study_order", [])),
            "weak_related_topics": weak_topics,
            "model_used": model_used,
        }

    except Exception as e:
        logger.error(f"Prerequisite check error: {e}")
        result = {
            "query": request.query,
            "missing_concepts": [],
            "prerequisite_topics": [],
            "study_recommendations": ["Review foundational concepts before studying this topic."],
            "weak_related_topics": weak_topics,
            "model_used": "fallback",
        }

    cache.set(cache_key, result, ttl=1800)
    return PrerequisiteResponse(**result)
