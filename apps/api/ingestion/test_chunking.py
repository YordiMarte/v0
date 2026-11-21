import pytest

from ingestion.chunking import split_text


def test_empty_text_gives_no_chunks():
    assert split_text("  \n\n ", size=100, overlap=10) == []


def test_short_text_is_a_single_chunk():
    assert split_text("Hello world.", size=100, overlap=10) == ["Hello world."]


def test_chunks_never_exceed_the_size():
    text = "\n\n".join(f"Paragraph {i}. " + "lorem ipsum " * 30 for i in range(20))

    chunks = split_text(text, size=500, overlap=80)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_consecutive_chunks_overlap_and_nothing_is_lost():
    paragraphs = [f"Paragraph number {i} " + "x" * 80 for i in range(12)]

    chunks = split_text("\n\n".join(paragraphs), size=400, overlap=150)

    assert len(chunks) > 1
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert previous.split("\n\n")[-1] in current
    joined = "\n".join(chunks)
    assert all(paragraph in joined for paragraph in paragraphs)


def test_an_oversized_token_is_sliced_without_losing_content():
    chunks = split_text("a" * 2500, size=1000, overlap=100)

    assert all(len(chunk) <= 1000 for chunk in chunks)
    assert "".join(chunks) == "a" * 2500


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        split_text("text", size=100, overlap=100)
