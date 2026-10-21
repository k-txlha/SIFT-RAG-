# import sys
# from pathlib import Path

# # Ensure project root is in sys.path when running script directly
# sys.path.append(str(Path(__file__).resolve().parent.parent))

from sentence_transformers import SentenceTransformer
from vector_store import VectorDB

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
db = VectorDB()

records = [
    {"chunk_index": 0, "text": "Kafka is a distributed event streaming platform."},
    {"chunk_index": 1, "text": "Kafka producers publish messages to topics."},
    {"chunk_index": 2, "text": "Kafka consumers read messages from topics."},
]

embeddings = model.encode([record["text"] for record in records])

db.add_data(records, "kafka_test.txt", embeddings)

query_embedding = model.encode("How do producers publish messages?")
results = db.search(query_embedding, top_k=2)

print("Stored chunks:", db.count())
print(results["documents"])
print(results["metadatas"])
print(results["distances"])