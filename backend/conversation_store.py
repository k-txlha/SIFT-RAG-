"""SQLite persistence for session-owned conversations and messages."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

DB_PATH = Path(__file__).parent / "sessions.sqlite3"


class ConversationRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._initialize_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_session_updated
                    ON conversations(session_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    text TEXT NOT NULL,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    timings_json TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
                    ON conversation_messages(conversation_id, created_at, message_id);
                """
            )

    @staticmethod
    def _format_conversation(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "conversation_id": row["conversation_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create(self, session_id: str, title: str = "New conversation") -> dict[str, Any]:
        conversation_id = str(uuid.uuid4())
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (conversation_id, session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, session_id, title, now, now),
            )
        return self.get(session_id, conversation_id)

    def list_conversations(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT conversation_id, title, created_at, updated_at
                FROM conversations
                WHERE session_id = ?
                ORDER BY updated_at DESC, created_at DESC
                """,
                (session_id,),
            ).fetchall()
        return [self._format_conversation(row) for row in rows]

    def get(self, session_id: str, conversation_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT conversation_id, title, created_at, updated_at
                FROM conversations
                WHERE conversation_id = ? AND session_id = ?
                """,
                (conversation_id, session_id),
            ).fetchone()
            if row is None:
                return None
            conversation = self._format_conversation(row)
            messages = conn.execute(
                """
                SELECT role, text, sources_json, timings_json, created_at
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY created_at, rowid
                """,
                (conversation_id,),
            ).fetchall()

        conversation["messages"] = [
            {
                "role": message["role"],
                "text": message["text"],
                "sources": json.loads(message["sources_json"]),
                "timings_ms": json.loads(message["timings_json"])
                if message["timings_json"]
                else None,
                "created_at": message["created_at"],
            }
            for message in messages
        ]
        return conversation

    def rename(self, session_id: str, conversation_id: str, title: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE conversations SET title = ?, updated_at = ?
                WHERE conversation_id = ? AND session_id = ?
                """,
                (title, time.time(), conversation_id, session_id),
            )
            return cursor.rowcount > 0

    def delete(self, session_id: str, conversation_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM conversations
                WHERE conversation_id = ? AND session_id = ?
                """,
                (conversation_id, session_id),
            )
            return cursor.rowcount > 0

    def save_exchange(
        self,
        session_id: str,
        conversation_id: str,
        question: str,
        answer: str,
        sources: list[dict[str, Any]],
        timings_ms: Optional[dict[str, int]] = None,
    ) -> None:
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT title FROM conversations
                WHERE conversation_id = ? AND session_id = ?
                """,
                (conversation_id, session_id),
            ).fetchone()
            if row is None:
                raise LookupError("Conversation not found in this session.")

            title = row["title"]
            if title == "New conversation":
                title = question.strip().replace("\n", " ")[:60] or title

            conn.execute(
                """
                UPDATE conversations SET title = ?, updated_at = ?
                WHERE conversation_id = ? AND session_id = ?
                """,
                (title, now, conversation_id, session_id),
            )
            conn.executemany(
                """
                INSERT INTO conversation_messages
                    (message_id, conversation_id, role, text, sources_json, timings_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (str(uuid.uuid4()), conversation_id, "user", question, "[]", None, now),
                    (
                        str(uuid.uuid4()),
                        conversation_id,
                        "assistant",
                        answer,
                        json.dumps(sources),
                        json.dumps(timings_ms) if timings_ms is not None else None,
                        now + 0.000001,
                    ),
                ],
            )
