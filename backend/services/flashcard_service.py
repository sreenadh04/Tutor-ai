"""
MediTutor AI - Flashcard Service
Generates Q&A flashcard pairs from document chunks using LLM.
Supports Anki CSV export.
"""

import uuid
import json
import logging
import hashlib
import csv
import io
from typing import List, Optional, Tuple

from config import FLASHCARD_COUNT, MAX_CONTEXT_LENGTH
from services.llm_service import llm_service
from services.vector_service import vector_service
from utils.cache import CacheManager

logger = logging.getLogger(__name__)
cache = CacheManager()


FLASHCARD_SYSTEM_PROMPT = """You are an expert medical/educational flashcard creator.
Your flashcards are clear, concise, and test genuine understanding.
Always respond ONLY with valid JSON — no preamble, no explanation outside the JSON."""


def _flashcard_prompt(context: str, count: int, topic: Optional[str]) -> str:
    topic_clause = f" Focus specifically on the topic: '{topic}'." if topic else ""
    return f"""Based on the following study material, generate exactly {count} high-quality flashcards.{topic_clause}

MATERIAL:
{context}

Rules:
- Questions must be specific and test real understanding (not trivial facts)
- Answers should be 1-3 sentences maximum
- Cover different aspects of the material
- Vary difficulty (mix easy, medium, hard)
- Label each card with its difficulty and a short topic tag

Respond ONLY with this exact JSON format:
{{
  "flashcards": [
    {{
      "question": "What is...",
      "answer": "...",
      "topic": "short topic label",
      "difficulty": "easy|medium|hard"
    }}
  ]
}}"""


class FlashcardService:

    async def generate(
        self,
        doc_id: str,
        count: int = FLASHCARD_COUNT,
        topic: Optional[str] = None,
    ) -> Tuple[List[dict], str]:
        """
        Generate flashcards for a document (or topic within it).
        Returns (flashcards_list, model_used).
        """
        # Cache key
        cache_key = f"flashcards:{doc_id}:{topic or 'all'}:{count}"
        cached = cache.get(cache_key)
        if cached:
            logger.info("Flashcard cache hit")
            return cached["cards"], cached["model"] + " (cached)"

        # Retrieve relevant chunks
        query = topic if topic else "key concepts definitions important facts"
        chunks = vector_service.search(doc_id, query, top_k=8)

        if not chunks:
            raise ValueError("No content found. Make sure the PDF is uploaded.")

        # Build context
        context = self._build_context(chunks)
        prompt = _flashcard_prompt(context, count, topic)

        # Generate
        raw_text, model = await llm_service.generate(
            prompt=prompt,
            system=FLASHCARD_SYSTEM_PROMPT,
            max_tokens=2048,
            use_cache=False,  # We cache ourselves
        )

        # Parse JSON
        cards = self._parse_flashcards(raw_text, count)

        # Attach IDs
        for card in cards:
            card["id"] = str(uuid.uuid4())

        cache.set(cache_key, {"cards": cards, "model": model})
        return cards, model

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

    def _parse_flashcards(self, raw: str, expected_count: int) -> List[dict]:
        """Robust JSON parser — handles LLM formatting quirks."""
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        # Find first { and last }
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error(f"No JSON found in LLM output: {raw[:200]}")
            return self._fallback_flashcards(raw, expected_count)

        try:
            data = json.loads(raw[start:end])
            cards = data.get("flashcards", [])
            
            # Validate and clean
            valid = []
            for c in cards:
                if c.get("question") and c.get("answer"):
                    valid.append({
                        "question": str(c["question"]).strip(),
                        "answer": str(c["answer"]).strip(),
                        "topic": str(c.get("topic", "General")).strip(),
                        "difficulty": c.get("difficulty", "medium"),
                    })
            return valid
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._fallback_flashcards(raw, expected_count)

    def _fallback_flashcards(self, raw: str, count: int) -> List[dict]:
        """Last resort: try to extract Q&A pairs from plain text."""
        cards = []
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        i = 0
        while i < len(lines) and len(cards) < count:
            line = lines[i]
            if line.lower().startswith("q:") or line.lower().startswith("question:"):
                q = line.split(":", 1)[-1].strip()
                if i + 1 < len(lines):
                    a_line = lines[i + 1]
                    if a_line.lower().startswith("a:") or a_line.lower().startswith("answer:"):
                        a = a_line.split(":", 1)[-1].strip()
                        cards.append({
                            "question": q,
                            "answer": a,
                            "topic": "General",
                            "difficulty": "medium",
                        })
                        i += 2
                        continue
            i += 1
        return cards

    def to_anki_csv(self, cards: List[dict]) -> str:
        """
        Export flashcards in Anki-compatible CSV format.
        Format: Front, Back, Tags
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        for card in cards:
            tags = f"meditutor {card.get('topic','').replace(' ', '_')} {card.get('difficulty','medium')}"
            writer.writerow([card["question"], card["answer"], tags])
        return output.getvalue()


# ─── Singleton ────────────────────────────────────────────────────────────────
flashcard_service = FlashcardService()
