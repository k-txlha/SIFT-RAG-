from pathlib import Path
import chromadb
import numpy as np

DB_PATH = str(Path(__file__).parent / "chroma_db")

class VectorDB:
    def __init__(
        self, collection: str = "documents", persistent_storage: str = DB_PATH, session_id: str | None = None
    ):
        self.client = chromadb.PersistentClient(path=persistent_storage)

        collection_name = (
            f"session_{session_id}"
            if session_id
            else collection
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            metadata={
                "hnsw:space": "cosine",
            },
        )

    @staticmethod
    def generate_id(records: list[dict], prefix: str) -> list[str]:
        ids = []
        for record in records:
            ids.append(f"{prefix}_{record['chunk_index']}")
        return ids

    def add_data(
        self,
        doc_records: list[dict],
        source: str,
        embeddings: np.ndarray,
        document_id: str | None = None,
    ):
        if len(doc_records) != len(embeddings):
            raise ValueError(
                "The number of documents must match the number of embeddings."
            )

        # Use document_id prefix if available, fallback to source for backward compatibility
        prefix = document_id if document_id else source
        ids = self.generate_id(doc_records, prefix)

        if ids:
            metadatas = []
            for doc in doc_records:
                meta = {
                    "source": source,
                    "chunk_index": int(doc["chunk_index"]),
                    "document_id": str(document_id if document_id else source),
                }
                if doc.get("page_number") is not None:
                    meta["page_number"] = int(doc["page_number"])
                metadatas.append(meta)

            self.collection.upsert(
                ids=ids,
                documents=[doc["text"] for doc in doc_records],
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
            )

        # Find existing chunks to clean up stale chunks from previous version
        filter_criteria = {"document_id": document_id} if document_id else {"source": source}
        existing = self.collection.get(
            where=filter_criteria,
            include=["metadatas"],
        )

        stale_ids = [stored_id for stored_id in existing["ids"] if stored_id not in ids]
        if stale_ids:
            self.collection.delete(ids=stale_ids)

    def delete_document(self, document_id: str) -> int:
        """Delete all chunks belonging to the given document_id."""
        existing = self.collection.get(
            where={"document_id": document_id},
            include=["metadatas"],
        )
        if existing and existing["ids"]:
            self.collection.delete(ids=existing["ids"])
            return len(existing["ids"])
        return 0

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 3,
        document_ids: list[str] | None = None,
    ):
        where_filter = None
        if document_ids:
            if len(document_ids) == 1:
                where_filter = {"document_id": document_ids[0]}
            else:
                where_filter = {"document_id": {"$in": document_ids}}

        return self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

    def count(self):
        return self.collection.count()
