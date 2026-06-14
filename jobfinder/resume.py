"""Resume loading. Accepts .txt / .md / .docx / .pdf and returns plain text.

The resume is User-Layer data: read-only to this app, never modified, never
uploaded except to the AI CLI the user chose for scoring (DATA_CONTRACT.md).
"""

from __future__ import annotations

import os


def load_resume(path: str) -> str:
    """Return the resume as plain text. Raises a clear error on failure rather
    than returning empty text (an empty resume would silently break scoring)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Resume not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md", ""):
        text = _read_text(path)
    elif ext == ".docx":
        text = _read_docx(path)
    elif ext == ".pdf":
        text = _read_pdf(path)
    else:
        # Best effort: try as text; if it's binary this will be obviously wrong.
        text = _read_text(path)

    text = (text or "").strip()
    if len(text) < 50:
        raise ValueError(
            f"Resume at {path} produced only {len(text)} chars of text — "
            "it may be empty, image-only, or an unsupported format. "
            "Convert it to .txt/.md/.docx/.pdf with selectable text."
        )
    return text


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_docx(path: str) -> str:
    try:
        import docx  # python-docx
    except ImportError as e:
        raise ImportError("Reading .docx needs python-docx: pip install python-docx") from e
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def _read_pdf(path: str) -> str:
    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError("Reading .pdf needs pdfplumber: pip install pdfplumber") from e
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)
