import io

from pypdf import PdfReader

from ingestion.errors import IngestionError


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError("The file is not valid UTF-8 text.") from exc


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise IngestionError("Password-protected PDFs are not supported.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError("The PDF could not be read.") from exc
    return "\n\n".join(pages)


def extract_text(data: bytes, content_type: str) -> str:
    """Return the plain text of a stored document."""
    if content_type == "application/pdf":
        return _extract_pdf(data)
    return _decode_text(data)
