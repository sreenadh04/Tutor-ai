"""
MediTutor AI - MCQ Service
Generates multiple-choice questions with 4 options, correct answer & explanation.
"""

import uuid
import json
import logging
import random
from typing import List, Optional, Tuple

from config import MCQ_COUNT, MAX_CONTEXT_LENGTH
from services.llm_service import llm_service
from services.vector_service import vector_service
from utils.cache import CacheManager

logger = logging.getLogger(__name__)
cache = CacheManager()


MCQ_SYSTEM_PROMPT = """You are an expert medical/educational exam question writer.
You write clear, unambiguous multiple-choice questions with exactly 4 options.
Always respond ONLY with valid JSON — no preamble, no explanation outside the JSON."""


def _mcq_prompt(context: str, count: int, topic: Optional[str]) -> str:
    topic_clause = f" Focus specifically on: '{topic}'." if topic else ""
    return f"""Based on the following study material, generate exactly {count} multiple-choice questions.{topic_clause}

MATERIAL:
{context}

Rules:
- Each question must have EXACTLY 4 options (A, B, C, D)
- Only ONE option is correct
- Distractors must be plausible (not obviously wrong)
- Include a clear explanation for the correct answer
- Tag each question with its topic

Respond ONLY with this JSON format:
{{
  "questions": [
    {{
      "question": "Which of the following best describes...?",
      "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
      "correct_index": 0,
      "explanation": "Option A is correct because...",
      "topic": "short topic label"
    }}
  ]
}}"""


class MCQService:

    async def generate(
        self,
        doc_id: str,
        count: int = MCQ_COUNT,
        topic: Optional[str] = None,
    ) -> Tuple[List[dict], str]:
        """
        Generate MCQs for a document.
        Returns (questions_list, model_used).
        """
        cache_key = f"mcqs:{doc_id}:{topic or 'all'}:{count}"
        cached = cache.get(cache_key)
        if cached:
            return cached["questions"], cached["model"] + " (cached)"

        query = topic if topic else "important concepts mechanisms processes"
        chunks = vector_service.search(doc_id, query, top_k=8)

        if not chunks:
            raise ValueError("No content found. Upload a PDF first.")

        context = self._build_context(chunks)
        prompt = _mcq_prompt(context, count, topic)

        raw_text, model = await llm_service.generate(
            prompt=prompt,
            system=MCQ_SYSTEM_PROMPT,
            max_tokens=2048,
            use_cache=False,
        )

        questions = self._parse_mcqs(raw_text, count)
        for q in questions:
            q["id"] = str(uuid.uuid4())

        cache.set(cache_key, {"questions": questions, "model": model})
        return questions, model

    def _build_context(self, chunks: List[dict]) -> str:
        parts = []
        total = 0
        for chunk in chunks:
            text = chunk["text"]
            page = chunk.get("page_number", "?")
            if total + len(text) > MAX_CONTEXT_LENGTH:
                break
            parts.append(f"[Page {page}]\n{text}")
            total += len(text)
        return "\n\n---\n\n".join(parts)

    def _parse_mcqs(self, raw: str, expected_count: int) -> List[dict]:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error(f"No JSON in MCQ output: {raw[:200]}")
            return []

        try:
            data = json.loads(raw[start:end])
            raw_qs = data.get("questions", [])
            
            valid = []
            for q in raw_qs:
                opts = q.get("options", [])
                if not q.get("question") or len(opts) != 4:
                    continue
                correct = int(q.get("correct_index", 0))
                if correct not in range(4):
                    correct = 0
                valid.append({
                    "question": str(q["question"]).strip(),
                    "options": [str(o).strip() for o in opts[:4]],
                    "correct_index": correct,
                    "explanation": str(q.get("explanation", "")).strip(),
                    "topic": str(q.get("topic", "General")).strip(),
                })
            return valid
        except json.JSONDecodeError as e:
            logger.error(f"MCQ JSON parse error: {e}")
            return []

    def grade_submission(
        self,
        questions_map: dict,
        submission: List[dict],
    ) -> dict:
        """
        Grade a submitted quiz.
        questions_map: {question_id: MCQ dict}
        submission: [{question_id, selected_index, topic}]
        """
        results = []
        correct_count = 0

        for item in submission:
            qid = item.get("question_id")
            selected = item.get("selected_index", -1)
            q = questions_map.get(qid)

            if not q:
                continue

            is_correct = selected == q["correct_index"]
            if is_correct:
                correct_count += 1

            results.append({
                "question_id": qid,
                "question": q["question"],
                "selected_index": selected,
                "correct_index": q["correct_index"],
                "is_correct": is_correct,
                "explanation": q["explanation"],
                "topic": q.get("topic", "General"),
            })

        total = len(results)
        score = (correct_count / total * 100) if total else 0

        return {
            "total": total,
            "correct": correct_count,
            "score": round(score, 1),
            "feedback": results,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────
mcq_service = MCQService()
