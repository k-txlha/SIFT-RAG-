
import re


def chunk_text(
    text: str,
    chunk_size: int = 300,
    overlap: int = 50,
) -> list[str]:
    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if overlap and current:
            # Keep the overlap near the requested character count,
            # but start at a complete word.
            overlap_start = max(0, len(current) - overlap)

            if overlap_start > 0:
                word_boundary = current.find(" ", overlap_start)
                if word_boundary != -1:
                    overlap_start = word_boundary + 1

            overlap_text = current[overlap_start:].strip()
            current = f"{overlap_text} {sentence}".strip()
        else:
            current = sentence

    if current:
        chunks.append(current)

    return chunks
