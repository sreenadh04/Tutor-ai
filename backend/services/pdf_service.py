"""
MediTutor AI - PDF Service
Extract text from PDFs, chunk intelligently, and store embeddings in FAISS.
"""

import uuid
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import fitz                        # PyMuPDF — best for text extraction
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    UPLOAD_DIR, CHUNK_SIZE, CHUNK_OVERLAP, VECTOR_DIR
)

logger = logging.getLogger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────

class TextChunk:
    """A single chunk of text with metadata."""
    def __init__(self, text: str, page_number: int, chunk_index: int, doc_id: str):
        self.text = text
        self.page_number = page_number
        self.chunk_index = chunk_index
        self.doc_id = doc_id
        self.id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "doc_id": self.doc_id,
        }


# ─── PDF Service ──────────────────────────────────────────────────────────────

class PDFService:

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
        )

    def extract_text_with_pages(self, pdf_path: Path) -> List[Dict]:
        """
        Extract text page-by-page using PyMuPDF.
        Returns list of {page_number, text} dicts.
        """
        pages = []
        try:
            doc = fitz.open(str(pdf_path))
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append({
                        "page_number": page_num,
                        "text": text,
                    })
            doc.close()
            logger.info(f"Extracted {len(pages)} pages from {pdf_path.name}")
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            raise ValueError(f"Could not read PDF: {e}")
        
        return pages

    def chunk_pages(self, pages: List[Dict], doc_id: str) -> List[TextChunk]:
        """
        Split page text into overlapping chunks.
        Preserves page number in metadata.
        """
        chunks: List[TextChunk] = []
        chunk_index = 0

        for page_data in pages:
            page_num = page_data["page_number"]
            page_text = page_data["text"]

            # Split the page text
            splits = self.splitter.split_text(page_text)
            for split in splits:
                if len(split.strip()) < 50:  # skip tiny fragments
                    continue
                chunk = TextChunk(
                    text=split.strip(),
                    page_number=page_num,
                    chunk_index=chunk_index,
                    doc_id=doc_id,
                )
                chunks.append(chunk)
                chunk_index += 1

        logger.info(f"Created {len(chunks)} chunks for doc {doc_id}")
        return chunks

    def get_document_stats(self, pdf_path: Path) -> dict:
        """Return quick stats about a PDF without full processing."""
        try:
            doc = fitz.open(str(pdf_path))
            stats = {
                "total_pages": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
            }
            doc.close()
            return stats
        except Exception as e:
            return {"total_pages": 0, "title": "", "author": ""}

    def save_upload(self, file_content: bytes, filename: str) -> Tuple[Path, str]:
        """
        Save uploaded PDF to disk.
        Returns (path, doc_id).
        """
        doc_id = str(uuid.uuid4())
        safe_name = f"{doc_id}_{filename}"
        save_path = UPLOAD_DIR / safe_name
        
        with open(save_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"Saved upload: {save_path}")
        return save_path, doc_id

    def process_pdf(
        self, file_content: bytes, filename: str
    ) -> Tuple[str, List[TextChunk], dict]:
        """
        Full pipeline: save → extract → chunk.
        Returns (doc_id, chunks, stats).
        """
        pdf_path, doc_id = self.save_upload(file_content, filename)
        stats = self.get_document_stats(pdf_path)
        pages = self.extract_text_with_pages(pdf_path)
        chunks = self.chunk_pages(pages, doc_id)
        
        stats["total_chunks"] = len(chunks)
        stats["doc_id"] = doc_id
        stats["filename"] = filename
        
        return doc_id, chunks, stats


# ─── Singleton ────────────────────────────────────────────────────────────────
pdf_service = PDFService()
