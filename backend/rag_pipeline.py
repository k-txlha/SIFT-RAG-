import time
import re
from dataclasses import dataclass
from typing import Optional

from hybrid_retriever import HybridRetriever
from llm import generate_response
from vector_store import VectorDB

SIMILARITY_THRESHOLD = 0.60
BROAD_SIMILARITY_THRESHOLD = 0.40
BROAD_RETRIEVAL_LIMIT = 12


@dataclass(frozen=True)
class QueryIntent:
    kind: str
    retrieval_limit: int
    similarity_threshold: float


def route_question(question: str, top_k: int = 3) -> QueryIntent:
    """Route by query form rather than document subject or domain vocabulary."""
    normalized = re.sub(r"\s+", " ", question.lower()).strip()
    if re.search(r"\b(summar(?:y|ize|ise|izing|ising)|overview)\b", normalized):
        return QueryIntent("summary", BROAD_RETRIEVAL_LIMIT, BROAD_SIMILARITY_THRESHOLD)
    if re.search(r"\b(compare|contrast|differences?|similarities)\b", normalized):
        return QueryIntent("comparison", BROAD_RETRIEVAL_LIMIT, BROAD_SIMILARITY_THRESHOLD)
    if re.search(r"\b(extract|list all|identify all|table of|as json|in a table)\b", normalized):
        return QueryIntent("extraction", BROAD_RETRIEVAL_LIMIT, BROAD_SIMILARITY_THRESHOLD)
    if re.search(
        r"\b(across|throughout|overall|main|major|key|all|various|multiple|"
        r"themes?|topics?|aspects?|factors?|ways?|approaches?|sections?|"
        r"discussed|described|covered|mentioned|presented)\b|"
        r"\bwhat\s+\w+\s+(?:can|could|should|would|do|does)\b|"
        r"\bwhat\s+are\s+the\b",
        normalized,
    ):
        return QueryIntent("broad", BROAD_RETRIEVAL_LIMIT, BROAD_SIMILARITY_THRESHOLD)
    return QueryIntent("specific", top_k, SIMILARITY_THRESHOLD)


def classify_question_intent(question: str) -> str:
    """Backward-compatible name for the general-purpose query router."""
    return route_question(question).kind

def answer_question(
    question: str,
    retriever: HybridRetriever,
    top_k: int = 3,
    document_ids: Optional[list[str]] = None,
) -> dict:
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    t_start = time.perf_counter()

    # Broad questions need evidence from more than the single best-matching passage.
    intent = route_question(question, top_k=top_k)
    if document_ids and len(document_ids) > 1 and intent.kind in {
        "broad",
        "comparison",
        "extraction",
    }:
        per_document = [
            retriever.retrieve(
                question,
                top_k=min(3, intent.retrieval_limit),
                document_ids=[document_id],
            )["hybrid"]
            for document_id in document_ids
        ]
        results_hybrid = []
        for rank in range(3):
            for document_results in per_document:
                if rank < len(document_results):
                    results_hybrid.append(document_results[rank])
                if len(results_hybrid) >= intent.retrieval_limit:
                    break
            if len(results_hybrid) >= intent.retrieval_limit:
                break
        results = {"hybrid": results_hybrid}
    else:
        results = retriever.retrieve(
            question,
            top_k=intent.retrieval_limit,
            document_ids=document_ids,
        )
    chunks = [
        chunk
        for chunk in results["hybrid"]
        if (
            chunk.get("semantic_score") is not None
            and chunk["semantic_score"] >= intent.similarity_threshold
        )
    ]
    t_retrieval = time.perf_counter()

    if not chunks:
        t_end = time.perf_counter()
        return {
            "question": question,
            "answer": "I couldn't find relevant information in the documents.",
            "sources": [],
            "timings_ms": {
                "retrieval": round((t_retrieval - t_start) * 1000),
                "generation": 0,
                "total": round((t_end - t_start) * 1000),
            },
        }

    # 2. Build context from the retrieved chunks.
    context_parts = []
    for chunk in chunks:
        location = f"Source: {chunk['source']}, Chunk: {chunk['chunk_index']}"
        if chunk.get("page_number"):
            location += f", Page: {chunk['page_number']}"
        context_parts.append(f"{location}\n{chunk['text']}")

    context = "\n\n".join(context_parts)

    # 3. Grounding prompt
    prompt = f"""You are a helpful assistant that answers questions using supplied documents.

Rules:
- Answer using only facts supported by the context.
- You may paraphrase or combine facts from the context, but do not introduce unsupported claims.
- If the context partially answers the question, explain what it supports and clearly state what remains unknown.
- If the context provides no useful information, say you don't know based on the provided documents.
- Cite claims using the provided source and page/chunk metadata. Do not invent citations.
- For comparisons or broad questions, synthesize evidence across the supplied sources.
- For extraction requests, return only fields and values supported by the context.
- Keep the answer clear and concise.

Context:
{context}

Question:
{question}

Answer:
"""

    # 4. Generate answer with local LLM
    answer = generate_response(prompt)
    t_end = time.perf_counter()

    # 5. Build enriched source citations
    sources = [
        {
            "document_id": chunk.get("document_id"),
            "source": chunk["source"],
            "filename": chunk["source"],
            "chunk_index": chunk["chunk_index"],
            "page_number": chunk.get("page_number"),
            "text": chunk.get("text"),
            "retrieval_score": round(chunk.get("score", 0.0), 4),
        }
        for chunk in chunks
    ]

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "timings_ms": {
            "retrieval": round((t_retrieval - t_start) * 1000),
            "generation": round((t_end - t_retrieval) * 1000),
            "total": round((t_end - t_start) * 1000),
        },
    }


if __name__ == "__main__":
    db = VectorDB()
    retriever = HybridRetriever(vector_db=db)
    question_test = "What is Apache Kafka used for?"
    result = answer_question(question_test, retriever)

    print("\nQuestion:", result["question"])
    print("\nAnswer:", result["answer"])
    print("\nSources:")
    for src in result["sources"]:
        print(f"- {src['filename']} (chunk {src['chunk_index']})")
    print("\nTimings:", result["timings_ms"])
