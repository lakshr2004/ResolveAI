import re
from app.config import settings

def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None):
    size = chunk_size or settings.chunk_size
    overlap = settings.chunk_overlap if overlap is None else overlap
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require chunk_size > overlap >= 0")
    words = clean_text(text).split()
    chunks, start, index = [], 0, 1
    while start < len(words):
        end = min(start + size, len(words))
        content = " ".join(words[start:end])
        if content.strip():
            chunks.append({"chunk_id": f"chunk_{index:04d}", "text": content,
                           "metadata": {"start_word": start, "end_word": end}})
            index += 1
        if end == len(words):
            break
        start = end - overlap
    return chunks
