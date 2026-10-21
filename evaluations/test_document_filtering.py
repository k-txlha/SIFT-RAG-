"""Unit test verifying document-aware retrieval filtering across semantic and BM25 branches."""

import unittest
from io import BytesIO
from fastapi.testclient import TestClient

from api import app


class TestDocumentFiltering(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.get("/session")

        # Ingest Document A (Kafka)
        kafka_content = b"Apache Kafka is a distributed event streaming platform used for building real-time data pipelines."
        res_a = self.client.post(
            "/documents",
            files={"file": ("kafka.txt", BytesIO(kafka_content), "text/plain")},
        )
        self.assertEqual(res_a.status_code, 200)
        self.doc_a_id = res_a.json()["document_id"]

        # Ingest Document B (Solar System)
        solar_content = b"Jupiter is the largest planet in our solar system. It is a gas giant with a Great Red Spot."
        res_b = self.client.post(
            "/documents",
            files={"file": ("solar.txt", BytesIO(solar_content), "text/plain")},
        )
        self.assertEqual(res_b.status_code, 200)
        self.doc_b_id = res_b.json()["document_id"]

    def tearDown(self):
        self.client.delete(f"/documents/{self.doc_a_id}")
        self.client.delete(f"/documents/{self.doc_b_id}")

    def test_filter_to_document_a(self):
        res = self.client.post(
            "/chat",
            json={
                "question": "What is Jupiter?",
                "document_ids": [self.doc_a_id],
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Even though query asked about Jupiter, because filter was Doc A (Kafka), Doc B cannot be cited!
        for source in data["sources"]:
            self.assertEqual(source["document_id"], self.doc_a_id)

    def test_filter_to_document_b(self):
        res = self.client.post(
            "/chat",
            json={
                "question": "What is the largest planet?",
                "document_ids": [self.doc_b_id],
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(len(data["sources"]) > 0)
        for source in data["sources"]:
            self.assertEqual(source["document_id"], self.doc_b_id)
            self.assertEqual(source["filename"], "solar.txt")

    def test_invalid_document_id_returns_404(self):
        res = self.client.post(
            "/chat",
            json={
                "question": "Test question?",
                "document_ids": ["non-existent-uuid-123"],
            },
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
