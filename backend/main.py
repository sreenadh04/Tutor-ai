"""
MediTutor AI - FastAPI Backend
Production-safe API with user isolation, request tracing, and health checks.
"""

import contextvars
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION, DEBUG
from database import Document, SessionLocal, create_tables, engine
from routers import flashcard_router, mcq_router, pdf_router, prereq_router, progress_router, qa_router
from routers.deps import normalize_user_id
from services.llm_service import llm_service
from services.progress_service import progress_service
from services.vector_service import vector_service
from utils.cache import get_cache

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_old_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs):
    record = _old_factory(*args, **kwargs)
    record.request_id = request_id_ctx.get("-")
    return record


logging.setLogRecordFactory(_record_factory)
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | [%(request_id)s] | %(message)s",
)
logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = request.headers.get("X-User-ID") or request.query_params.get("user_id")
        request.state.user_id = None
        request.state.is_authenticated = False

        if user_id:
            try:
                request.state.user_id = normalize_user_id(user_id)
                request.state.is_authenticated = True
            except HTTPException:
                logger.warning("Rejected invalid X-User-ID value")
        response = await call_next(request)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/", "/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        if user_id:
            now = time.time()
            window_start = now - 60
            timestamps = [ts for ts in self._requests.get(user_id, []) if ts > window_start]
            if len(timestamps) >= self.requests_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Rate limit exceeded. Max {self.requests_per_minute} requests per minute.",
                        "retry_after": 60,
                    },
                )
            timestamps.append(now)
            self._requests[user_id] = timestamps
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", APP_NAME, APP_VERSION)
    create_tables()
    availability = await llm_service.check_availability()
    logger.info("LLM availability: %s", availability)
    logger.info("Vector store status: %s", await vector_service.health_check())
    yield
    engine.dispose()
    vector_service._executor.shutdown(wait=False)


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="AI-powered study assistant with isolated user storage and RAG workflows.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["X-User-ID", "X-Request-ID", "Content-Type", "Authorization"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    started = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.time() - started:.3f}s"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "-")
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again.", "request_id": request_id},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(pdf_router.router, prefix="/api/v1")
app.include_router(qa_router.router, prefix="/api/v1")
app.include_router(flashcard_router.router, prefix="/api/v1")
app.include_router(mcq_router.router, prefix="/api/v1")
app.include_router(progress_router.router, prefix="/api/v1")
app.include_router(prereq_router.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health(request: Request):
    health_status = {
        "status": "healthy",
        "app": APP_NAME,
        "version": APP_VERSION,
        "timestamp": time.time(),
    }

    try:
        health_status["llm"] = await llm_service.check_availability()
    except Exception as exc:
        health_status["llm"] = {"error": str(exc)}
        health_status["status"] = "degraded"

    try:
        health_status["vector_store"] = await vector_service.health_check()
    except Exception as exc:
        health_status["vector_store"] = {"available": False, "error": str(exc)}
        health_status["status"] = "degraded"

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_status["database"] = {"available": True}
    except Exception as exc:
        health_status["database"] = {"available": False, "error": str(exc)}
        health_status["status"] = "unhealthy"

    user_id = getattr(request.state, "user_id", None)
    health_status["auth"] = {
        "user_id_provided": user_id is not None,
        "mode": "authenticated" if user_id else "anonymous",
    }

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.delete("/api/v1/user/data")
async def delete_user_data(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header required")

    deleted = {
        "vector_files": await vector_service.delete_user_data(user_id),
        "cache_files": get_cache().clear_user_cache(user_id),
        "progress_records": 0,
        "database_records": 0,
    }

    db = SessionLocal()
    try:
        deleted["progress_records"] = sum(progress_service.delete_user_data(db, user_id).values())
        documents = db.query(Document).filter(Document.user_id == user_id).all()
        deleted["database_records"] = len(documents)
        for document in documents:
            db.delete(document)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {"message": "User data deleted successfully", "deleted": deleted}


@app.get("/api/v1/user/stats")
async def get_user_stats(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header required")

    vector_docs = await vector_service.list_user_indexes(user_id)
    return {
        "user_id": user_id[:8] + "...",
        "documents": {"count": len(vector_docs), "ids": vector_docs[:10]},
        "cache": get_cache().stats(user_id),
        "storage_path": f"/data/vectors/{user_id}",
    }
