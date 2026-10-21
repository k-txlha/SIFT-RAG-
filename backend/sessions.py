
"""Manage anonymous sessions for the RAG demo."""

import secrets
import sqlite3
import time
from pathlib import Path

from vector_store import VectorDB

SESSION_DB = Path(__file__).parent / "sessions.sqlite3"

INACTIVITY_TIMEOUT = 60 * 60       # 1 hour
MAX_SESSION_LIFETIME = 24 * 60 * 60  # 24 hours


CHROMA_DIR = str(Path(__file__).parent / "chroma_db")


class SessionManager:
    def __init__(self, persistent_storage: str = CHROMA_DIR):
        self.persistent_storage = persistent_storage
        self._initialize_db()

    def _connect(self):
        connection = sqlite3.connect(SESSION_DB, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    last_seen REAL NOT NULL
                )
            """)

    def create_session(self) -> str:
        now = time.time()
        session_id = secrets.token_hex(32)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, created_at, last_seen)
                VALUES (?, ?, ?)
                """,
                (session_id, now, now),
            )

        return session_id

    def get_active_session(self, session_id: str | None):
        """Validate a session, update activity, or return None."""
        if not session_id:
            return None

        now = time.time()

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

            if row is None:
                return None

            expired = (
                now - row["last_seen"] >= INACTIVITY_TIMEOUT
                or now - row["created_at"] >= MAX_SESSION_LIFETIME
            )

            if expired:
                conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,),
                )
                expired_id = session_id
            else:
                conn.execute(
                    "UPDATE sessions SET last_seen = ? WHERE session_id = ?",
                    (now, session_id),
                )
                return session_id

        # Remove the expired session's documents, vectors, and uploads.
        self._cleanup_session_data(expired_id)
        return None

    def _cleanup_session_data(self, session_id: str):
        import shutil
        # 1. Clean ChromaDB collection
        try:
            client = VectorDB(persistent_storage=self.persistent_storage).client
            client.delete_collection(name=f"session_{session_id}")
        except Exception:
            pass

        # 2. Clean SQLite document records
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM documents WHERE session_id = ?", (session_id,))
        except Exception:
            pass

        # 3. Clean uploaded source files
        try:
            uploads_dir = Path(__file__).parent / "uploads" / session_id
            if uploads_dir.exists():
                shutil.rmtree(uploads_dir, ignore_errors=True)
        except Exception:
            pass

    def delete_expired_sessions(self):
        """Remove expired sessions and their associated collections and files."""
        now = time.time()

        with self._connect() as conn:
            expired = conn.execute(
                """
                SELECT session_id FROM sessions
                WHERE last_seen <= ?
                   OR created_at <= ?
                """,
                (
                    now - INACTIVITY_TIMEOUT,
                    now - MAX_SESSION_LIFETIME,
                ),
            ).fetchall()

            conn.executemany(
                "DELETE FROM sessions WHERE session_id = ?",
                [(row["session_id"],) for row in expired],
            )

        for row in expired:
            self._cleanup_session_data(row["session_id"])

        return len(expired)
