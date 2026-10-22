"""Hybrid retrieval using persistent ChromaDB, BM25, and RRF."""

import re
from typing import Any, Optional

import numpy as np
from nltk.stem import PorterStemmer
from rank_bm25 import BM25Okapi
from jina_embedding import embed_query
from vector_store import VectorDB


class HybridRetriever:
    """Retrieve stored chunks using semantic search, BM25, and RRF."""

    def __init__(
        self,
        vector_db: VectorDB,
        *,
        rrf_k: int = 60,
    ) -> None:
        if vector_db.count() == 0:
            raise ValueError("The vector database is empty")
        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1")

        self.vector_db = vector_db
        self.rrf_k = rrf_k
        self.stemmer = PorterStemmer()

        self._load_records()

    def _load_records(self) -> None:
        """Load stored text and metadata to build the BM25 index."""
        stored = self.vector_db.collection.get(
            include=["documents", "metadatas"]
        )

        self.records: list[dict[str, Any]] = [
            {
                "id": stored["ids"][i],
                "text": stored["documents"][i],
                "source": stored["metadatas"][i].get("source", ""),
                "chunk_index": stored["metadatas"][i].get("chunk_index", 0),
                "document_id": stored["metadatas"][i].get(
                    "document_id", stored["metadatas"][i].get("source", "")
                ),
                "page_number": stored["metadatas"][i].get("page_number"),
            }
            for i in range(len(stored["ids"]))
        ]

        self.record_by_id = {
            record["id"]: record for record in self.records
        }

        if self.records:
            tokenized_chunks = [
                self.tokenize(record["text"]) for record in self.records
            ]
            self.bm25 = BM25Okapi(tokenized_chunks)
        else:
            self.bm25 = None

    def refresh(self) -> None:
        """Reload stored chunks and rebuild the BM25 index."""
        self._load_records()

    def tokenize(self, text: str) -> list[str]:
        """Lowercase, tokenize, and stem terms for BM25."""
        words = re.findall(r"\b[a-z0-9]+\b", text.lower())
        return [self.stemmer.stem(word) for word in words]

    def retrieve(
        self,
        question: str,
        *,
        top_k: int = 3,
        document_ids: Optional[list[str]] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return semantic, BM25, and hybrid rankings optionally filtered by document_ids."""
        if not question or not question.strip():
            raise ValueError("question must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        # Determine the eligible candidate pool
        if document_ids is not None:
            doc_id_set = set(document_ids)
            eligible_records = [
                rec for rec in self.records if rec["document_id"] in doc_id_set
            ]
        else:
            eligible_records = self.records

        if not eligible_records:
            return {"semantic": [], "bm25": [], "hybrid": []}

        # 1. Semantic search with ChromaDB
        query_embedding = embed_query(question) 
        semantic_results = self.vector_db.search(
            query_embedding,
            top_k=min(top_k, len(eligible_records)),
            document_ids=document_ids,
        )

        all_semantic = []
        if semantic_results and semantic_results["ids"] and len(semantic_results["ids"][0]) > 0:
            for record_id, document, metadata, distance in zip(
                semantic_results["ids"][0],
                semantic_results["documents"][0],
                semantic_results["metadatas"][0],
                semantic_results["distances"][0],
            ):
                if record_id in self.record_by_id:
                    all_semantic.append({
                        **self.record_by_id[record_id],
                        "score": float(1.0 - distance),
                    })

        semantic_scores_by_id = {
            record["id"]: record["score"]
            for record in all_semantic
        }
        semantic = all_semantic[:top_k]

        # 2. Keyword retrieval with BM25 constrained to the same eligible records
        if document_ids is not None:
            tokenized_eligible = [
                self.tokenize(record["text"]) for record in eligible_records
            ]
            scoped_bm25 = BM25Okapi(tokenized_eligible)
            bm25_scores = scoped_bm25.get_scores(self.tokenize(question))
            bm25_ranking = np.argsort(bm25_scores)[::-1][:top_k]
            bm25 = [
                {
                    **eligible_records[int(index)],
                    "score": float(bm25_scores[index]),
                }
                for index in bm25_ranking
            ]
        else:
            if self.bm25:
                bm25_scores = self.bm25.get_scores(self.tokenize(question))
                bm25_ranking = np.argsort(bm25_scores)[::-1][:top_k]
                bm25 = [
                    {
                        **self.records[int(index)],
                        "score": float(bm25_scores[index]),
                    }
                    for index in bm25_ranking
                ]
            else:
                bm25 = []

        bm25_scores_by_id = {
            record["id"]: record["score"]
            for record in bm25
        }

        # 3. Reciprocal Rank Fusion combines the two rankings
        rrf_scores: dict[str, float] = {}

        for ranking in (semantic, bm25):
            for rank, record in enumerate(ranking, start=1):
                record_id = record["id"]
                rrf_scores[record_id] = (
                    rrf_scores.get(record_id, 0.0)
                    + 1.0 / (self.rrf_k + rank)
                )

        hybrid_ids = sorted(
            rrf_scores,
            key=rrf_scores.__getitem__,
            reverse=True,
        )[:top_k]

        hybrid = [
            {
                **self.record_by_id[record_id],
                "score": rrf_scores[record_id],
                "semantic_score": semantic_scores_by_id.get(record_id),
                "bm25_score": bm25_scores_by_id.get(record_id),
            }
            for record_id in hybrid_ids
            if record_id in self.record_by_id
        ]

        # Public output structure
        def public_results(results):
            return [
                {
                    key: value
                    for key, value in record.items()
                    if key != "id"
                }
                for record in results
            ]

        return {
            "semantic": public_results(semantic),
            "bm25": public_results(bm25),
            "hybrid": public_results(hybrid),
        }
