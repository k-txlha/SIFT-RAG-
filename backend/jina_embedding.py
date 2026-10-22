
"""Jina AI embedding client for SIFT-RAG."""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("JINA_EMBEDDING_API_URL", "https://api.jina.ai/v1/embeddings")

MODEL_NAME = os.getenv(
    "JINA_EMBEDDING_MODEL",
    "jina-embeddings-v5-text-small",
)

EMBEDDING_DIMENSIONS = int(
    os.getenv("JINA_EMBEDDING_DIMENSIONS", "768")
)

BATCH_SIZE = 32
MAX_RETRIES = 5


def _embed_batch(
    texts: list[str],
    task: str,
) -> list[list[float]]:
    """Embed a batch of texts using Jina's hosted API."""
    api_key = os.getenv("JINA_API_KEY")

    if not api_key:
        raise RuntimeError(
            "JINA_API_KEY environment variable is not configured."
        )

    if not texts or any(not text or not text.strip() for text in texts):
        raise ValueError("Embedding inputs cannot be empty.")

    payload = {
        "model": MODEL_NAME,
        "input": texts,
        "task": task,
        "dimensions": EMBEDDING_DIMENSIONS,
        "embedding_type": "float",
        "normalized": True,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=90,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else min(2 ** attempt * 2, 60)
                )

                if attempt == MAX_RETRIES - 1:
                    response.raise_for_status()

                print(f"Jina rate limit reached; waiting {wait}s.")
                time.sleep(wait)
                continue

            response.raise_for_status()
            result = response.json()

            # Restore input order using each result's index.
            items = sorted(result["data"], key=lambda item: item["index"])
            embeddings = [item["embedding"] for item in items]

            if len(embeddings) != len(texts):
                raise RuntimeError(
                    "Jina returned an unexpected number of embeddings."
                )

            if any(
                len(vector) != EMBEDDING_DIMENSIONS
                for vector in embeddings
            ):
                raise RuntimeError(
                    "Jina returned embeddings with unexpected dimensions."
                )

            return embeddings

        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise

            wait = min(2 ** attempt * 2, 60)
            print(f"Jina request failed; retrying in {wait}s.")
            time.sleep(wait)

    raise RuntimeError("Jina embedding request failed after retries.")


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for semantic retrieval."""
    embeddings = []

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]

        print(
            f"Embedding batch: {start + 1}-"
            f"{start + len(batch)} of {len(texts)} chunks"
        )

        embeddings.extend(
            _embed_batch(batch, task="retrieval.passage")
        )

    return embeddings


def embed_query(text: str) -> list[float]:
    """Embed a search query for semantic retrieval."""
    if not text or not text.strip():
        raise ValueError("Query cannot be empty.")

    return _embed_batch(
        [text],
        task="retrieval.query",
    )[0]
