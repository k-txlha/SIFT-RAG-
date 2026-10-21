from vector_store import VectorDB

db = VectorDB()

results = db.collection.get(
    where={"source": "kafka_intro.txt"},
    include=["documents", "metadatas"],
)

for doc, metadata in zip(results["documents"], results["metadatas"]):
    print(f"\nChunk {metadata['chunk_index']}:")
    print(repr(doc))