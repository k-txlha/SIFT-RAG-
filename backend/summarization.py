"""Page-aware, hierarchical summaries for complete uploaded documents."""

import json
import re
from typing import Any

from chunking import chunk_text
from llm import generate_response
from parsers import ParsedSection

MAX_SUMMARY_CHUNKS = 100
MAX_TOTAL_SUMMARY_CHUNKS = 200
MAX_SUMMARY_DOCUMENTS = 10
SUMMARY_CHUNK_SIZE = 3500
SUMMARY_BATCH_CHARS = 7000
SUMMARY_FIELDS = (
    "overview",
    "overview_sources",
    "key_points",
)


class SummaryGenerationError(RuntimeError):
    """Raised when the model cannot produce a grounded structured summary."""


def _bounded_text_chunks(text: str) -> list[str]:
    chunks = []
    for chunk in chunk_text(text, chunk_size=SUMMARY_CHUNK_SIZE, overlap=200):
        if len(chunk) <= SUMMARY_CHUNK_SIZE:
            chunks.append(chunk)
            continue

        offset = 0
        while offset < len(chunk):
            end = min(offset + SUMMARY_CHUNK_SIZE, len(chunk))
            if end < len(chunk):
                boundary = chunk.rfind(" ", offset + SUMMARY_CHUNK_SIZE // 2, end)
                if boundary > offset:
                    end = boundary
            piece = chunk[offset:end].strip()
            if piece:
                chunks.append(piece)
            if end == len(chunk):
                break
            offset = max(offset + 1, end - 200)
    return chunks


def _parse_summary_response(response: str, allowed_sources: set[str]) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise SummaryGenerationError("The model returned an invalid summary format.")

    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise SummaryGenerationError("The model returned invalid summary JSON.") from exc

    if not isinstance(parsed, dict) or any(field not in parsed for field in SUMMARY_FIELDS):
        raise SummaryGenerationError("The model summary is missing required fields.")
    if not isinstance(parsed["overview_sources"], list):
        raise SummaryGenerationError("The model returned invalid overview citations.")

    result: dict[str, Any] = {"overview": str(parsed["overview"]).strip()}
    result["overview_sources"] = [
        source
        for source in parsed["overview_sources"]
        if isinstance(source, str) and source in allowed_sources
    ]
    items = parsed["key_points"]
    if not isinstance(items, list):
        raise SummaryGenerationError("The model returned an invalid key_points list.")
    cleaned_items = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        references = [
            source
            for source in item.get("sources", [])
            if isinstance(source, str) and source in allowed_sources
        ]
        if item["text"].strip() and references:
            cleaned_items.append({"text": item["text"].strip(), "sources": references})
    result["key_points"] = cleaned_items

    if not result["overview"]:
        raise SummaryGenerationError("The model returned an empty document summary.")
    if not result["overview_sources"]:
        raise SummaryGenerationError("The model returned no citations for its overview.")
    return result


def _run_summary_prompt(instruction: str, content: str, source_ids: set[str]) -> dict[str, Any]:
    prompt = f"""You summarize supplied document evidence for a reader who needs a faithful, useful account of the source.

Return only valid JSON with exactly these fields:
{{
  "overview": "concise synthesis",
  "overview_sources": ["source-id"],
  "key_points": [{{"text": "grounded point", "sources": ["source-id"]}}]
}}

Rules:
- Use only facts present in the supplied evidence. Do not fill gaps with outside knowledge.
- Cite every point with one or more exact source IDs shown in the evidence.
- Never invent, alter, or guess a source ID. Omit unsupported points.
- Preserve meaningful section headings, labels, and identifiers when present.
- Do not force evidence into predefined subject categories.
- If the evidence provides no supported key points, return an empty list.
- {instruction}

Evidence:
{content}
"""
    return _parse_summary_response(generate_response(prompt), source_ids)


def summarize_sections(
    filename: str,
    sections: list[ParsedSection],
    *,
    source_prefix: str = "",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Summarize every parsed section in bounded, cited map/reduce batches."""
    if not sections or not any(section.text.strip() for section in sections):
        raise ValueError("The document contains no readable text to summarize.")

    chunks: list[dict[str, Any]] = []
    source_namespace = f"{source_prefix}-" if source_prefix else ""
    for section_index, section in enumerate(sections, start=1):
        for chunk_index, text in enumerate(_bounded_text_chunks(section.text), start=1):
            source_id = (
                f"{source_namespace}p{section.page_number}-c{chunk_index}"
                if section.page_number is not None
                else f"{source_namespace}s{section_index}-c{chunk_index}"
            )
            chunks.append(
                {
                    "source_id": source_id,
                    "text": text,
                    "page_number": section.page_number,
                    "section_index": section_index,
                    "chunk_index": chunk_index,
                }
            )

    if len(chunks) > MAX_SUMMARY_CHUNKS:
        raise OverflowError(
            f"The document is too large to summarize safely ({len(chunks)} sections; "
            f"limit is {MAX_SUMMARY_CHUNKS})."
        )

    sources = {
        chunk["source_id"]: {
            "source_id": chunk["source_id"],
            "source": filename,
            "filename": filename,
            "page_number": chunk["page_number"],
            "section_index": chunk["section_index"],
            "chunk_index": chunk["chunk_index"],
            "text": chunk["text"],
        }
        for chunk in chunks
    }

    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for chunk in chunks:
        size = len(chunk["text"])
        if current and current_chars + size > SUMMARY_BATCH_CHARS:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(chunk)
        current_chars += size
    if current:
        batches.append(current)

    summaries = []
    for batch in batches:
        evidence = "\n\n".join(
            f"[{chunk['source_id']}]"
            + (
                f" Section {chunk['section_index']}, page {chunk['page_number']}"
                if chunk["page_number"] is not None
                else f" Section {chunk['section_index']}"
            )
            + f"\n{chunk['text']}"
            for chunk in batch
        )
        allowed = {chunk["source_id"] for chunk in batch}
        summaries.append(
            _run_summary_prompt(
                "This is a map step: summarize this evidence batch without assuming it represents the entire document.",
                evidence,
                allowed,
            )
        )

    while len(summaries) > 1:
        reduced = []
        for offset in range(0, len(summaries), 4):
            group = summaries[offset : offset + 4]
            available_sources = {
                source
                for summary in group
                for source in summary["overview_sources"]
            }
            for summary in group:
                for item in summary["key_points"]:
                    available_sources.update(item["sources"])
            if not available_sources:
                raise SummaryGenerationError(
                    "The model did not preserve citations while reducing the summary."
                )

            reduced.append(
                _run_summary_prompt(
                    "Synthesize these partial summaries into a document-level summary, "
                    "preserving their source IDs exactly.",
                    json.dumps(group, ensure_ascii=True),
                    available_sources,
                )
            )
        summaries = reduced

    summary = summaries[0]
    return summary, [sources[source_id] for source_id in sorted(sources)]


def summarize_documents(
    documents: list[tuple[str, list[ParsedSection]]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Summarize complete selected documents and synthesize their cited summaries."""
    if not documents:
        raise ValueError("Select at least one document to summarize.")
    if len(documents) > MAX_SUMMARY_DOCUMENTS:
        raise OverflowError(
            f"A maximum of {MAX_SUMMARY_DOCUMENTS} documents can be summarized at once."
        )

    chunk_count = 0
    for _, sections in documents:
        if not sections or not any(section.text.strip() for section in sections):
            raise ValueError("A selected document contains no readable text to summarize.")
        chunk_count += sum(
            len(_bounded_text_chunks(section.text))
            for section in sections
            if section.text.strip()
        )
    if chunk_count > MAX_TOTAL_SUMMARY_CHUNKS:
        raise OverflowError(
            f"The selected documents are too large to summarize safely "
            f"({chunk_count} sections; limit is {MAX_TOTAL_SUMMARY_CHUNKS})."
        )

    partial_summaries = []
    all_sources = []
    for index, (filename, sections) in enumerate(documents, start=1):
        summary, sources = summarize_sections(
            filename,
            sections,
            source_prefix=f"d{index}",
        )
        partial_summaries.append(summary)
        all_sources.extend(sources)

    if len(partial_summaries) == 1:
        return partial_summaries[0], all_sources

    allowed_sources = {
        source_id
        for summary in partial_summaries
        for source_id in summary["overview_sources"]
    }
    for summary in partial_summaries:
        for item in summary["key_points"]:
            allowed_sources.update(item["sources"])
    combined = _run_summary_prompt(
        "Synthesize the complete selected documents. Identify shared and differing "
        "ideas only when supported, and cite each point with its exact source IDs.",
        json.dumps(partial_summaries, ensure_ascii=True),
        allowed_sources,
    )
    return combined, all_sources
