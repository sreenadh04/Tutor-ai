"""
MediTutor AI - PDF Service
Extract text from PDFs, chunk content, and persist uploads locally.
"""

import logging
import re
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_OVERLAP, CHUNK_SIZE, UPLOAD_DIR

logger = logging.getLogger(__name__)

_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class TextChunk:
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


def _safe_component(value: str) -> str:
    return _SAFE_NAME_PATTERN.sub("_", value.strip())


class PDFService:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
        )

    def extract_text_with_pages(self, pdf_path: Path) -> List[Dict]:
        pages = []
        try:
            document = fitz.open(str(pdf_path))
            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append({"page_number": page_number, "text": text})
            document.close()
        except Exception as exc:
            raise ValueError(f"Could not read PDF: {exc}") from exc
        return pages

    def chunk_pages(self, pages: List[Dict], doc_id: str) -> List[TextChunk]:
        chunks: List[TextChunk] = []
        chunk_index = 0

        for page_data in pages:
            for split in self.splitter.split_text(page_data["text"]):
                cleaned = split.strip()
                if len(cleaned) < 50:
                    continue
                chunks.append(
                    TextChunk(
                        text=cleaned,
                        page_number=page_data["page_number"],
                        chunk_index=chunk_index,
                        doc_id=doc_id,
                    )
                )
                chunk_index += 1
        return chunks

    def get_document_stats(self, pdf_path: Path) -> dict:
        try:
            document = fitz.open(str(pdf_path))
            stats = {
                "total_pages": len(document),
                "title": document.metadata.get("title", ""),
                "author": document.metadata.get("author", ""),
            }
            document.close()
            return stats
        except Exception:
            return {"total_pages": 0, "title": "", "author": ""}

    def save_upload(self, file_content: bytes, filename: str, user_id: str, doc_id: str) -> Path:
        user_dir = UPLOAD_DIR / _safe_component(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        save_path = user_dir / f"{_safe_component(doc_id)}_{_safe_component(filename)}"
        with open(save_path, "wb") as handle:
            handle.write(file_content)
        return save_path

    def find_upload(self, user_id: str, doc_id: str) -> Path | None:
        user_dir = UPLOAD_DIR / _safe_component(user_id)
        if not user_dir.exists():
            return None
        matches = list(user_dir.glob(f"{_safe_component(doc_id)}_*"))
        return matches[0] if matches else None

    def process_pdf(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        doc_id: str | None = None,
    ) -> Tuple[str, List[TextChunk], dict]:
        document_id = doc_id or str(uuid.uuid4())
        pdf_path = self.save_upload(file_content, filename, user_id, document_id)
        stats = self.get_document_stats(pdf_path)
        pages = self.extract_text_with_pages(pdf_path)
        chunks = self.chunk_pages(pages, document_id)
        stats["total_chunks"] = len(chunks)
        stats["doc_id"] = document_id
        stats["filename"] = filename
        return document_id, chunks, stats


pdf_service = PDFService()
