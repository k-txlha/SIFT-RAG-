from pathlib import Path
from chunking import chunk_text

text = Path("kafka_intro.txt").read_text(encoding="utf-8")
chunks = chunk_text(text, chunk_size=150, overlap=30)

for index, chunk in enumerate(chunks):
    print(f"\nChunk {index} ({len(chunk)} chars):")
    print(repr(chunk))