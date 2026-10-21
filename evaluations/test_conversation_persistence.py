"""Conversation persistence and session-isolation API tests."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
from parsers import ParsedSection


class TestConversationPersistence(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def create_conversation(self, client=None, title="New conversation"):
        response = (client or self.client).post(
            "/conversations", json={"title": title}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_creating_two_conversations_preserves_both(self):
        first = self.create_conversation(title="First")
        second = self.create_conversation(title="Second")

        response = self.client.get("/conversations")
        self.assertEqual(response.status_code, 200)
        conversations = response.json()["conversations"]
        ids = {conversation["conversation_id"] for conversation in conversations}
        self.assertEqual(ids, {first["conversation_id"], second["conversation_id"]})

    def test_reload_restores_messages_and_source_citations(self):
        conversation = self.create_conversation()
        source = {
            "document_id": "doc-1",
            "filename": "security.pdf",
            "source": "security.pdf",
            "chunk_index": 3,
            "page_number": 7,
            "text": "The documented control requires access reviews.",
            "retrieval_score": 0.025,
        }
        result = {
            "question": "What does the access control require?",
            "answer": "It requires access reviews.",
            "sources": [source],
            "timings_ms": {"retrieval": 3, "generation": 8, "total": 11},
        }

        with (
            patch.object(api, "get_session_retriever", return_value=object()),
            patch.object(api, "answer_question", return_value=result),
        ):
            response = self.client.post(
                "/chat",
                json={
                    "question": result["question"],
                    "conversation_id": conversation["conversation_id"],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        reloaded_client = TestClient(api.app)
        reloaded_client.cookies.update(self.client.cookies)
        restored = reloaded_client.get(
            f"/conversations/{conversation['conversation_id']}"
        )
        self.assertEqual(restored.status_code, 200)
        messages = restored.json()["messages"]
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
        self.assertEqual(messages[1]["sources"], [source])
        self.assertEqual(messages[1]["timings_ms"], result["timings_ms"])

    def test_all_conversation_endpoints_enforce_session_ownership(self):
        conversation = self.create_conversation()
        other_client = TestClient(api.app)

        self.assertNotIn(
            conversation["conversation_id"],
            {
                item["conversation_id"]
                for item in other_client.get("/conversations").json()["conversations"]
            },
        )
        path = f"/conversations/{conversation['conversation_id']}"
        self.assertEqual(other_client.get(path).status_code, 404)
        self.assertEqual(
            other_client.patch(path, json={"title": "Stolen"}).status_code, 404
        )
        self.assertEqual(other_client.delete(path).status_code, 404)
        response = other_client.post(
            "/chat",
            json={
                "question": "Question",
                "conversation_id": conversation["conversation_id"],
            },
        )
        self.assertEqual(response.status_code, 404)

        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.patch(path, json={"title": "Renamed"}).status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 200)

    def test_failed_answer_does_not_append_partial_exchange(self):
        conversation = self.create_conversation()
        with (
            patch.object(api, "get_session_retriever", return_value=object()),
            patch.object(api, "answer_question", side_effect=RuntimeError("model unavailable")),
        ):
            response = self.client.post(
                "/chat",
                json={
                    "question": "Question",
                    "conversation_id": conversation["conversation_id"],
                },
            )
        self.assertEqual(response.status_code, 500)
        restored = self.client.get(
            f"/conversations/{conversation['conversation_id']}"
        ).json()
        self.assertEqual(restored["messages"], [])

    def test_summary_endpoint_saves_cited_result_in_conversation(self):
        self.client.get("/session")
        session_id = self.client.cookies.get("rag_session")
        doc = api.doc_repo.create_document(
            session_id=session_id,
            filename="controls.pdf",
            file_type="pdf",
            size_bytes=12,
            status="indexed",
        )
        conversation = self.create_conversation()
        source = {
            "source_id": "p4-c1",
            "filename": "controls.pdf",
            "source": "controls.pdf",
            "page_number": 4,
            "section_index": 1,
            "chunk_index": 1,
            "text": "Access to information shall be controlled.",
        }
        summary = {
            "overview": "The document defines access controls.",
            "overview_sources": ["p4-c1"],
            "key_points": [{"text": "Access is controlled.", "sources": ["p4-c1"]}],
            "important_controls": [],
            "risks": [],
        }

        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "controls.pdf"
            file_path.write_bytes(b"pdf")
            with (
                patch.object(api, "get_document_storage_path", return_value=file_path),
                patch.object(api, "parse_document", return_value=("pdf", [ParsedSection("text", 4)])),
                patch.object(
                    api,
                    "summarize_documents",
                    return_value=(summary, [source]),
                ),
            ):
                response = self.client.post(
                    f"/documents/{doc['document_id']}/summary",
                    json={"conversation_id": conversation["conversation_id"]},
                )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["sources"], [source])
        restored = self.client.get(
            f"/conversations/{conversation['conversation_id']}"
        ).json()
        self.assertEqual(restored["messages"][1]["sources"], [source])
        api.doc_repo.delete_document(session_id, doc["document_id"])

    def test_cross_document_summary_respects_selected_document_scope(self):
        self.client.get("/session")
        session_id = self.client.cookies.get("rag_session")
        selected = [
            api.doc_repo.create_document(
                session_id=session_id,
                filename=f"selected-{index}.txt",
                file_type="txt",
                size_bytes=10,
                status="indexed",
            )
            for index in range(2)
        ]
        excluded = api.doc_repo.create_document(
            session_id=session_id,
            filename="excluded.txt",
            file_type="txt",
            size_bytes=10,
            status="indexed",
        )
        conversation = self.create_conversation()
        result = {"answer": "Summary", "sources": [], "summary": {}}

        with patch.object(api, "_create_documents_summary", return_value=result) as summarize:
            response = self.client.post(
                "/chat",
                json={
                    "question": "Summarize the selected documents",
                    "document_ids": [doc["document_id"] for doc in selected],
                    "conversation_id": conversation["conversation_id"],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        called_docs = summarize.call_args.args[1]
        self.assertEqual(
            {doc["document_id"] for doc in called_docs},
            {doc["document_id"] for doc in selected},
        )
        self.assertNotIn(
            excluded["document_id"],
            {doc["document_id"] for doc in called_docs},
        )
        for doc in [*selected, excluded]:
            api.doc_repo.delete_document(session_id, doc["document_id"])


if __name__ == "__main__":
    unittest.main()
