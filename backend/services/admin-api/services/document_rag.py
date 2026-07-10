"""
Qube Admin API — Document RAG (Phase 9)
Extracts text from PDF / DOCX / TXT / MD files.
OCR fallback via pytesseract when available.
"""

from __future__ import annotations

import io
import os


async def extract_text(
    raw: bytes,
    filename: str = "file",
    language: str | None = None,
) -> dict:
    """
    Extract text from raw file bytes.

    Returns:
        {
            text: str,
            language: str,
            doc_type: str,
            pages: int,
            ocr_pages: int,
        }
    """
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if suffix in (".txt", ".md", ".markdown"):
        return _extract_plaintext(raw, suffix)
    elif suffix == ".pdf":
        return await _extract_pdf(raw, language)
    elif suffix == ".docx":
        return _extract_docx(raw)
    else:
        # Try as plain text
        try:
            text = raw.decode("utf-8", errors="replace")
            return {"text": text, "language": language or "unknown", "doc_type": "text", "pages": 1, "ocr_pages": 0}
        except Exception:
            return {"text": "", "language": "unknown", "doc_type": "unknown", "pages": 0, "ocr_pages": 0}


def _extract_plaintext(raw: bytes, suffix: str) -> dict:
    text = raw.decode("utf-8", errors="replace")
    doc_type = "markdown" if suffix in (".md", ".markdown") else "text"
    return {"text": text, "language": "unknown", "doc_type": doc_type, "pages": 1, "ocr_pages": 0}


async def _extract_pdf(raw: bytes, language: str | None) -> dict:
    text_parts: list[str] = []
    page_count = 0
    ocr_pages = 0

    # Try pypdf (preferred, maintained)
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(raw))
        page_count = len(reader.pages)
        for page in reader.pages:
            t = page.extract_text() or ""
            text_parts.append(t)
    except ImportError:
        # Try pdfminer
        try:
            from pdfminer.high_level import extract_text_to_fp  # type: ignore
            from pdfminer.layout import LAParams  # type: ignore
            buf = io.StringIO()
            extract_text_to_fp(io.BytesIO(raw), buf, laparams=LAParams())
            text_parts = [buf.getvalue()]
            page_count = 1
        except ImportError:
            pass
    except Exception:
        pass

    text = "\n\n".join(t for t in text_parts if t.strip())

    # OCR fallback for scanned pages
    if not text.strip() and is_ocr_ready():
        text, ocr_pages = _ocr_pdf(raw, language)

    return {
        "text": text,
        "language": language or "unknown",
        "doc_type": "pdf",
        "pages": page_count,
        "ocr_pages": ocr_pages,
    }


def _extract_docx(raw: bytes) -> dict:
    text = ""
    try:
        import docx  # type: ignore
        doc = docx.Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        pass
    except Exception:
        pass
    return {"text": text, "language": "unknown", "doc_type": "docx", "pages": 1, "ocr_pages": 0}


def _ocr_pdf(raw: bytes, language: str | None) -> tuple[str, int]:
    """Run Tesseract OCR on every page of a PDF. Returns (text, num_ocr_pages)."""
    parts: list[str] = []
    ocr_count = 0
    try:
        import pdf2image  # type: ignore
        import pytesseract  # type: ignore
        lang_str = None
        if language == "ru":
            lang_str = "rus"
        elif language == "uz":
            lang_str = "uzb"
        images = pdf2image.convert_from_bytes(raw, dpi=200)
        for img in images:
            text = pytesseract.image_to_string(img, lang=lang_str or "eng")
            if text.strip():
                parts.append(text)
                ocr_count += 1
    except Exception:
        pass
    return "\n\n".join(parts), ocr_count


def is_ocr_ready() -> bool:
    """Return True if pytesseract + pdf2image + tesseract binary are all available."""
    try:
        import pytesseract  # type: ignore
        import pdf2image  # type: ignore
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
