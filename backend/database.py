"""
MediTutor AI - Database Models & Setup
SQLite with SQLAlchemy ORM for document metadata and user-scoped study progress.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    total_pages = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    vector_store_path = Column(String)
    user_id = Column(String, index=True, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship(
        "StudySession",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    flashcards = relationship(
        "Flashcard",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    mcqs = relationship(
        "MCQuestion",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(String, index=True, nullable=True)
    student_id = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    document = relationship("Document", back_populates="sessions")
    attempts = relationship(
        "QuestionAttempt",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("study_sessions.id"), nullable=False, index=True)
    user_id = Column(String, index=True, nullable=True)
    question_text = Column(Text)
    question_type = Column(String)
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
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(String, index=True, nullable=True)
    question = Column(Text)
    answer = Column(Text)
    topic = Column(String, nullable=True)
    difficulty = Column(String, default="medium")
    review_count = Column(Integer, default=0)
    last_reviewed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="flashcards")


class MCQuestion(Base):
    __tablename__ = "mc_questions"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(String, index=True, nullable=True)
    question = Column(Text)
    options = Column(JSON)
    correct_index = Column(Integer)
    explanation = Column(Text)
    topic = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="mcqs")


class TopicProgress(Base):
    __tablename__ = "topic_progress"

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=True)
    student_id = Column(String, nullable=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    topic = Column(String)
    attempts = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    last_attempt = Column(DateTime, nullable=True)
    is_weak = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


def _sqlite_column_exists(db: Engine, table_name: str, column_name: str) -> bool:
    with db.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    return any(row["name"] == column_name for row in rows)


def _safe_add_column(table_name: str, column_sql: str):
    try:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
    except Exception:
        # Column may already exist or the table may not be present yet.
        pass


def run_migrations():
    migrations = {
        "study_sessions": [
            "user_id VARCHAR",
            "student_id VARCHAR",
        ],
        "question_attempts": [
            "user_id VARCHAR",
        ],
        "flashcards": [
            "user_id VARCHAR",
        ],
        "mc_questions": [
            "user_id VARCHAR",
        ],
        "topic_progress": [
            "user_id VARCHAR",
            "student_id VARCHAR",
        ],
    }

    for table_name, columns in migrations.items():
        for column_sql in columns:
            column_name = column_sql.split()[0]
            if not _sqlite_column_exists(engine, table_name, column_name):
                _safe_add_column(table_name, column_sql)

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE study_sessions "
                "SET user_id = COALESCE(user_id, student_id) "
                "WHERE user_id IS NULL OR user_id = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE study_sessions "
                "SET student_id = COALESCE(student_id, user_id) "
                "WHERE student_id IS NULL OR student_id = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE topic_progress "
                "SET user_id = COALESCE(user_id, student_id) "
                "WHERE user_id IS NULL OR user_id = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE topic_progress "
                "SET student_id = COALESCE(student_id, user_id) "
                "WHERE student_id IS NULL OR student_id = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE flashcards "
                "SET user_id = (SELECT documents.user_id FROM documents WHERE documents.id = flashcards.document_id) "
                "WHERE user_id IS NULL OR user_id = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE mc_questions "
                "SET user_id = (SELECT documents.user_id FROM documents WHERE documents.id = mc_questions.document_id) "
                "WHERE user_id IS NULL OR user_id = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE question_attempts "
                "SET user_id = ("
                "SELECT COALESCE(study_sessions.user_id, study_sessions.student_id) "
                "FROM study_sessions WHERE study_sessions.id = question_attempts.session_id"
                ") "
                "WHERE user_id IS NULL OR user_id = ''"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON study_sessions (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_attempts_user_id ON question_attempts (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_flashcards_user_id ON flashcards (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mc_questions_user_id ON mc_questions (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_topic_progress_user_id ON topic_progress (user_id)"))


def create_tables():
    Base.metadata.create_all(bind=engine)
    run_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


create_tables()
