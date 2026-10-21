from sentence_transformers import SentenceTransformer

from vector_store import VectorDB

db = VectorDB()
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

question = "How can consumers process messages at their own pace?"
query_embedding = model.encode(question)

results = db.search(query_embedding, top_k=3)

for document, metadata, distance in zip(
    results["documents"][0],
    results["metadatas"][0],
    results["distances"][0],
):
    print(f"\nSource: {metadata['source']}")
    print(f"Chunk index: {metadata['chunk_index']}")
    print(f"Distance: {distance:.4f}")
    print(f"Text: {document}")