"""
MediTutor AI - Pydantic Schemas
Request and response models for API endpoints.
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


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


class QARequest(BaseModel):
    document_id: str
    question: str = Field(..., min_length=5, max_length=500)
    session_id: Optional[str] = None
    user_id: Optional[str] = None


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


class FlashcardRequest(BaseModel):
    document_id: str
    topic: Optional[str] = None
    count: int = Field(default=10, ge=1, le=30)
    user_id: Optional[str] = None


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


class MCQRequest(BaseModel):
    document_id: str
    topic: Optional[str] = None
    count: int = Field(default=5, ge=1, le=20)
    user_id: Optional[str] = None


class MCQItem(BaseModel):
    id: str
    question: str
    options: List[str]
    correct_index: int
    explanation: str
    topic: Optional[str] = None


class MCQResponse(BaseModel):
    questions: List[MCQItem]
    document_id: str
    total_generated: int
    model_used: str
    cached: bool = False


class MCQAnswer(BaseModel):
    question_id: str
    selected_index: int = Field(..., ge=0, le=3)
    topic: Optional[str] = None


class MCQSubmission(BaseModel):
    document_id: str
    session_id: str
    answers: List[MCQAnswer]
    user_id: Optional[str] = None


class MCQResult(BaseModel):
    total: int
    correct: int
    score: float
    feedback: List[dict]


class ProgressResponse(BaseModel):
    user_id: str
    student_id: Optional[str] = None
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
    user_id: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    document_id: str
    started_at: datetime


class PrerequisiteRequest(BaseModel):
    document_id: str
    query: str = Field(..., min_length=3, max_length=500)
    user_id: Optional[str] = None


class PrerequisiteResponse(BaseModel):
    query: str
    missing_concepts: List[str]
    prerequisite_topics: List[str]
    study_recommendations: List[str]
    weak_related_topics: List[str]
    model_used: str


class HealthResponse(BaseModel):
    status: str
    version: str
    models_available: dict
    database: str
