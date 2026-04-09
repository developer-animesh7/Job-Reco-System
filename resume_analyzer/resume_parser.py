import logging
from pathlib import Path

import pdfplumber
from docx import Document

logger = logging.getLogger(__name__)


def _extract_text_from_pdf(file_path: str) -> str:
    lines = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                lines.append(text)
    return "\n".join(lines).strip()


def _extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    lines = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
    return "\n".join(lines).strip()


def extract_text(file_path: str) -> str:
    """Extract plain text from PDF or DOCX file."""
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        text = _extract_text_from_pdf(file_path)
    elif suffix == ".docx":
        text = _extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported resume format. Only PDF and DOCX are allowed.")

    if not text:
        raise ValueError("Could not extract text from resume.")

    return text


def extract_skills(text: str):
    """Backward-compat helper; Gemini extraction is used in views."""
    return {"skills": []}
