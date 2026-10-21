
import unittest

from hybrid_retriever import HybridRetriever
from rag_pipeline import answer_question
from vector_store import VectorDB


class TestRAGPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = VectorDB()
        cls.retriever = HybridRetriever(vector_db=cls.db)

    def test_relevant_question(self):
        question = "What is Apache Kafka used for?"

        result = answer_question(question, self.retriever)

        self.assertTrue(result["sources"])
        self.assertIn("Kafka", result["answer"])

    def test_irrelevant_question(self):
        question = "Who invented Python?"

        result = answer_question(question, self.retriever)

        self.assertEqual(result["sources"], [])
        self.assertEqual(
            result["answer"],
            "I couldn't find relevant information in the documents.",
        )
    
    def test_partially_supported_question(self):
        question = "What happens if a Kafka consumer goes offline?"

        result = answer_question(question, self.retriever)

        self.assertTrue(result["sources"])
        self.assertIn(
            "provided context",
            result["answer"].lower(),
        )


    def test_unsupported_kafka_question(self):
        question = (
            "How does Kafka guarantee exactly-once message processing?"
        )

        result = answer_question(question, self.retriever)

        answer = result["answer"].lower()

        self.assertTrue(
            "do not contain information" in answer
            or "don't know" in answer
            or "not possible to determine" in answer
        )

        self.assertTrue(result["sources"])


    def test_message_retention_question(self):
        question = (
            "For how long does Kafka retain messages?"
        )

        result = answer_question(question, self.retriever)

        self.assertTrue(result["sources"])
        self.assertIn("configured period", result["answer"].lower())

    def test_retrieval_finds_expected_chunk(self):
        question = "What is Apache Kafka used for?"

        results = self.retriever.retrieve(question, top_k=3)
        retrieved_texts = [
            chunk["text"].lower()
            for chunk in results["hybrid"]
        ]

        self.assertTrue(
            any("distributed event streaming platform" in text
                for text in retrieved_texts)
        )

    def test_unsupported_question_has_no_sources(self):
        question = "Who founded Apache Kafka?"

        result = answer_question(question, self.retriever)

        self.assertEqual(result["sources"], [])
        self.assertEqual(
            result["answer"],
            "I couldn't find relevant information in the documents.",
        )
 


if __name__ == "__main__":
    unittest.main()
