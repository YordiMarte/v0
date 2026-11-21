import pytest

from ingestion.errors import IngestionError
from ingestion.extraction import extract_text


def test_text_is_decoded_as_utf8():
    assert extract_text("café".encode(), "text/plain") == "café"


def test_utf8_bom_is_removed():
    assert extract_text(b"\xef\xbb\xbfhello", "text/plain") == "hello"


def test_invalid_utf8_is_reported():
    with pytest.raises(IngestionError):
        extract_text(b"\xff\xfe\xfa", "text/plain")


def test_pdf_text_is_extracted(make_pdf):
    text = extract_text(make_pdf("Kivoff builds custom software"), "application/pdf")

    assert "Kivoff builds custom software" in text


def test_unreadable_pdf_is_reported():
    with pytest.raises(IngestionError):
        extract_text(b"%PDF-1.4 this is not really a pdf", "application/pdf")
