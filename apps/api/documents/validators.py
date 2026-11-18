import re
from codecs import getincrementaldecoder
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def clean_filename(name: str) -> str:
    """Keep only the base name and drop control characters."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    return _CONTROL_CHARS.sub("", base).strip()


def extension_of(name: str) -> str:
    return PurePosixPath(name).suffix.lower()


def _describe_size(size: int) -> str:
    mebibyte = 1024 * 1024
    return f"{size // mebibyte} MB" if size >= mebibyte else f"{size} bytes"


def _check_pdf(upload) -> None:
    upload.seek(0)
    head = upload.read(1024)
    upload.seek(0)
    # PDF readers accept the header anywhere in the first 1024 bytes.
    if b"%PDF-" not in head:
        raise ValidationError("The file is not a valid PDF.")


def _check_text(upload) -> None:
    decoder = getincrementaldecoder("utf-8")()
    try:
        for chunk in upload.chunks():
            if b"\x00" in chunk:
                raise ValidationError("The file is not a plain text file.")
            decoder.decode(chunk)
        decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise ValidationError("The file must be UTF-8 text.") from exc
    finally:
        upload.seek(0)


def validate_upload(upload) -> None:
    """Validate by extension, size and actual content.

    The client controls both the extension and the declared content type, so
    neither is trusted on its own: the bytes must match the claimed type.
    """
    extension = extension_of(clean_filename(upload.name or ""))
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValidationError(f"Unsupported file type. Allowed types: {allowed}.")

    if upload.size == 0:
        raise ValidationError("The file is empty.")

    max_bytes = settings.DOCUMENT_MAX_UPLOAD_BYTES
    if upload.size > max_bytes:
        raise ValidationError(
            f"The file is too large. The maximum size is {_describe_size(max_bytes)}."
        )

    if extension == ".pdf":
        _check_pdf(upload)
    else:
        _check_text(upload)
