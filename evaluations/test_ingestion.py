from backend.ingestion import DocumentIngester
from backend.vector_store import VectorDB

db = VectorDB()
ingester = DocumentIngester(db)

file_path = "./iso27001.pdf"

ingested = ingester.ingest_file(file_path)

print("Chunks ingested:", ingested)
print("Total chunks in database:", db.count())