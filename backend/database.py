"""
MediTutor AI - Database Models & Setup
SQLite with SQLAlchemy ORM for progress tracking.
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    DateTime, Text, Boolean, ForeignKey, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── ORM Models ──────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)          # UUID
    filename = Column(String, nullable=False)
    total_pages = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    vector_store_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sessions = relationship("StudySession", back_populates="document")
    flashcards = relationship("Flashcard", back_populates="document")
    mcqs = relationship("MCQuestion", back_populates="document")


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    student_id = Column(String, default="default_student")
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    document = relationship("Document", back_populates="sessions")
    attempts = relationship("QuestionAttempt", back_populates="session")


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("study_sessions.id"))
    question_text = Column(Text)
    question_type = Column(String)     # "mcq" | "qa" | "flashcard"
    topic = Column(String, nullable=True)
    user_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, default=0.0)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("StudySession", back_populates="attempts")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    question = Column(Text)
    answer = Column(Text)
    topic = Column(String, nullable=True)
    difficulty = Column(String, default="medium")   # easy | medium | hard
    review_count = Column(Integer, default=0)
    last_reviewed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    document = relationship("Document", back_populates="flashcards")


class MCQuestion(Base):
    __tablename__ = "mc_questions"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    question = Column(Text)
    options = Column(JSON)          # list of 4 strings
    correct_index = Column(Integer) # 0-3
    explanation = Column(Text)
    topic = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    document = relationship("Document", back_populates="mcqs")


class TopicProgress(Base):
    __tablename__ = "topic_progress"

    id = Column(String, primary_key=True)
    student_id = Column(String, default="default_student")
    document_id = Column(String, ForeignKey("documents.id"))
    topic = Column(String)
    attempts = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    last_attempt = Column(DateTime, nullable=True)
    is_weak = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize tables on import
create_tables()
