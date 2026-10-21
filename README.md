# SIFT 🌿

> A clean, minimal document-intelligence workspace with session-isolated document management, hybrid retrieval (Dense + BM25 + Reciprocal Rank Fusion), and local LLM answer grounding.

---

## Features

- **Multi-Format Ingestion**: Upload and index `.txt`, `.pdf` (via `pypdf`), and `.docx` (via `python-docx`) files up to 2 MB.
- **Session-Isolated Workspace**: Anonymous sessions driven by `HttpOnly` cookies and SQLite session registries. Users cannot read, chat over, re-index, or delete another session's documents.
- **Stable Document Identity**: Server-generated UUIDs ensure that duplicate filenames do not collide or overwrite each other.
- **Document Library Management**: View indexed chunks, file sizes, format badges, and processing statuses; re-index or delete documents on demand with cascade cleanup.
- **Document-Scoped Querying**: Ask questions across all documents or toggle checkboxes to focus retrieval on an explicit subset of files.
- **Hybrid Retrieval (Dense + BM25 + RRF)**: Combines semantic cosine similarity from ChromaDB (`sentence-transformers/all-MiniLM-L6-v2`) with sparse keyword search (`rank_bm25.BM25Okapi`) fused with Reciprocal Rank Fusion ($k=60$).
- **Grounded Citations & Timings**: Expandable source citations citing filenames, chunk indices, page numbers (for PDFs), passages, relevance scores, and latency metrics (`retrieval`, `generation`, `total`).
- **Clean & Minimal UI**: Built with React 19 + Vite using warm off-white (`#F7F7F1`), surface white (`#FFFFFF`), and muted sage accents (`#647653`), featuring custom sleek scrollbars and keyboard navigation.

---

## Architecture & Request Flow

```
+-------------------------------------------------------------------------+
|                               Browser / React UI                         |
|  - Document Library (List / Re-index / Delete)                          |
|  - Drag & Drop Upload Zone (.txt, .pdf, .docx)                          |
|  - Chat Composer with Document Scope Filters                            |
+------------------------------------+------------------------------------+
                                     |  HTTP (Credentials: include)
                                     v
+------------------------------------+------------------------------------+
|                             FastAPI Backend                              |
|  - Session Validation (HttpOnly cookie -> session_id)                   |
|  - Document CRUD & Ownership Gate (404 for unowned / missing docs)      |
+------------------+-----------------+-------------------+----------------+
                   |                 |                   |
                   v                 v                   v
          +--------+--------+  +-----+------+      +-----+------+
          | SQLite Metadata |  | Disk Store |      | ChromaDB   |
          |  - sessions     |  | uploads/   |      | session_{id|
          |  - documents    |  |  session_id|      | collections|
          +-----------------+  +------------+      +-----+------+
                                                         |
                                 +-----------------------+-----------------------+
                                 |                                               |
                                 v                                               v
                     +-----------+-----------+                       +-----------+-----------+
                     | Dense Semantic Search |                       | Sparse BM25 Keyword   |
                     | sentence-transformers |                       | rank_bm25 Tokenizer   |
                     +-----------+-----------+                       +-----------+-----------+
                                 \                                   /
                                  \         Reciprocal Rank         /
                                   +--------+    Fusion     +------+
                                            |   (k = 60)    |
                                            +-------+-------+
                                                    | Top-K Chunks
                                                    v
                                            +-------+-------+
                                            | Grounded LLM  |
                                            | (Local Ollama)|
                                            | qwen3:4b-inst |
                                            +-------+-------+
                                                    |
                                                    v
                                      Answer + Sources + Timings
```

---

## Local Setup

### Prerequisites

1. **Python 3.11+**
2. **Node.js 18+** & npm
3. **Ollama** installed with the target model:
   ```bash
   ollama pull qwen3:4b-instruct
   ```

### 1. Backend Setup

```bash
# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pypdf python-docx
```

### 2. Run the Backend API

```bash
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

> **Note on Origin Consistency**: The frontend connects to `http://localhost:8000` or `http://127.0.0.1:8000`. Ensure that you do not mix `127.0.0.1` and `localhost` in the browser URL to allow `HttpOnly` session cookies to pass properly.

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## API Reference

| Method   | Path                      | Description                                                               | Key Status Codes                         |
| :------- | :------------------------ | :------------------------------------------------------------------------ | :--------------------------------------- |
| `GET`    | `/health`                 | Liveness check and dependencies summary                                   | `200`                                    |
| `GET`    | `/session`                | Validates/creates anonymous session & summary                             | `200`                                    |
| `GET`    | `/documents`              | Lists all documents owned by current session                              | `200`                                    |
| `GET`    | `/documents/{id}`         | Inspect metadata for a specific document                                  | `200`, `404`                             |
| `POST`   | `/documents`              | Upload, validate, parse, chunk, embed, and store                          | `200`, `400`, `413`, `422`, `500`        |
| `DELETE` | `/documents/{id}`         | Delete document, associated chunks, and stored file                       | `200`, `404`                             |
| `POST`   | `/documents/{id}/reindex` | Re-parse and re-embed document from stored upload                         | `200`, `404`, `422`                      |
| `POST`   | `/documents/{id}/summary` | Map/reduce summary of a complete indexed document, with source references | `200`, `404`, `409`, `413`, `422`, `502` |
| `GET`    | `/conversations`          | List conversations owned by the current session                           | `200`                                    |
| `POST`   | `/conversations`          | Create an empty conversation                                              | `201`                                    |
| `GET`    | `/conversations/{id}`     | Restore saved messages and citations                                      | `200`, `404`                             |
| `PATCH`  | `/conversations/{id}`     | Rename a conversation                                                     | `200`, `404`, `422`                      |
| `DELETE` | `/conversations/{id}`     | Delete a conversation and its messages                                    | `200`, `404`                             |
| `POST`   | `/chat`                   | Answer and persist a question/answer pair in a conversation               | `200`, `400`, `404`, `422`               |

### Chat Request Example

```json
{
  "question": "What is Apache Kafka used for?",
  "document_ids": ["c4b8b672-468e-4f51-b062-a5e2f75ef293"],
  "conversation_id": "existing-conversation-id"
}
```

`document_ids` and `conversation_id` are optional for compatibility. When omitted, chat uses all indexed documents owned by the current session and creates a conversation. Summary prompts process complete selected documents; factual questions use targeted hybrid retrieval, and broad, comparison, and extraction prompts retrieve a wider sample of sections. The browser uses the session cookie to scope all conversation operations.

---

## Testing & Evaluation

Execute the test suites via Python's unittest runner:

```bash
# Run metadata repository tests
.venv\Scripts\python.exe -m unittest evaluations/test_document_metadata.py

# Run parser tests (TXT, PDF, DOCX)
.venv\Scripts\python.exe -m unittest evaluations/test_parsers.py

# Run document lifecycle & session isolation tests
.venv\Scripts\python.exe -m unittest evaluations/test_document_lifecycle.py

# Run document-scoped filtering tests
.venv\Scripts\python.exe -m unittest evaluations/test_document_filtering.py

# Run all tests (from the backend directory; some legacy scripts use relative data paths)
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s ..\evaluations -t .. -p "test_*.py"
```

Conversation tables are created automatically in the existing `backend/sessions.sqlite3` database when the API starts; no manual migration is required.

---

## Security, Privacy & Reliability

- **Session Ownership**: Every document operation validates the caller's session ID against the database. Non-existent documents and documents belonging to other sessions return `404 Not Found` to prevent identity enumeration.
- **Untrusted Input**: Document text is treated strictly as untrusted data placed inside grounded prompt boundaries.
- **No Path Traversal**: Files are stored using server-generated UUIDs on disk rather than untrusted client filenames.
- **Cascade Deletion**: When an anonymous session expires, its SQLite records, vector collection in ChromaDB, and uploaded files on disk are automatically purged.

---

## Deployment Caveats

- **Ollama Inference**: Local CPU/GPU models cannot be called by publicly hosted cloud services without a self-hosted inference proxy or tunnel. For cloud deployments, replace `llm.py` with an external hosted model provider (e.g. OpenAI, Anthropic, or Hugging Face Inference API).
- **Persistent Disk**: SQLite and ChromaDB require persistent disk storage. On ephemeral hosts (e.g. basic free tiers), uploads and vectors will reset on server restart. Use persistent block volumes or external storage when deploying to production.
