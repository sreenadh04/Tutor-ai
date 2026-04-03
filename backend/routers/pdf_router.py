"""
MediTutor AI - PDF Router
Upload, process, and manage PDFs with per-user ownership enforcement.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from config import MAX_PDF_SIZE_MB
from database import Document, get_db
from models import DocumentListResponse, DocumentResponse
from routers.deps import get_owned_document, get_request_user_id
from services.pdf_service import pdf_service
from services.vector_service import vector_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pdf", tags=["PDF"])

MAX_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024


@router.post("/upload", response_model=DocumentResponse)
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(request)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_PDF_SIZE_MB} MB.")
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="File appears to be empty.")

    try:
        doc_id, chunks, stats = pdf_service.process_pdf(content, file.filename, user_id=user_id)
        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="Could not extract text from this PDF. It may be image-only (scanned).",
            )

        await vector_service.build_index(user_id=user_id, doc_id=doc_id, chunks=chunks)
        document = Document(
            id=doc_id,
            filename=file.filename,
            total_pages=stats.get("total_pages", 0),
            total_chunks=len(chunks),
            vector_store_path=f"{user_id}/{doc_id}",
            user_id=user_id,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return DocumentResponse.model_validate(document)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Upload failed for user %s: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Processing failed.") from exc


@router.get("/list", response_model=DocumentListResponse)
async def list_documents(request: Request, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    documents = db.query(Document).filter(Document.user_id == user_id).order_by(Document.created_at.desc()).all()
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(document) for document in documents],
        total=len(documents),
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(request: Request, doc_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    document = get_owned_document(db, user_id, doc_id)
    return DocumentResponse.model_validate(document)


@router.delete("/{doc_id}")
async def delete_document(request: Request, doc_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    document = get_owned_document(db, user_id, doc_id)

    await vector_service.delete_index(user_id, doc_id)
    upload_path = pdf_service.find_upload(user_id, doc_id)
    if upload_path and upload_path.exists():
        upload_path.unlink()

    db.delete(document)
    db.commit()
    return {"message": "Document deleted successfully.", "id": doc_id, "filename": document.filename}


@router.head("/{doc_id}/exists")
async def check_document_exists(request: Request, doc_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    exists = db.query(Document).filter(Document.id == doc_id, Document.user_id == user_id).first() is not None
    if not exists:
        raise HTTPException(status_code=404)
    return {"exists": True}


@router.post("/{doc_id}/reprocess")
async def reprocess_document(request: Request, doc_id: str, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    document = get_owned_document(db, user_id, doc_id)
    upload_path = pdf_service.find_upload(user_id, doc_id)
    if not upload_path:
        raise HTTPException(status_code=404, detail="Original PDF file not found. Please re-upload.")

    try:
        with open(upload_path, "rb") as handle:
            content = handle.read()
        _, chunks, stats = pdf_service.process_pdf(
            content,
            document.filename,
            user_id=user_id,
            doc_id=doc_id,
        )
        await vector_service.delete_index(user_id, doc_id)
        await vector_service.build_index(user_id=user_id, doc_id=doc_id, chunks=chunks)
        document.total_pages = stats.get("total_pages", 0)
        document.total_chunks = len(chunks)
        document.vector_store_path = f"{user_id}/{doc_id}"
        db.commit()
        return {
            "message": "Document reprocessed successfully",
            "doc_id": doc_id,
            "total_chunks": len(chunks),
            "total_pages": stats.get("total_pages", 0),
        }
    except Exception as exc:
        logger.error("Reprocess error for user %s document %s: %s", user_id, doc_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Reprocessing failed.") from exc


@router.get("/stats/summary")
async def get_user_stats(request: Request, db: Session = Depends(get_db)):
    user_id = get_request_user_id(request)
    documents = db.query(Document).filter(Document.user_id == user_id).all()
    total_chunks = sum(document.total_chunks or 0 for document in documents)
    vector_docs = await vector_service.list_user_indexes(user_id)
    return {
        "user_id": user_id[:8] + "...",
        "documents": {"total": len(documents), "ids": vector_docs[:10]},
        "storage": {"total_chunks": total_chunks, "approx_size_kb": total_chunks * 1.5},
    }
