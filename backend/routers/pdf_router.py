"""
MediTutor AI - PDF Router
Upload, process, and manage PDF documents.
"""

import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Query
from sqlalchemy.orm import Session

from database import get_db, Document
from models import DocumentResponse, DocumentListResponse
from services.pdf_service import pdf_service
from services.vector_service import vector_service
from config import MAX_PDF_SIZE_MB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pdf", tags=["PDF"])

MAX_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024


@router.post("/upload", response_model=DocumentResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload and process a PDF:
    1. Extract text page-by-page
    2. Split into overlapping chunks
    3. Embed and store in FAISS
    4. Save document record to SQLite
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()

    # Validate size
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_PDF_SIZE_MB} MB."
        )

    if len(content) < 100:
        raise HTTPException(status_code=400, detail="File appears to be empty.")

    try:
        # Process PDF
        doc_id, chunks, stats = pdf_service.process_pdf(content, file.filename)

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="Could not extract text from this PDF. It may be image-only (scanned)."
            )

        # Build vector index
        vector_service.build_index(doc_id, chunks)

        # Save to database
        doc = Document(
            id=doc_id,
            filename=file.filename,
            total_pages=stats.get("total_pages", 0),
            total_chunks=len(chunks),
            vector_store_path=str(doc_id),
            user_id=user_id,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        logger.info(f"Uploaded and indexed: {file.filename} ({len(chunks)} chunks)")
        return DocumentResponse.from_orm(doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/list", response_model=DocumentListResponse)
def list_documents(user_id: str = Query(...), db: Session = Depends(get_db)):
    """List all uploaded documents."""
    docs = db.query(Document).filter(
    Document.user_id == user_id
).order_by(Document.created_at.desc()).all()
    return DocumentListResponse(
        documents=[DocumentResponse.from_orm(d) for d in docs],
        total=len(docs),
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: str, db: Session = Depends(get_db)):
    """Get a single document's details."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.from_orm(doc)


@router.delete("/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """Delete a document and its vector index."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    vector_service.delete_index(doc_id)
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully.", "id": doc_id}
