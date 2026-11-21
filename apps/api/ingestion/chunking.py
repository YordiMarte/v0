import re
from collections.abc import Iterator


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return text.strip()


def _hard_split(piece: str, size: int) -> Iterator[str]:
    """Split an oversized piece on word boundaries (and slice pathological tokens)."""
    if not piece:
        return
    if len(piece) <= size:
        yield piece
        return

    current = ""
    for word in piece.split():
        while len(word) > size:
            if current:
                yield current
                current = ""
            yield word[:size]
            word = word[size:]
        if not word:
            continue
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= size:
            current += " " + word
        else:
            yield current
            current = word
    if current:
        yield current


def _units(text: str, size: int) -> Iterator[str]:
    """Paragraphs, falling back to sentences and then words when too long."""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= size:
            yield paragraph
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            yield from _hard_split(sentence.strip(), size)


def split_text(text: str, *, size: int = 1000, overlap: int = 150) -> list[str]:
    """Split text into chunks of at most `size` characters.

    Chunks follow paragraph and sentence boundaries. Each chunk starts with the
    last whole units of the previous one (up to `overlap` characters), so an
    idea cut at a boundary still appears intact in one of the two chunks.
    """
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks: list[str] = []
    window: list[str] = []
    length = 0

    for unit in _units(normalize_text(text), size):
        added = len(unit) + (2 if window else 0)

        if window and length + added > size:
            chunks.append("\n\n".join(window))

            carry: list[str] = []
            carried = 0
            for previous in reversed(window):
                if carried + len(previous) + 2 > overlap:
                    break
                carry.insert(0, previous)
                carried += len(previous) + 2

            window = carry
            length = sum(len(item) for item in window) + 2 * max(len(window) - 1, 0)
            added = len(unit) + (2 if window else 0)
            if length + added > size:
                window, length, added = [], 0, len(unit)

        window.append(unit)
        length += added

    if window:
        chunks.append("\n\n".join(window))
    return chunks
