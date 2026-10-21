"""Lifecycle and session isolation tests for SIFT FastAPI endpoints."""

from io import BytesIO
import unittest
from fastapi.testclient import TestClient

from api import app, doc_repo, session_manager


class TestDocumentLifecycle(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Session A client
        self.client_a = TestClient(app)
        # Session B client
        self.client_b = TestClient(app)

    def test_upload_list_reindex_delete_lifecycle(self):
        # 1. Initialize session A
        res_session = self.client_a.get("/session")
        self.assertEqual(res_session.status_code, 200)

        # 2. Upload document 1
        content1 = b"Apache Kafka is a distributed event streaming platform.\nIt handles high throughput."
        file_payload = {"file": ("kafka.txt", BytesIO(content1), "text/plain")}
        res_upload = self.client_a.post("/documents", files=file_payload)
        self.assertEqual(res_upload.status_code, 200, res_upload.text)
        data1 = res_upload.json()
        doc_id1 = data1["document_id"]
        self.assertEqual(data1["filename"], "kafka.txt")
        self.assertEqual(data1["status"], "indexed")
        self.assertTrue(data1["chunk_count"] > 0)

        # 3. Upload document 2 with the EXACT SAME filename (duplicate filename test)
        content2 = b"Apache Kafka topics are divided into partitions.\nConsumer groups read them."
        file_payload2 = {"file": ("kafka.txt", BytesIO(content2), "text/plain")}
        res_upload2 = self.client_a.post("/documents", files=file_payload2)
        self.assertEqual(res_upload2.status_code, 200)
        data2 = res_upload2.json()
        doc_id2 = data2["document_id"]
        self.assertNotEqual(doc_id1, doc_id2)

        # 4. List documents for Session A
        res_list = self.client_a.get("/documents")
        self.assertEqual(res_list.status_code, 200)
        docs = res_list.json()["documents"]
        self.assertEqual(len(docs), 2)
        doc_ids = [d["document_id"] for d in docs]
        self.assertIn(doc_id1, doc_ids)
        self.assertIn(doc_id2, doc_ids)

        # 5. Session isolation test: Session B attempts to read Session A's document
        res_b_get = self.client_b.get(f"/documents/{doc_id1}")
        self.assertEqual(res_b_get.status_code, 404)

        # Session B lists documents (should be 0)
        res_b_list = self.client_b.get("/documents")
        self.assertEqual(len(res_b_list.json()["documents"]), 0)

        # 6. Re-index document 1
        res_reindex = self.client_a.post(f"/documents/{doc_id1}/reindex")
        self.assertEqual(res_reindex.status_code, 200)
        self.assertEqual(res_reindex.json()["status"], "indexed")

        # 7. Delete document 1 (leaves document 2 with same filename intact)
        res_delete = self.client_a.delete(f"/documents/{doc_id1}")
        self.assertEqual(res_delete.status_code, 200)
        self.assertTrue(res_delete.json()["deleted"])

        # Check list again
        res_list_after = self.client_a.get("/documents")
        remaining_docs = res_list_after.json()["documents"]
        self.assertEqual(len(remaining_docs), 1)
        self.assertEqual(remaining_docs[0]["document_id"], doc_id2)

        # Clean up remaining document
        self.client_a.delete(f"/documents/{doc_id2}")

    def test_validation_errors(self):
        # Empty file
        empty_payload = {"file": ("empty.txt", BytesIO(b""), "text/plain")}
        res_empty = self.client_a.post("/documents", files=empty_payload)
        self.assertEqual(res_empty.status_code, 400)

        # Unsupported format (.exe)
        unsupported = {"file": ("script.exe", BytesIO(b"binary"), "application/octet-stream")}
        res_unsupported = self.client_a.post("/documents", files=unsupported)
        self.assertEqual(res_unsupported.status_code, 400)

        # Oversized file (> 2 MB)
        oversized_content = b"A" * (2 * 1024 * 1024 + 10)
        res_oversized = self.client_a.post(
            "/documents",
            files={"file": ("large.txt", BytesIO(oversized_content), "text/plain")},
        )
        self.assertEqual(res_oversized.status_code, 413)


if __name__ == "__main__":
    unittest.main()
