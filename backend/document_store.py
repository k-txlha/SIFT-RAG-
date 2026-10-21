"""SQLite repository for document metadata and per-session ownership."""

import hashlib
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).parent / "sessions.sqlite3"


from contextlib import contextmanager

class DocumentRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._initialize_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    content_hash TEXT,
                    status TEXT NOT NULL,
                    chunk_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_session_id 
                ON documents (session_id)
            """)

    @staticmethod
    def compute_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def create_document(
        self,
        session_id: str,
        filename: str,
        file_type: str,
        size_bytes: int,
        content_hash: Optional[str] = None,
        status: str = "processing",
    ) -> dict[str, Any]:
        document_id = str(uuid.uuid4())
        now = time.time()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, session_id, filename, file_type,
                    size_bytes, content_hash, status, chunk_count,
                    error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
                """,
                (
                    document_id,
                    session_id,
                    filename,
                    file_type.lower().lstrip("."),
                    size_bytes,
                    content_hash,
                    status,
                    now,
                    now,
                ),
            )

        return self.get_document(session_id, document_id)

    @staticmethod
    def _format_doc(row: sqlite3.Row) -> dict[str, Any]:
        from datetime import datetime, timezone
        d = dict(row)
        if "created_at" in d and isinstance(d["created_at"], (int, float)):
            d["created_at"] = datetime.fromtimestamp(d["created_at"], tz=timezone.utc).isoformat()
        if "updated_at" in d and isinstance(d["updated_at"], (int, float)):
            d["updated_at"] = datetime.fromtimestamp(d["updated_at"], tz=timezone.utc).isoformat()
        return d

    def get_document(self, session_id: str, document_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM documents
                WHERE document_id = ? AND session_id = ?
                """,
                (document_id, session_id),
            ).fetchone()

            if row is None:
                return None
            return self._format_doc(row)

    def list_documents(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM documents
                WHERE session_id = ?
                ORDER BY created_at DESC
                """,
                (session_id,),
            ).fetchall()
            return [self._format_doc(row) for row in rows]

    def update_status(
        self,
        session_id: str,
        document_id: str,
        status: str,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        now = time.time()
        with self._connect() as conn:
            if chunk_count is not None:
                conn.execute(
                    """
                    UPDATE documents
                    SET status = ?, chunk_count = ?, error_message = ?, updated_at = ?
                    WHERE document_id = ? AND session_id = ?
                    """,
                    (status, chunk_count, error_message, now, document_id, session_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE documents
                    SET status = ?, error_message = ?, updated_at = ?
                    WHERE document_id = ? AND session_id = ?
                    """,
                    (status, error_message, now, document_id, session_id),
                )

        return self.get_document(session_id, document_id)

    def delete_document(self, session_id: str, document_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM documents
                WHERE document_id = ? AND session_id = ?
                """,
                (document_id, session_id),
            )
            return cursor.rowcount > 0

    def delete_session_documents(self, session_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM documents WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount
