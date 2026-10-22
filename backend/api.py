"""FastAPI endpoints for the session-isolated SIFT workspace."""

import os
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import (
    Body,
    Cookie,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Response,
    UploadFile,
    status as http_status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sys
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from document_store import DocumentRepository
from conversation_store import ConversationRepository
from hybrid_retriever import HybridRetriever
from ingestion import DocumentIngester
from parsers import EmptyDocumentError, ParsingError, UnsupportedFileError, parse_document
from rag_pipeline import answer_question, route_question
from sessions import SessionManager
from summarization import SummaryGenerationError, summarize_documents
from vector_store import VectorDB

app = FastAPI(
    title="SIFT API",
    description="Session-isolated document intelligence workspace using hybrid retrieval and an LLM.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://sift-rag.vercel.app/"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

SESSION_COOKIE = "rag_session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB limit
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

session_manager = SessionManager()
doc_repo = DocumentRepository()
conversation_repo = ConversationRepository()
retrievers: dict[str, HybridRetriever] = {}


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    document_ids: Optional[list[str]] = None
    conversation_id: Optional[str] = None


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=100)


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class SummaryRequest(BaseModel):
    conversation_id: Optional[str] = None


def get_session_id(
    response: Response,
    rag_session: Optional[str] = Cookie(default=None),
) -> str:
    """Validate the session cookie or create a new anonymous session."""
    session_manager.delete_expired_sessions()

    session_id = session_manager.get_active_session(rag_session)
    if session_id is None:
        session_id = session_manager.create_session()

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return session_id


def get_session_db(session_id: str) -> VectorDB:
    return VectorDB(session_id=session_id)


def get_session_retriever(session_id: str) -> Optional[HybridRetriever]:
    db = get_session_db(session_id)
    if db.count() == 0:
        retrievers.pop(session_id, None)
        return None

    if session_id not in retrievers:
        retrievers[session_id] = HybridRetriever(vector_db=db)

    return retrievers[session_id]


def get_document_storage_path(session_id: str, document_id: str, file_type: str) -> Path:
    session_folder = UPLOADS_DIR / session_id
    session_folder.mkdir(parents=True, exist_ok=True)
    clean_ext = file_type.lower().lstrip(".")
    return session_folder / f"{document_id}.{clean_ext}"


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "0.3.0",
        "dependencies": {
            "database": "ok",
            "vector_store": "ok",
        },
    }


@app.get("/session")
def get_session(session_id: str = Depends(get_session_id)):
    """Create or resume session and return summary."""
    db = get_session_db(session_id)
    docs = doc_repo.list_documents(session_id)
    indexed_docs = [d for d in docs if d["status"] == "indexed"]

    return {
        "status": "ok",
        "documents_count": len(indexed_docs),
        "total_files": len(docs),
        "chunks_count": db.count(),
        "session_expires_after_inactivity_seconds": 3600,
        "maximum_session_lifetime_seconds": 86400,
    }


@app.get("/conversations")
def list_conversations(session_id: str = Depends(get_session_id)):
    return {"conversations": conversation_repo.list_conversations(session_id)}


@app.post("/conversations", status_code=http_status.HTTP_201_CREATED)
def create_conversation(
    request: ConversationCreate,
    session_id: str = Depends(get_session_id),
):
    title = request.title.strip()
    if not title:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conversation title cannot be empty.",
        )
    return conversation_repo.create(session_id, title)


@app.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    session_id: str = Depends(get_session_id),
):
    conversation = conversation_repo.get(session_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation


@app.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    request: ConversationRename,
    session_id: str = Depends(get_session_id),
):
    title = request.title.strip()
    if not title:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conversation title cannot be empty.",
        )
    if not conversation_repo.rename(session_id, conversation_id, title):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation_repo.get(session_id, conversation_id)


@app.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    session_id: str = Depends(get_session_id),
):
    if not conversation_repo.delete(session_id, conversation_id):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return {"deleted": True, "conversation_id": conversation_id}


@app.get("/documents")
def list_documents(session_id: str = Depends(get_session_id)):
    """List all documents owned by the current session."""
    documents = doc_repo.list_documents(session_id)
    return {"documents": documents}


@app.get("/documents/{document_id}")
def get_document(document_id: str, session_id: str = Depends(get_session_id)):
    """Retrieve metadata for a specific document."""
    doc = doc_repo.get_document(session_id, document_id)
    if not doc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return doc


@app.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Depends(get_session_id),
):
    """Upload, validate, parse, chunk, embed and store a document."""
    if not file.filename or "." not in file.filename:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename. Supported formats are .txt, .pdf, and .docx.",
        )

    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    if file_ext not in {"txt", "pdf", "docx"}:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '.{file_ext}'. Please upload .txt, .pdf, or .docx.",
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=http_status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File size exceeds the 2 MB limit.",
        )

    if not content:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    # Validate parsing before creating persistent metadata
    try:
        _, sections = parse_document(file.filename, content)
    except EmptyDocumentError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except UnsupportedFileError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ParsingError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse file: {exc}",
        ) from exc

    content_hash = DocumentRepository.compute_hash(content)
    clean_filename = Path(file.filename).name

    # Create document record in SQLite
    doc_record = doc_repo.create_document(
        session_id=session_id,
        filename=clean_filename,
        file_type=file_ext,
        size_bytes=len(content),
        content_hash=content_hash,
        status="processing",
    )
    document_id = doc_record["document_id"]

    # Save original source file on server disk for safe re-indexing
    storage_path = get_document_storage_path(session_id, document_id, file_ext)
    try:
        storage_path.write_bytes(content)
    except Exception as exc:
        doc_repo.update_status(session_id, document_id, "failed", error_message="Disk write failed")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store uploaded file on server disk.",
        ) from exc

    # Ingest chunks into ChromaDB
    db = get_session_db(session_id)
    try:
        ingester = DocumentIngester(db)
        chunk_count = ingester.ingest_bytes(
            filename=clean_filename,
            content=content,
            document_id=document_id,
        )

        if chunk_count == 0:
            doc_repo.update_status(session_id, document_id, "failed", error_message="Zero chunks generated")
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="No usable chunks could be generated from document.",
            )

        updated_doc = doc_repo.update_status(
            session_id=session_id,
            document_id=document_id,
            status="indexed",
            chunk_count=chunk_count,
        )

        # Refresh or initialize hybrid retriever
        if session_id in retrievers:
            retrievers[session_id].refresh()
        else:
            retrievers[session_id] = HybridRetriever(vector_db=db)

        return {
            "document_id": document_id,
            "filename": clean_filename,
            "file_type": file_ext,
            "status": "indexed",
            "chunk_count": chunk_count,
            "size_bytes": len(content),
            "documents_count": db.count(),
        }

    except HTTPException:
        raise
    except Exception as exc:
        doc_repo.update_status(session_id, document_id, "failed", error_message=str(exc))
        db.delete_document(document_id)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ingestion failed while generating embeddings.",
        ) from exc


@app.delete("/documents/{document_id}")
def delete_document(document_id: str, session_id: str = Depends(get_session_id)):
    """Delete document metadata, stored file, and all associated chunks."""
    doc = doc_repo.get_document(session_id, document_id)
    if not doc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # 1. Delete matching chunks from ChromaDB
    db = get_session_db(session_id)
    db.delete_document(document_id)

    # 2. Delete source file from uploads
    storage_path = get_document_storage_path(session_id, document_id, doc["file_type"])
    if storage_path.exists():
        try:
            storage_path.unlink()
        except Exception:
            pass

    # 3. Delete from SQLite
    doc_repo.delete_document(session_id, document_id)

    # 4. Refresh retriever
    if session_id in retrievers:
        if db.count() > 0:
            retrievers[session_id].refresh()
        else:
            retrievers.pop(session_id, None)

    return {"deleted": True, "document_id": document_id}


@app.post("/documents/{document_id}/reindex")
def reindex_document(document_id: str, session_id: str = Depends(get_session_id)):
    """Re-parse, re-chunk, and re-embed an existing document from stored upload."""
    doc = doc_repo.get_document(session_id, document_id)
    if not doc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    storage_path = get_document_storage_path(session_id, document_id, doc["file_type"])
    if not storage_path.exists():
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Source file content not found on server disk.",
        )

    content = storage_path.read_bytes()
    db = get_session_db(session_id)

    try:
        ingester = DocumentIngester(db)
        chunk_count = ingester.ingest_bytes(
            filename=doc["filename"],
            content=content,
            document_id=document_id,
        )

        updated_doc = doc_repo.update_status(
            session_id=session_id,
            document_id=document_id,
            status="indexed",
            chunk_count=chunk_count,
        )

        if session_id in retrievers:
            retrievers[session_id].refresh()
        else:
            retrievers[session_id] = HybridRetriever(vector_db=db)

        return updated_doc

    except Exception as exc:
        doc_repo.update_status(
            session_id=session_id,
            document_id=document_id,
            status="failed",
            error_message=f"Re-indexing failed: {exc}",
        )
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to re-index document.",
        ) from exc


def _create_documents_summary(
    session_id: str, documents: list[dict[str, Any]]
) -> dict[str, Any]:
    if not documents:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Select at least one indexed document to summarize.",
        )

    parsed_documents = []
    for doc in documents:
        if doc["status"] != "indexed":
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Document '{doc['filename']}' is not indexed.",
            )

        storage_path = get_document_storage_path(
            session_id, doc["document_id"], doc["file_type"]
        )
        if not storage_path.is_file():
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Stored content for '{doc['filename']}' is unavailable.",
            )

        try:
            _, sections = parse_document(doc["filename"], storage_path.read_bytes())
        except EmptyDocumentError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{doc['filename']}: {exc}",
            ) from exc
        except ParsingError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not parse '{doc['filename']}': {exc}",
            ) from exc
        parsed_documents.append((doc["filename"], sections))

    try:
        summary, available_sources = summarize_documents(parsed_documents)
    except OverflowError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SummaryGenerationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=f"Document summarization failed: {exc}",
        ) from exc

    referenced_ids = set(summary["overview_sources"])
    for item in summary["key_points"]:
        referenced_ids.update(item["sources"])
    source_lookup = {
        source["source_id"]: source
        for source in available_sources
        if source["source_id"] in referenced_ids
    }

    def citation_label(source_id: str) -> str:
        source = source_lookup[source_id]
        if source["page_number"] is not None:
            return f'{source["filename"]}, page {source["page_number"]}'
        return f'{source["filename"]}, section {source["section_index"]}'

    answer_lines = [
        "## Overview",
        summary["overview"]
        + " "
        + " ".join(f"[{citation_label(source_id)}]" for source_id in summary["overview_sources"]),
    ]
    answer_lines.append("\n## Key points")
    if summary["key_points"]:
        answer_lines.extend(
            "- "
            + item["text"]
            + " "
            + " ".join(f"[{citation_label(source_id)}]" for source_id in item["sources"])
            for item in summary["key_points"]
        )
    else:
        answer_lines.append("- No supported key points were identified.")

    return {
        "summary": summary,
        "answer": "\n".join(answer_lines),
        "sources": list(source_lookup.values()),
    }


def _create_document_summary(session_id: str, doc: dict[str, Any]) -> dict[str, Any]:
    return _create_documents_summary(session_id, [doc])


@app.post("/documents/{document_id}/summary")
def summarize_document(
    document_id: str,
    request: SummaryRequest = Body(default=SummaryRequest()),
    session_id: str = Depends(get_session_id),
):
    doc = doc_repo.get_document(session_id, document_id)
    if doc is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    conversation_id = request.conversation_id
    if conversation_id is not None:
        if conversation_repo.get(session_id, conversation_id) is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
    else:
        conversation_id = conversation_repo.create(session_id)["conversation_id"]

    result = _create_document_summary(session_id, doc)
    question = f"Summarize {doc['filename']}"
    conversation_repo.save_exchange(
        session_id,
        conversation_id,
        question,
        result["answer"],
        result["sources"],
    )
    return {**result, "conversation_id": conversation_id}


@app.post("/chat")
def chat(
    request: ChatRequest,
    session_id: str = Depends(get_session_id),
):
    """Answer questions over all or selected session documents."""
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty.",
        )

    conversation_id = request.conversation_id
    if conversation_id is not None:
        if conversation_repo.get(session_id, conversation_id) is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
    else:
        conversation_id = conversation_repo.create(session_id)["conversation_id"]

    # Validate document_ids filter if provided
    filter_doc_ids = None
    if request.document_ids is not None:
        if len(request.document_ids) == 0:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Empty document list provided. Select at least one document or omit filter.",
            )
        # Ensure all document IDs belong to current session
        session_docs = {d["document_id"] for d in doc_repo.list_documents(session_id)}
        for target_id in request.document_ids:
            if target_id not in session_docs:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Document '{target_id}' not found in current session.",
                )
        filter_doc_ids = request.document_ids

    if filter_doc_ids is None:
        filter_doc_ids = [
            doc["document_id"]
            for doc in doc_repo.list_documents(session_id)
            if doc["status"] == "indexed"
        ]

    if route_question(question).kind == "summary":
        session_docs = {
            doc["document_id"]: doc
            for doc in doc_repo.list_documents(session_id)
            if doc["status"] == "indexed"
        }
        selected_ids = (
            filter_doc_ids
            if filter_doc_ids is not None
            else list(session_docs)
        )
        if not selected_ids or any(doc_id not in session_docs for doc_id in selected_ids):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="One or more selected documents are unavailable.",
            )
        summary_result = _create_documents_summary(
            session_id,
            [session_docs[document_id] for document_id in selected_ids],
        )
        conversation_repo.save_exchange(
            session_id,
            conversation_id,
            question,
            summary_result["answer"],
            summary_result["sources"],
        )
        return {**summary_result, "conversation_id": conversation_id}

    retriever = get_session_retriever(session_id)
    if retriever is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Upload and index at least one document before asking questions.",
        )

    try:
        result = answer_question(
            question=question,
            retriever=retriever,
            top_k=3,
            document_ids=filter_doc_ids,
        )
        conversation_repo.save_exchange(
            session_id,
            conversation_id,
            question,
            result["answer"],
            result["sources"],
            result["timings_ms"],
        )
        return {**result, "conversation_id": conversation_id}
    except LookupError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the answer.",
        ) from exc
