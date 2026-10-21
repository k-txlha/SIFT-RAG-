"""Unit tests for SQLite document metadata repository and session isolation."""

import tempfile
import unittest
from pathlib import Path

from document_store import DocumentRepository


class TestDocumentMetadata(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sessions.sqlite3"
        self.repo = DocumentRepository(self.db_path)
        with self.repo._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    last_seen REAL NOT NULL
                )
            """)
            conn.execute(
                "INSERT INTO sessions VALUES ('session_a', 1000.0, 1000.0), ('session_b', 1000.0, 1000.0)"
            )
            conn.commit()

        self.repo = DocumentRepository(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_get_document(self):
        doc = self.repo.create_document(
            session_id="session_a",
            filename="report.pdf",
            file_type="pdf",
            size_bytes=1024,
            content_hash="dummy_hash",
        )
        self.assertIsNotNone(doc)
        self.assertEqual(doc["session_id"], "session_a")
        self.assertEqual(doc["filename"], "report.pdf")
        self.assertEqual(doc["file_type"], "pdf")
        self.assertEqual(doc["status"], "processing")
        self.assertIsNotNone(doc["document_id"])

        fetched = self.repo.get_document("session_a", doc["document_id"])
        self.assertEqual(fetched["document_id"], doc["document_id"])

    def test_session_isolation_get_and_list(self):
        doc_a = self.repo.create_document(
            session_id="session_a",
            filename="secret.txt",
            file_type="txt",
            size_bytes=500,
        )

        # Session B attempts to read Session A's document
        fetched_by_b = self.repo.get_document("session_b", doc_a["document_id"])
        self.assertIsNone(fetched_by_b)

        # Session B lists its documents
        b_docs = self.repo.list_documents("session_b")
        self.assertEqual(len(b_docs), 0)

        # Session A lists its documents
        a_docs = self.repo.list_documents("session_a")
        self.assertEqual(len(a_docs), 1)
        self.assertEqual(a_docs[0]["document_id"], doc_a["document_id"])

    def test_duplicate_filenames_do_not_collide(self):
        doc1 = self.repo.create_document(
            session_id="session_a",
            filename="notes.txt",
            file_type="txt",
            size_bytes=100,
        )
        doc2 = self.repo.create_document(
            session_id="session_a",
            filename="notes.txt",
            file_type="txt",
            size_bytes=200,
        )

        self.assertNotEqual(doc1["document_id"], doc2["document_id"])

        docs = self.repo.list_documents("session_a")
        self.assertEqual(len(docs), 2)

        # Deleting one leaves the other intact
        deleted = self.repo.delete_document("session_a", doc1["document_id"])
        self.assertTrue(deleted)

        remaining = self.repo.list_documents("session_a")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["document_id"], doc2["document_id"])

    def test_update_status(self):
        doc = self.repo.create_document(
            session_id="session_a",
            filename="doc.txt",
            file_type="txt",
            size_bytes=50,
        )

        updated = self.repo.update_status(
            session_id="session_a",
            document_id=doc["document_id"],
            status="indexed",
            chunk_count=5,
        )
        self.assertEqual(updated["status"], "indexed")
        self.assertEqual(updated["chunk_count"], 5)


if __name__ == "__main__":
    unittest.main()
