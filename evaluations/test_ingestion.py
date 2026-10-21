from ingestion import DocumentIngester
from vector_store import VectorDB

db = VectorDB()
ingester = DocumentIngester(db)

file_path = "kafka_intro.txt"

ingested = ingester.ingest_file(file_path)

print("Chunks ingested:", ingested)
print("Total chunks in database:", db.count())