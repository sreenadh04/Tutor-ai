"""
MediTutor AI - Progress Service
Tracks student performance, identifies weak topics, and manages sessions.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    StudySession, QuestionAttempt, TopicProgress,
    Document, Flashcard, MCQuestion
)

logger = logging.getLogger(__name__)

WEAK_TOPIC_THRESHOLD = 0.6   # below 60% accuracy = weak topic


class ProgressService:

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, db: Session, document_id: str, student_id: str = "default_student") -> str:
        session_id = str(uuid.uuid4())
        session = StudySession(
            id=session_id,
            document_id=document_id,
            student_id=student_id,
        )
        db.add(session)
        db.commit()
        return session_id

    def end_session(self, db: Session, session_id: str):
        session = db.query(StudySession).filter(StudySession.id == session_id).first()
        if session:
            session.ended_at = datetime.utcnow()
            db.commit()

    # ── Record attempts ───────────────────────────────────────────────────────

    def record_attempt(
        self,
        db: Session,
        session_id: str,
        question_text: str,
        question_type: str,
        topic: Optional[str],
        user_answer: Optional[str],
        correct_answer: Optional[str],
        is_correct: Optional[bool],
        score: float = 0.0,
    ) -> str:
        attempt_id = str(uuid.uuid4())
        attempt = QuestionAttempt(
            id=attempt_id,
            session_id=session_id,
            question_text=question_text,
            question_type=question_type,
            topic=topic,
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct,
            score=score,
        )
        db.add(attempt)
        db.commit()

        # Update topic progress
        if topic:
            session = db.query(StudySession).filter(StudySession.id == session_id).first()
            if session:
                self._update_topic_progress(
                    db, session.student_id, session.document_id, topic, bool(is_correct)
                )

        return attempt_id

    def record_mcq_batch(
        self,
        db: Session,
        session_id: str,
        document_id: str,
        results: List[dict],
    ):
        """Record all MCQ answers from a quiz submission."""
        session = db.query(StudySession).filter(StudySession.id == session_id).first()
        if not session:
            return

        for item in results:
            topic = item.get("topic", "General")
            is_correct = item.get("is_correct", False)
            
            attempt = QuestionAttempt(
                id=str(uuid.uuid4()),
                session_id=session_id,
                question_text=item.get("question", ""),
                question_type="mcq",
                topic=topic,
                user_answer=str(item.get("selected_index", "")),
                correct_answer=str(item.get("correct_index", "")),
                is_correct=is_correct,
                score=1.0 if is_correct else 0.0,
            )
            db.add(attempt)
            self._update_topic_progress(
                db, session.student_id, document_id, topic, is_correct
            )

        db.commit()

    # ── Topic progress ────────────────────────────────────────────────────────

    def _update_topic_progress(
        self,
        db: Session,
        student_id: str,
        document_id: str,
        topic: str,
        is_correct: bool,
    ):
        existing = db.query(TopicProgress).filter(
            TopicProgress.student_id == student_id,
            TopicProgress.document_id == document_id,
            TopicProgress.topic == topic,
        ).first()

        if existing:
            existing.attempts += 1
            if is_correct:
                existing.correct += 1
            existing.accuracy = existing.correct / existing.attempts
            existing.is_weak = existing.accuracy < WEAK_TOPIC_THRESHOLD
            existing.last_attempt = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
        else:
            tp = TopicProgress(
                id=str(uuid.uuid4()),
                student_id=student_id,
                document_id=document_id,
                topic=topic,
                attempts=1,
                correct=1 if is_correct else 0,
                accuracy=1.0 if is_correct else 0.0,
                is_weak=not is_correct,
                last_attempt=datetime.utcnow(),
            )
            db.add(tp)

        db.commit()

    # ── Progress Report ───────────────────────────────────────────────────────

    def get_progress(
        self,
        db: Session,
        document_id: str,
        student_id: str = "default_student",
    ) -> dict:
        # Topic breakdown
        topic_rows = db.query(TopicProgress).filter(
            TopicProgress.student_id == student_id,
            TopicProgress.document_id == document_id,
        ).all()

        total_attempts = sum(t.attempts for t in topic_rows)
        total_correct = sum(t.correct for t in topic_rows)
        overall_accuracy = (total_correct / total_attempts * 100) if total_attempts else 0

        weak_topics = [t.topic for t in topic_rows if t.is_weak]
        strong_topics = [
            t.topic for t in topic_rows
            if not t.is_weak and t.attempts >= 3 and t.accuracy >= 0.8
        ]

        topics_data = [
            {
                "topic": t.topic,
                "attempts": t.attempts,
                "correct": t.correct,
                "accuracy": round(t.accuracy * 100, 1),
                "is_weak": t.is_weak,
                "last_attempt": t.last_attempt.isoformat() if t.last_attempt else None,
            }
            for t in sorted(topic_rows, key=lambda x: x.accuracy)
        ]

        # Recent sessions
        sessions = db.query(StudySession).filter(
            StudySession.document_id == document_id,
            StudySession.student_id == student_id,
        ).order_by(StudySession.started_at.desc()).limit(5).all()

        recent_sessions = []
        for s in sessions:
            attempts = db.query(QuestionAttempt).filter(
                QuestionAttempt.session_id == s.id
            ).all()
            session_correct = sum(1 for a in attempts if a.is_correct)
            recent_sessions.append({
                "session_id": s.id,
                "started_at": s.started_at.isoformat(),
                "total_questions": len(attempts),
                "correct": session_correct,
                "accuracy": round(session_correct / len(attempts) * 100, 1) if attempts else 0,
            })

        return {
            "student_id": student_id,
            "document_id": document_id,
            "total_attempts": total_attempts,
            "total_correct": total_correct,
            "overall_accuracy": round(overall_accuracy, 1),
            "topics": topics_data,
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "recent_sessions": recent_sessions,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────
progress_service = ProgressService()
