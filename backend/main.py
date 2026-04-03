"""
MediTutor AI — FastAPI Backend
Production-ready educational AI assistant backend.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from config import APP_NAME, APP_VERSION, ALLOWED_ORIGINS, DEBUG
from database import create_tables
from routers import pdf_router, qa_router, flashcard_router, mcq_router, progress_router, prereq_router
from services.llm_service import llm_service

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {APP_NAME} v{APP_VERSION}")
    create_tables()
    logger.info("✅ Database tables ready")
    
    avail = await llm_service.check_availability()
    if avail["groq"]["configured"]:
        logger.info("✅ Groq API configured")
    else:
        logger.warning("⚠️  Groq API key not set — will use HuggingFace only")
    if avail["huggingface"]["configured"]:
        logger.info("✅ HuggingFace API configured")
    else:
        logger.warning("⚠️  HuggingFace API key not set")
    
    yield  # App running
    
    logger.info("🛑 Shutting down MediTutor AI")


# ─── App Instance ─────────────────────────────────────────────────────────────
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="AI-powered study assistant with RAG, flashcards, MCQs, and progress tracking.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS + ["*"],   # Restrict in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.time() - start):.3f}s"
    return response


# ─── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(pdf_router.router, prefix="/api/v1")
app.include_router(qa_router.router, prefix="/api/v1")
app.include_router(flashcard_router.router, prefix="/api/v1")
app.include_router(mcq_router.router, prefix="/api/v1")
app.include_router(progress_router.router, prefix="/api/v1")
app.include_router(prereq_router.router, prefix="/api/v1")


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health():
    avail = await llm_service.check_availability()
    return {
        "status": "healthy",
        "app": APP_NAME,
        "version": APP_VERSION,
        "models": avail,
    }


# ─── Dev runner ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG)
