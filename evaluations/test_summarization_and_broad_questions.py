"""Tests for full-document summaries and broad evidence retrieval."""

import json
import re
import unittest
from unittest.mock import patch

from parsers import ParsedSection
from rag_pipeline import answer_question, route_question
from summarization import summarize_documents, summarize_sections


def fake_summary_response(prompt):
    source_ids = sorted(
        set(re.findall(r"\b(?:d\d+-)?(?:p\d+|s\d+)-c\d+\b", prompt))
    )
    if not source_ids:
        raise AssertionError("Summary prompt did not contain source references.")
    citations = [source_ids[0]]
    return json.dumps(
        {
            "overview": "The source describes its subject and supporting evidence.",
            "overview_sources": citations,
            "key_points": [{"text": "A supported point from the source.", "sources": citations}],
        }
    )


class TestDocumentSummarization(unittest.TestCase):
    def test_short_document_summary_is_structured_and_page_cited(self):
        sections = [
            ParsedSection(
                text="5.1 Field observations. The study records seasonal changes.",
                page_number=4,
            )
        ]
        with patch("summarization.generate_response", side_effect=fake_summary_response):
            summary, sources = summarize_sections("field-study.pdf", sections)

        self.assertTrue(summary["overview"])
        self.assertTrue(summary["key_points"])
        self.assertEqual(summary["overview_sources"], ["p4-c1"])
        self.assertEqual(sources[0]["page_number"], 4)

    def test_long_document_uses_multiple_map_reduce_calls_and_preserves_pages(self):
        long_text = "The technical process includes validation and regular review. " * 140
        sections = [
            ParsedSection(text=long_text, page_number=7),
            ParsedSection(text=long_text, page_number=8),
            ParsedSection(text=long_text, page_number=9),
        ]
        with patch(
            "summarization.generate_response", side_effect=fake_summary_response
        ) as generate:
            summary, sources = summarize_sections("technical-guide.pdf", sections)

        self.assertGreater(generate.call_count, 1)
        self.assertEqual({source["page_number"] for source in sources}, {7, 8, 9})
        valid_ids = {source["source_id"] for source in sources}
        self.assertTrue(set(summary["overview_sources"]).issubset(valid_ids))

    def test_excessively_large_summary_is_rejected_before_model_calls(self):
        sections = [
            ParsedSection(
                text="x" * 400000,
                page_number=1,
            )
        ]
        with patch("summarization.generate_response") as generate:
            with self.assertRaises(OverflowError):
                summarize_sections("large.txt", sections)
        generate.assert_not_called()


class StubRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.requested_top_k = None

    def retrieve(self, question, *, top_k, document_ids=None):
        self.requested_top_k = top_k
        return {"hybrid": self.chunks}


class TestBroadQuestionRetrieval(unittest.TestCase):
    def test_broad_question_uses_multiple_relevant_sections(self):
        chunks = [
            {
                "document_id": "doc",
                "source": "climate.pdf",
                "chunk_index": 1,
                "page_number": 8,
                "text": "The river flow was measured at the upstream station.",
                "semantic_score": 0.52,
                "score": 0.03,
            },
            {
                "document_id": "doc",
                "source": "climate.pdf",
                "chunk_index": 2,
                "page_number": 17,
                "text": "The downstream station recorded a lower average flow.",
                "semantic_score": 0.48,
                "score": 0.02,
            },
        ]
        retriever = StubRetriever(chunks)
        prompts = []

        def capture_prompt(prompt):
            prompts.append(prompt)
            return             "The sources describe related observations across sections."

        with patch("rag_pipeline.generate_response", side_effect=capture_prompt):
            result = answer_question(
                "What patterns can explain these observations?", retriever
            )

        self.assertEqual(retriever.requested_top_k, 12)
        self.assertEqual(len(result["sources"]), 2)
        self.assertIn("page: 8", prompts[0].lower())
        self.assertIn("page: 17", prompts[0].lower())

    def test_unsupported_normal_question_is_not_given_low_similarity_evidence(self):
        retriever = StubRetriever(
            [
                {
                    "document_id": "doc",
                    "source": "climate.pdf",
                    "chunk_index": 1,
                    "page_number": 3,
                    "text": "The document describes a regional climate study.",
                    "semantic_score": 0.32,
                    "score": 0.01,
                }
            ]
        )
        with patch("rag_pipeline.generate_response") as generate:
            result = answer_question("Who wrote the novel mentioned here?", retriever)

        self.assertEqual(result["sources"], [])
        generate.assert_not_called()
        self.assertIn("couldn't find", result["answer"].lower())

    def test_general_query_router_handles_query_forms_not_subject_terms(self):
        self.assertEqual(route_question("What is the reported sample size?").kind, "specific")
        self.assertEqual(route_question("Summarize this research paper").kind, "summary")
        self.assertEqual(route_question("Compare the two quarterly reports").kind, "comparison")
        self.assertEqual(route_question("Extract every date and amount as a table").kind, "extraction")
        self.assertEqual(route_question("What are the main causes discussed across sections?").kind, "broad")

    def test_comparison_retrieves_from_each_selected_document(self):
        per_doc_results = {
            "guide": [{
                "document_id": "guide",
                "source": "guide.txt",
                "chunk_index": 1,
                "page_number": 2,
                "text": "The device uses a direct-current power supply.",
                "semantic_score": 0.65,
                "score": 0.03,
            }],
            "report": [{
                "document_id": "report",
                "source": "report.txt",
                "chunk_index": 4,
                "page_number": 9,
                "text": "Operating expenses rose after the system upgrade.",
                "semantic_score": 0.61,
                "score": 0.02,
            }],
        }

        class MultiDocumentRetriever:
            def retrieve(self, question, *, top_k, document_ids=None):
                return {"hybrid": per_doc_results[document_ids[0]]}

        prompt = []
        with patch(
            "rag_pipeline.generate_response",
            side_effect=lambda value: (prompt.append(value) or "The sources describe different subjects."),
        ):
            result = answer_question(
                "Compare the selected documents",
                MultiDocumentRetriever(),
                document_ids=["guide", "report"],
            )

        self.assertEqual(
            {source["document_id"] for source in result["sources"]},
            {"guide", "report"},
        )
        self.assertIn("guide.txt", prompt[0])
        self.assertIn("report.txt", prompt[0])

    def test_multi_document_summary_keeps_each_document_reference(self):
        documents = [
            ("manual.txt", [ParsedSection("Connect the sensor to the gateway.", 2)]),
            ("report.txt", [ParsedSection("Revenue increased during the quarter.", 8)]),
            ("textbook.txt", [ParsedSection("Water changes state when heated.", 14)]),
            ("paper.txt", [ParsedSection("The trial enrolled 120 participants.", 3)]),
        ]
        with patch("summarization.generate_response", side_effect=fake_summary_response):
            summary, sources = summarize_documents(documents)

        self.assertEqual(len(sources), 4)
        self.assertEqual({source["filename"] for source in sources}, {
            "manual.txt", "report.txt", "textbook.txt", "paper.txt"
        })
        self.assertEqual(summary["overview_sources"], ["d1-p2-c1"])


if __name__ == "__main__":
    unittest.main()
