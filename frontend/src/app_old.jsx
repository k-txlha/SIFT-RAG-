
import { useEffect, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

export default function App() {
    const [question, setQuestion] = useState("");
    const [messages, setMessages] = useState([]);
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [asking, setAsking] = useState(false);
    const [status, setStatus] = useState("Checking session...");
    const [documentsCount, setDocumentsCount] = useState(0);

    async function loadSession() {
        try {
            const response = await fetch(`${API}/session`, {
                credentials: "include",
            });
            if (!response.ok) throw new Error("Session unavailable");

            const data = await response.json();
            setDocumentsCount(data.documents_count);
            setStatus("Session ready");
        } catch {
            setStatus("API unavailable — start FastAPI first");
        }
    }

    useEffect(() => {
        loadSession();
    }, []);

    async function uploadDocument() {
        if (!file) return;

        setUploading(true);
        try {
            const body = new FormData();
            body.append("file", file);

            const response = await fetch(`${API}/documents`, {
                method: "POST",
                credentials: "include",
                body,
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Upload failed");
            }

            setDocumentsCount(data.documents_count);
            setStatus(`Uploaded ${data.filename}`);
            setMessages((previous) => [
                ...previous,
                {
                    role: "system",
                    text: `${data.filename} indexed successfully (${data.chunks_ingested} chunks).`,
                },
            ]);
            setFile(null);
        } catch (error) {
            setStatus(error.message);
        } finally {
            setUploading(false);
        }
    }

    async function askQuestion(event) {
        event.preventDefault();
        const currentQuestion = question.trim();

        if (!currentQuestion || asking) return;

        setMessages((previous) => [
            ...previous,
            { role: "user", text: currentQuestion },
        ]);
        setQuestion("");
        setAsking(true);

        try {
            const response = await fetch(`${API}/chat`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: currentQuestion }),
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Request failed");
            }

            setMessages((previous) => [
                ...previous,
                {
                    role: "assistant",
                    text: data.answer,
                    sources: data.sources || [],
                },
            ]);
        } catch (error) {
            setMessages((previous) => [
                ...previous,
                { role: "system", text: error.message },
            ]);
        } finally {
            setAsking(false);
        }
    }

    return (
        <main className="app">
            <header className="header">
                <a className="logo" href="/">little<span>rag</span></a>
                <span className="session-status">
                    <span className="status-dot" />
                    {status}
                </span>
            </header>

            <section className="workspace">
                <aside className="sidebar">
                    <p className="eyebrow">YOUR WORKSPACE</p>
                    <h2>Documents</h2>
                    <p className="muted">
                        Upload text files to build your private knowledge base.
                    </p>

                    <label className="upload-area">
                        <span className="upload-icon">＋</span>
                        <strong>{file ? file.name : "Choose a text file"}</strong>
                        <span className="muted">.txt · up to 2 MB</span>
                        <input
                            type="file"
                            accept=".txt,text/plain"
                            onChange={(event) =>
                                setFile(event.target.files?.[0] || null)
                            }
                        />
                    </label>

                    <button
                        className="primary-button"
                        onClick={uploadDocument}
                        disabled={!file || uploading}
                    >
                        {uploading ? "Indexing..." : "Upload document"}
                    </button>

                    <div className="document-count">
                        <span>Indexed chunks</span>
                        <strong>{documentsCount}</strong>
                    </div>

                    <p className="privacy-note">
                        Your documents are isolated to this browser session and
                        expire after inactivity.
                    </p>
                </aside>

                <section className="chat-panel">
                    <div className="chat-heading">
                        <div>
                            <p className="eyebrow">RETRIEVAL AUGMENTED GENERATION</p>
                            <h1>Ask your documents.</h1>
                        </div>
                        <span className="model-tag">Hybrid search</span>
                    </div>

                    <div className="messages">
                        {messages.length === 0 ? (
                            <div className="empty-state">
                                <span className="empty-icon">⌘</span>
                                <h2>A little more context.</h2>
                                <p>
                                    Upload a document, then ask a question.
                                    Answers are grounded in your indexed content.
                                </p>
                            </div>
                        ) : (
                            messages.map((message, index) => (
                                <article
                                    className={`message ${message.role}`}
                                    key={index}
                                >
                                    <span className="message-role">
                                        {message.role === "user"
                                            ? "YOU"
                                            : message.role === "assistant"
                                                ? "RAG ASSISTANT"
                                                : "SYSTEM"}
                                    </span>
                                    <p>{message.text}</p>

                                    {message.sources?.length > 0 && (
                                        <details className="sources">
                                            <summary>
                                                Sources ({message.sources.length})
                                            </summary>
                                            {message.sources.map((source, i) => (
                                                <div key={i} className="source-item">
                                                    <strong>{source.source}</strong>
                                                    {source.chunk_index !== undefined &&
                                                        ` · Chunk ${source.chunk_index}`}
                                                    {source.text && <p>{source.text}</p>}
                                                </div>
                                            ))}
                                        </details>
                                    )}
                                </article>
                            ))
                        )}
                        {asking && (
                            <p className="thinking">Searching and generating...</p>
                        )}
                    </div>

                    <form className="composer" onSubmit={askQuestion}>
                        <input
                            value={question}
                            onChange={(event) => setQuestion(event.target.value)}
                            placeholder="Ask something about your documents..."
                            maxLength={1000}
                        />
                        <button
                            type="submit"
                            disabled={!question.trim() || asking}
                        >
                            {asking ? "..." : "Ask ↗"}
                        </button>
                    </form>
                    <p className="footer-note">
                        Answers may be imperfect. Check the cited source chunks.
                    </p>
                </section>
            </section>
        </main>
    );
}
