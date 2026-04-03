"""
MediTutor AI - Configuration
All settings loaded from environment variables with safe defaults.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
VECTOR_DIR = DATA_DIR / "vectors"
DB_DIR = DATA_DIR / "db"
UPLOAD_DIR = DATA_DIR / "uploads"
CACHE_DIR = DATA_DIR / "cache"

for directory in [DATA_DIR, VECTOR_DIR, DB_DIR, UPLOAD_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")

GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "gemma2-9b-it",
]

HF_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "HuggingFaceH4/zephyr-7b-beta",
    "microsoft/phi-2",
]

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
HF_API_URL = "https://api-inference.huggingface.co/models/{model}"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MAX_PDF_SIZE_MB = 50

TOP_K_CHUNKS = 5
MAX_CONTEXT_LENGTH = 3000

MAX_TOKENS = 1024
TEMPERATURE = 0.3
FLASHCARD_COUNT = 10
MCQ_COUNT = 5

GROQ_RPM = 30
HF_RPM = 10
REQUEST_TIMEOUT = 60
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

CACHE_TTL = 3600
MAX_CACHE_SIZE = 500

DATABASE_URL = f"sqlite:///{DB_DIR}/meditutor.db"


def _parse_allowed_origins() -> list[str]:
    raw = os.getenv(
        "ALLOWED_ORIGINS",
        "https://meditutor-frontend.onrender.com,http://localhost:8501,http://127.0.0.1:8501",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip() and origin.strip() != "*"]
    return origins


ALLOWED_ORIGINS = _parse_allowed_origins()

APP_NAME = "MediTutor AI"
APP_VERSION = "1.0.0"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
