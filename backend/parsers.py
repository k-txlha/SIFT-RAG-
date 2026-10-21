"""File parser abstraction for SIFT supporting TXT, PDF, and DOCX."""

import re
from io import BytesIO
from typing import NamedTuple, Optional


class ParsedSection(NamedTuple):
    text: str
    page_number: Optional[int] = None


class ParsingError(Exception):
    """Raised when parsing or text extraction fails."""
    pass


class UnsupportedFileError(ParsingError):
    """Raised when the file format or extension is unsupported."""
    pass


class EmptyDocumentError(ParsingError):
    """Raised when the file yields no readable text."""
    pass


def normalize_whitespace(text: str) -> str:
    """Normalize excessive whitespace while preserving paragraph flow."""
    # Replace carriage returns and excessive horizontal whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace non-breaking spaces
    text = text.replace("\u00a0", " ")
    # Collapse multiple consecutive blank lines into at most two newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading and trailing whitespace
    return text.strip()


def parse_txt(content: bytes) -> list[ParsedSection]:
    """Parse UTF-8 plain text file with fallback decoding."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception as exc:
            raise ParsingError("Could not decode text file with UTF-8 or Latin-1.") from exc

    cleaned = normalize_whitespace(text)
    if not cleaned:
        raise EmptyDocumentError("The text file is empty or contains only whitespace.")

    return [ParsedSection(text=cleaned, page_number=None)]


def parse_pdf(content: bytes) -> list[ParsedSection]:
    """Extract page-by-page text from a PDF file using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(BytesIO(content))
    except Exception as exc:
        raise ParsingError(f"Failed to read PDF file: {exc}") from exc

    if len(reader.pages) == 0:
        raise EmptyDocumentError("The PDF file contains no pages.")

    sections: list[ParsedSection] = []
    total_text = ""

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""

        cleaned = normalize_whitespace(page_text)
        if cleaned:
            sections.append(ParsedSection(text=cleaned, page_number=page_idx))
            total_text += cleaned + "\n"

    if not total_text.strip():
        raise EmptyDocumentError(
            "The PDF contains no extractable text. Scanned-only PDFs without OCR are not supported."
        )

    return sections


def parse_docx(content: bytes) -> list[ParsedSection]:
    """Extract paragraphs and table text from a Word document using python-docx."""
    try:
        import docx
        doc = docx.Document(BytesIO(content))
    except Exception as exc:
        raise ParsingError(f"Failed to read Word document: {exc}") from exc

    paragraphs: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    # Also extract text from any tables
    for table in doc.tables:
        for row in table.rows:
            row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_texts:
                paragraphs.append(" | ".join(row_texts))

    combined = "\n\n".join(paragraphs)
    cleaned = normalize_whitespace(combined)

    if not cleaned:
        raise EmptyDocumentError("The DOCX document is empty or contains no extractable text.")

    return [ParsedSection(text=cleaned, page_number=None)]


PARSERS = {
    "txt": parse_txt,
    "pdf": parse_pdf,
    "docx": parse_docx,
}


def parse_document(filename: str, content: bytes) -> tuple[str, list[ParsedSection]]:
    """Validate file type, parse content, and return normalized sections."""
    if not filename or "." not in filename:
        raise UnsupportedFileError("File must have a valid extension (.txt, .pdf, .docx).")

    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in PARSERS:
        raise UnsupportedFileError(
            f"Unsupported file type '.{ext}'. Supported formats are: .txt, .pdf, .docx."
        )

    parser = PARSERS[ext]
    sections = parser(content)
    return ext, sections
