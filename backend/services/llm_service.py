"""
MediTutor AI - LLM Service
Multi-model fallback: Groq → HuggingFace Inference API
Includes rate limiting, retry logic, and caching.
"""

import time
import json
import logging
import hashlib
import asyncio
from typing import Optional, Tuple
import httpx
from config import (
    GROQ_API_KEY, HUGGINGFACE_API_KEY,
    GROQ_API_URL, HF_API_URL,
    GROQ_MODELS, HF_MODELS,
    MAX_TOKENS, TEMPERATURE,
    REQUEST_TIMEOUT, RETRY_ATTEMPTS, RETRY_DELAY,
    GROQ_RPM, HF_RPM
)
from utils.cache import CacheManager

logger = logging.getLogger(__name__)
cache = CacheManager()

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.rpm = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_call = 0.0
        self._lock = asyncio.Lock()

    async def wait(self):
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_call = time.time()


groq_limiter = RateLimiter(GROQ_RPM)
hf_limiter = RateLimiter(HF_RPM)


# ─── Core LLM Class ───────────────────────────────────────────────────────────

class LLMService:
    """
    Tries models in this order:
      1. Groq (llama-3.1-8b-instant) — fastest free tier
      2. Groq fallback models
      3. HuggingFace Inference API models
    """

    def __init__(self):
        self.groq_available = bool(GROQ_API_KEY)
        self.hf_available = bool(HUGGINGFACE_API_KEY)

    # ── Cache key helper ──────────────────────────────────────────────────────
    @staticmethod
    def _cache_key(prompt: str, system: str) -> str:
        combined = f"{system}|||{prompt}"
        return "llm:" + hashlib.md5(combined.encode()).hexdigest()

    # ── Groq call ─────────────────────────────────────────────────────────────
    async def _call_groq(
        self,
        messages: list,
        model: str,
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
    ) -> str:
        await groq_limiter.wait()

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
            resp = await client.post(GROQ_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    # ── HuggingFace call ──────────────────────────────────────────────────────
    async def _call_huggingface(
        self,
        prompt: str,
        model: str,
        max_tokens: int = MAX_TOKENS,
    ) -> str:
        await hf_limiter.wait()

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
            for attempt in range(3):
                resp = await client.post(url, json=payload, headers=headers)
                
                # Model loading — wait and retry
                if resp.status_code == 503:
                    wait_time = resp.json().get("estimated_time", 20)
                    logger.info(f"HF model loading, waiting {wait_time}s...")
                    await asyncio.sleep(min(wait_time, 30))
                    continue
                
                resp.raise_for_status()
                data = resp.json()
                
                if isinstance(data, list) and data:
                    return data[0].get("generated_text", "").strip()
                return str(data)
        
        raise Exception("HuggingFace model failed after retries")

    # ── Format prompt for HF models ───────────────────────────────────────────
    @staticmethod
    def _format_hf_prompt(system: str, user: str) -> str:
        return f"<s>[INST] {system}\n\n{user} [/INST]"

    # ── Main generate method with full fallback chain ─────────────────────────
    async def generate(
        self,
        prompt: str,
        system: str = "You are MediTutor AI, a helpful medical/educational assistant.",
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
        use_cache: bool = True,
    ) -> Tuple[str, str]:
        """
        Returns: (response_text, model_name_used)
        """
        # Check cache first
        if use_cache:
            cache_key = self._cache_key(prompt, system)
            cached = cache.get(cache_key)
            if cached:
                logger.info("LLM cache hit")
                return cached["text"], cached["model"] + " (cached)"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        # ── Try Groq models ──────────────────────────────────────────────────
        if self.groq_available:
            for model in GROQ_MODELS:
                for attempt in range(RETRY_ATTEMPTS):
                    try:
                        text = await self._call_groq(messages, model, max_tokens, temperature)
                        logger.info(f"Groq success: {model}")
                        if use_cache:
                            cache.set(cache_key, {"text": text, "model": model})
                        return text, model
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            # Rate limited — wait and retry
                            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                            continue
                        elif e.response.status_code in [400, 401, 403]:
                            # Auth or bad request — skip this model
                            logger.warning(f"Groq {model} auth error: {e}")
                            break
                        logger.warning(f"Groq {model} attempt {attempt+1} failed: {e}")
                        await asyncio.sleep(RETRY_DELAY)
                    except Exception as e:
                        logger.warning(f"Groq {model} attempt {attempt+1} error: {e}")
                        await asyncio.sleep(RETRY_DELAY)

        # ── Try HuggingFace models ────────────────────────────────────────────
        if self.hf_available:
            hf_prompt = self._format_hf_prompt(system, prompt)
            for model in HF_MODELS:
                for attempt in range(RETRY_ATTEMPTS):
                    try:
                        text = await self._call_huggingface(hf_prompt, model, max_tokens)
                        logger.info(f"HuggingFace success: {model}")
                        if use_cache:
                            cache.set(cache_key, {"text": text, "model": model})
                        return text, model
                    except Exception as e:
                        logger.warning(f"HF {model} attempt {attempt+1} error: {e}")
                        await asyncio.sleep(RETRY_DELAY)

        # ── Complete failure ──────────────────────────────────────────────────
        raise Exception(
            "All LLM providers failed. Check your API keys and rate limits. "
            "Add GROQ_API_KEY and/or HUGGINGFACE_API_KEY to your .env file."
        )

    async def check_availability(self) -> dict:
        """Quick check of which providers are configured."""
        return {
            "groq": {
                "configured": self.groq_available,
                "models": GROQ_MODELS,
            },
            "huggingface": {
                "configured": self.hf_available,
                "models": HF_MODELS,
            },
        }


# ─── Singleton instance ───────────────────────────────────────────────────────
llm_service = LLMService()
