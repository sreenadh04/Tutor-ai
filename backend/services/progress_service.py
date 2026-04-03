"""
MediTutor AI - Progress Service with User Isolation
Tracks study sessions, attempts, and topic-level progress per user.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import Document, QuestionAttempt, StudySession, TopicProgress

logger = logging.getLogger(__name__)

WEAK_TOPIC_THRESHOLD = 0.6


class ProgressService:
    def create_session(self, db: Session, document_id: str, user_id: str) -> str:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id,
        ).first()
        if not document:
            raise ValueError("Document not found or not owned by user.")

        session_id = str(uuid.uuid4())
        session = StudySession(
            id=session_id,
            document_id=document_id,
            user_id=user_id,
            student_id=user_id,
        )
        db.add(session)
        db.commit()
        return session_id

    def end_session(self, db: Session, session_id: str, user_id: str):
        session = db.query(StudySession).filter(
            StudySession.id == session_id,
            StudySession.user_id == user_id,
        ).first()
        if not session:
            raise ValueError("Session not found or not owned by user.")
        session.ended_at = datetime.utcnow()
        db.commit()

    def record_attempt(
        self,
        db: Session,
        session_id: str,
        user_id: str,
        question_text: str,
        question_type: str,
        topic: Optional[str],
        user_answer: Optional[str],
        correct_answer: Optional[str],
        is_correct: Optional[bool],
        score: float = 0.0,
    ) -> str:
        session = db.query(StudySession).filter(
            StudySession.id == session_id,
            StudySession.user_id == user_id,
        ).first()
        if not session:
            raise ValueError("Session not found or not owned by user.")

        attempt = QuestionAttempt(
            id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            question_text=question_text[:500],
            question_type=question_type,
            topic=topic[:100] if topic else None,
            user_answer=str(user_answer)[:500] if user_answer is not None else None,
            correct_answer=str(correct_answer)[:500] if correct_answer is not None else None,
            is_correct=is_correct,
            score=score,
        )
        db.add(attempt)
        db.commit()

        if topic:
            self._update_topic_progress(
                db=db,
                user_id=user_id,
                document_id=session.document_id,
                topic=topic,
                is_correct=bool(is_correct) if is_correct is not None else False,
            )
        return attempt.id

    def record_mcq_batch(
        self,
        db: Session,
        session_id: str,
        document_id: str,
        user_id: str,
        results: List[dict],
    ):
        session = db.query(StudySession).filter(
            StudySession.id == session_id,
            StudySession.user_id == user_id,
            StudySession.document_id == document_id,
        ).first()
        if not session:
            raise ValueError("Session not found or not owned by user.")

        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id,
        ).first()
        if not document:
            raise ValueError("Document not found or not owned by user.")

        for item in results:
            topic = item.get("topic") or "General"
            is_correct = bool(item.get("is_correct", False))
            db.add(
                QuestionAttempt(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    user_id=user_id,
                    question_text=item.get("question", "")[:500],
                    question_type="mcq",
                    topic=topic[:100],
                    user_answer=str(item.get("selected_index", ""))[:10],
                    correct_answer=str(item.get("correct_index", ""))[:10],
                    is_correct=is_correct,
                    score=1.0 if is_correct else 0.0,
                )
            )
            self._update_topic_progress(
                db=db,
                user_id=user_id,
                document_id=document_id,
                topic=topic,
                is_correct=is_correct,
                commit=False,
            )

        db.commit()

    def _update_topic_progress(
        self,
        db: Session,
        user_id: str,
        document_id: str,
        topic: str,
        is_correct: bool,
        commit: bool = True,
    ):
        progress = db.query(TopicProgress).filter(
            TopicProgress.user_id == user_id,
            TopicProgress.document_id == document_id,
            TopicProgress.topic == topic,
        ).first()

        if progress:
            progress.attempts += 1
            if is_correct:
                progress.correct += 1
            progress.accuracy = progress.correct / progress.attempts
            progress.is_weak = progress.accuracy < WEAK_TOPIC_THRESHOLD
            progress.last_attempt = datetime.utcnow()
            progress.updated_at = datetime.utcnow()
        else:
            db.add(
                TopicProgress(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    student_id=user_id,
                    document_id=document_id,
                    topic=topic[:100],
                    attempts=1,
                    correct=1 if is_correct else 0,
                    accuracy=1.0 if is_correct else 0.0,
                    is_weak=not is_correct,
                    last_attempt=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

        if commit:
            db.commit()

    def get_progress(self, db: Session, document_id: str, user_id: str) -> dict:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id,
        ).first()
        if not document:
            raise ValueError("Document not found or not owned by user.")

        topic_rows = db.query(TopicProgress).filter(
            TopicProgress.user_id == user_id,
            TopicProgress.document_id == document_id,
        ).all()

        total_attempts = sum(row.attempts for row in topic_rows)
        total_correct = sum(row.correct for row in topic_rows)
        overall_accuracy = (total_correct / total_attempts * 100) if total_attempts else 0.0

        weak_topics = [row.topic for row in topic_rows if row.is_weak]
        strong_topics = [
            row.topic
            for row in topic_rows
            if not row.is_weak and row.attempts >= 3 and row.accuracy >= 0.8
        ]
        topics_data = [
            {
                "topic": row.topic,
                "attempts": row.attempts,
                "correct": row.correct,
                "accuracy": round(row.accuracy * 100, 1),
                "is_weak": row.is_weak,
                "last_attempt": row.last_attempt.isoformat() if row.last_attempt else None,
            }
            for row in sorted(topic_rows, key=lambda item: item.accuracy)
        ]

        sessions = db.query(StudySession).filter(
            StudySession.document_id == document_id,
            StudySession.user_id == user_id,
        ).order_by(StudySession.started_at.desc()).limit(10).all()

        recent_sessions = []
        for session in sessions:
            attempts = db.query(QuestionAttempt).filter(
                QuestionAttempt.session_id == session.id,
                QuestionAttempt.user_id == user_id,
            ).all()
            correct_answers = sum(1 for attempt in attempts if attempt.is_correct)
            recent_sessions.append(
                {
                    "session_id": session.id[:8] + "...",
                    "started_at": session.started_at.isoformat(),
                    "total_questions": len(attempts),
                    "correct": correct_answers,
                    "accuracy": round(correct_answers / len(attempts) * 100, 1) if attempts else 0.0,
                }
            )

        return {
            "user_id": user_id,
            "student_id": user_id,
            "document_id": document_id,
            "total_attempts": total_attempts,
            "total_correct": total_correct,
            "overall_accuracy": round(overall_accuracy, 1),
            "topics": topics_data,
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "recent_sessions": recent_sessions,
        }

    def delete_user_data(self, db: Session, user_id: str) -> Dict[str, int]:
        deleted_counts = {
            "sessions": 0,
            "attempts": 0,
            "topic_progress": 0,
        }

        sessions = db.query(StudySession).filter(StudySession.user_id == user_id).all()
        session_ids = [session.id for session in sessions]

        if session_ids:
            deleted_counts["attempts"] = db.query(QuestionAttempt).filter(
                QuestionAttempt.session_id.in_(session_ids)
            ).delete(synchronize_session=False)

        deleted_counts["sessions"] = db.query(StudySession).filter(
            StudySession.user_id == user_id
        ).delete(synchronize_session=False)
        deleted_counts["topic_progress"] = db.query(TopicProgress).filter(
            TopicProgress.user_id == user_id
        ).delete(synchronize_session=False)
        db.commit()
        return deleted_counts

    def get_user_summary(self, db: Session, user_id: str) -> Dict[str, Any]:
        documents = db.query(Document).filter(Document.user_id == user_id).all()
        doc_ids = [document.id for document in documents]
        if not doc_ids:
            return {
                "user_id": user_id[:8] + "...",
                "total_documents": 0,
                "total_attempts": 0,
                "overall_accuracy": 0,
                "total_weak_topics": 0,
            }

        topic_rows = db.query(TopicProgress).filter(
            TopicProgress.user_id == user_id,
            TopicProgress.document_id.in_(doc_ids),
        ).all()

        total_attempts = sum(row.attempts for row in topic_rows)
        total_correct = sum(row.correct for row in topic_rows)
        overall_accuracy = (total_correct / total_attempts * 100) if total_attempts else 0
        total_weak_topics = sum(1 for row in topic_rows if row.is_weak)

        return {
            "user_id": user_id[:8] + "...",
            "total_documents": len(documents),
            "total_attempts": total_attempts,
            "overall_accuracy": round(overall_accuracy, 1),
            "total_weak_topics": total_weak_topics,
        }


progress_service = ProgressService()
