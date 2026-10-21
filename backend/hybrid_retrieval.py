
from hybrid_retriever import HybridRetriever
from vector_store import VectorDB
from ingestion import DocumentIngester

QUESTION = "How can consumers handle events at their own speed?"

def print_ranking(title, results):
    print(f"\n{title}")

    for result in results:
        print(
            f"\nSource: {result['source']} | "
            f"Chunk: {result['chunk_index']} | "
            f"Score: {result['score']:.4f}"
        )
        print(result["text"])


def main():
    db = VectorDB()

    # Ingest the document into persistent storage.
    ingester = DocumentIngester(vector_db=db)
    ingester.ingest_file("kafka_intro.txt")

    # Build BM25 and use ChromaDB for semantic retrieval.
    retriever = HybridRetriever(vector_db=db)

    results = retriever.retrieve(QUESTION, top_k=3)

    print("Question:", QUESTION)
    print_ranking("SEMANTIC SEARCH", results["semantic"])
    print_ranking("BM25 KEYWORD SEARCH", results["bm25"])
    print_ranking("HYBRID SEARCH (RRF)", results["hybrid"])


if __name__ == "__main__":
    main()