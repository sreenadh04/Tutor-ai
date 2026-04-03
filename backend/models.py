"""
MediTutor AI - Pydantic Schemas
Request/response models for all API endpoints.
"""

from typing import Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ─── Document Schemas ─────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    filename: str
    total_pages: int
    total_chunks: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


# ─── Q&A Schemas ──────────────────────────────────────────────────────────────

class QARequest(BaseModel):
    document_id: str
    question: str = Field(..., min_length=5, max_length=500)
    session_id: Optional[str] = None


class SourceChunk(BaseModel):
    text: str
    page_number: Optional[int] = None
    chunk_index: int
    relevance_score: float


class QAResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    model_used: str
    cached: bool = False


# ─── Flashcard Schemas ────────────────────────────────────────────────────────

class FlashcardRequest(BaseModel):
    document_id: str
    topic: Optional[str] = None          # None = full document
    count: int = Field(default=10, ge=1, le=30)


class FlashcardItem(BaseModel):
    id: str
    question: str
    answer: str
    topic: Optional[str] = None
    difficulty: str = "medium"


class FlashcardResponse(BaseModel):
    flashcards: List[FlashcardItem]
    document_id: str
    total_generated: int
    model_used: str
    cached: bool = False


# ─── MCQ Schemas ──────────────────────────────────────────────────────────────

class MCQRequest(BaseModel):
    document_id: str
    topic: Optional[str] = None
    count: int = Field(default=5, ge=1, le=20)


class MCQItem(BaseModel):
    id: str
    question: str
    options: List[str]          # exactly 4 options
    correct_index: int           # 0-3
    explanation: str
    topic: Optional[str] = None


class MCQResponse(BaseModel):
    questions: List[MCQItem]
    document_id: str
    total_generated: int
    model_used: str
    cached: bool = False


class MCQSubmission(BaseModel):
    document_id: str
    session_id: str
    answers: List[dict]     # [{"question_id": ..., "selected_index": ..., "topic": ...}]


class MCQResult(BaseModel):
    total: int
    correct: int
    score: float
    feedback: List[dict]


# ─── Progress Schemas ─────────────────────────────────────────────────────────

class ProgressResponse(BaseModel):
    student_id: str
    document_id: str
    total_attempts: int
    total_correct: int
    overall_accuracy: float
    topics: List[dict]
    weak_topics: List[str]
    strong_topics: List[str]
    recent_sessions: List[dict]


class SessionCreate(BaseModel):
    document_id: str
    student_id: str = "default_student"


class SessionResponse(BaseModel):
    session_id: str
    document_id: str
    started_at: datetime


# ─── Prerequisite Schemas ─────────────────────────────────────────────────────

class PrerequisiteRequest(BaseModel):
    document_id: str
    query: str
    student_id: str = "default_student"


class PrerequisiteResponse(BaseModel):
    query: str
    missing_concepts: List[str]
    prerequisite_topics: List[str]
    study_recommendations: List[str]
    weak_related_topics: List[str]
    model_used: str


# ─── Health / Status ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    models_available: dict
    database: str
