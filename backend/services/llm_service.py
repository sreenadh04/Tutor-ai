"""
MediTutor AI - LLM Service
Multi-model fallback: Groq -> HuggingFace Inference API with per-user rate limiting.
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from typing import Optional, Tuple

import httpx

from config import (
    GROQ_API_KEY,
    GROQ_API_URL,
    GROQ_MODELS,
    GROQ_RPM,
    HF_API_URL,
    HF_MODELS,
    HF_RPM,
    HUGGINGFACE_API_KEY,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    TEMPERATURE,
)
from utils.cache import get_cache

logger = logging.getLogger(__name__)
cache = get_cache()


class PerUserRateLimiter:
    def __init__(self, requests_per_minute: int):
        self.min_interval = 60.0 / requests_per_minute
        self._last_call: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    async def wait(self, user_id: Optional[str]):
        key = user_id or "anonymous"
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_call[key]
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_call[key] = time.time()


groq_limiter = PerUserRateLimiter(GROQ_RPM)
hf_limiter = PerUserRateLimiter(HF_RPM)


class LLMService:
    def __init__(self):
        self.groq_available = bool(GROQ_API_KEY)
        self.hf_available = bool(HUGGINGFACE_API_KEY)

    @staticmethod
    def _cache_key(prompt: str, system: str) -> str:
        return "llm:" + hashlib.sha256(f"{system}|||{prompt}".encode("utf-8")).hexdigest()

    async def _call_groq(
        self,
        messages: list,
        model: str,
        user_id: Optional[str],
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
    ) -> str:
        await groq_limiter.wait(user_id)
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(GROQ_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

    async def _call_huggingface(
        self,
        prompt: str,
        model: str,
        user_id: Optional[str],
        max_tokens: int = MAX_TOKENS,
    ) -> str:
        await hf_limiter.wait(user_id)
        url = HF_API_URL.format(model=model)
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": TEMPERATURE,
                "return_full_text": False,
                "do_sample": True,
            },
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            for _ in range(RETRY_ATTEMPTS):
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 503:
                    wait_time = min(response.json().get("estimated_time", 20), 30)
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list) and data:
                    return data[0].get("generated_text", "").strip()
                return str(data)

        raise RuntimeError("HuggingFace model failed after retries")

    @staticmethod
    def _format_hf_prompt(system: str, user: str) -> str:
        return f"<s>[INST] {system}\n\n{user} [/INST]"

    async def generate(
        self,
        prompt: str,
        system: str = "You are MediTutor AI, a helpful medical/educational assistant.",
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
        use_cache: bool = True,
        user_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        cache_key = self._cache_key(prompt, system)
        if use_cache and user_id:
            cached = cache.get(user_id, cache_key)
            if cached:
                return cached["text"], f'{cached["model"]} (cached)'

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        if self.groq_available:
            for model in GROQ_MODELS:
                for attempt in range(RETRY_ATTEMPTS):
                    try:
                        text = await self._call_groq(messages, model, user_id, max_tokens, temperature)
                        if use_cache and user_id:
                            cache.set(user_id, cache_key, {"text": text, "model": model})
                        return text, model
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 429:
                            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                            continue
                        if exc.response.status_code in {400, 401, 403}:
                            logger.warning("Groq auth/request error for model %s: %s", model, exc)
                            break
                        logger.warning("Groq error for model %s attempt %s: %s", model, attempt + 1, exc)
                        await asyncio.sleep(RETRY_DELAY)
                    except Exception as exc:
                        logger.warning("Groq failure for model %s attempt %s: %s", model, attempt + 1, exc)
                        await asyncio.sleep(RETRY_DELAY)

        if self.hf_available:
            hf_prompt = self._format_hf_prompt(system, prompt)
            for model in HF_MODELS:
                for attempt in range(RETRY_ATTEMPTS):
                    try:
                        text = await self._call_huggingface(hf_prompt, model, user_id, max_tokens)
                        if use_cache and user_id:
                            cache.set(user_id, cache_key, {"text": text, "model": model})
                        return text, model
                    except Exception as exc:
                        logger.warning("HF failure for model %s attempt %s: %s", model, attempt + 1, exc)
                        await asyncio.sleep(RETRY_DELAY)

        raise RuntimeError(
            "All LLM providers failed. Configure GROQ_API_KEY and/or HUGGINGFACE_API_KEY."
        )

    async def check_availability(self) -> dict:
        return {
            "groq": {"configured": self.groq_available, "models": GROQ_MODELS},
            "huggingface": {"configured": self.hf_available, "models": HF_MODELS},
        }


llm_service = LLMService()
