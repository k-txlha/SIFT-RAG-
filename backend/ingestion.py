from pathlib import Path
from typing import Optional

from jina_embedding import embed_documents
from chunking import chunk_text
from parsers import parse_document
from vector_store import VectorDB


class DocumentIngester:
    def __init__(
        self,
        vector_db: VectorDB,
        chunk_size: int = 150,
        overlap: int = 30,
    ):
        self.vector_db = vector_db
        self.chunk_size = chunk_size
        self.overlap = overlap

    def ingest_bytes(
        self,
        filename: str,
        content: bytes,
        document_id: Optional[str] = None,
    ) -> int:
        _, sections = parse_document(filename, content)

        records = []
        for section in sections:
            chunks = chunk_text(
                section.text,
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            )
            for chunk in chunks:
                records.append({
                    "chunk_index": len(records),
                    "text": chunk,
                    "page_number": section.page_number,
                })

        if not records:
            return 0

        chunk_texts = [record["text"] for record in records]
        embeddings = embed_documents(chunk_texts)

        self.vector_db.add_data(
            doc_records=records,
            source=filename,
            embeddings=embeddings,
            document_id=document_id,
        )

        return len(records)

    def ingest_file(
        self,
        file_path: str,
        document_id: Optional[str] = None,
    ) -> int:
        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_bytes()
        return self.ingest_bytes(
            filename=path.name,
            content=content,
            document_id=document_id,
        )