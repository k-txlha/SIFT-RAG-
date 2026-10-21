
import numpy as np

from vector_store import VectorDB

db = VectorDB(
    collection="cleanup_test",
    persistent_storage="./chroma_cleanup_test_db",
)

source = "sample.txt"

# Simulate the original version: three chunks.
old_records = [
    {"chunk_index": 0, "text": "Chunk zero"},
    {"chunk_index": 1, "text": "Chunk one"},
    {"chunk_index": 2, "text": "Chunk two"},
]

old_embeddings = np.array([
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
])

db.add_data(old_records, source, old_embeddings)
print("After original version:", db.count())

# Simulate an updated version: only two chunks remain.
new_records = old_records[:2]
new_embeddings = old_embeddings[:2]

db.add_data(new_records, source, new_embeddings)
print("After updated version:", db.count())

# Simulate an empty version of the same document.
db.add_data([], source, np.empty((0, 3)))
print("After empty version:", db.count())
