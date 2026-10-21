import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "./api";
import NavRail from "./components/NavRail";
import DocumentLibrary from "./components/DocumentLibrary";
import AssistantPanel from "./components/AssistantPanel";
import DeleteModal from "./components/DeleteModal";
import "./App.css";

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [chunksCount, setChunksCount] = useState(0);
  const [sessionStatus, setSessionStatus] = useState("Connecting...");

  // Action states
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [busyDocIds, setBusyDocIds] = useState({});
  const [confirmDeleteDoc, setConfirmDeleteDoc] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Chat states
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(
    () => window.localStorage.getItem("little-rag-active-conversation")
  );
  const initialConversationId = useRef(activeConversationId);
  const [chatError, setChatError] = useState("");
  const [summarizing, setSummarizing] = useState(false);

  // Responsive states
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [mobileAssistantOpen, setMobileAssistantOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("documents");

  // Load session summary
  const loadSession = useCallback(async () => {
    try {
      const data = await apiFetch("/session");
      if (data) {
        setChunksCount(data.chunks_count ?? 0);
        setSessionStatus("Session ready");
      }
    } catch {
      setSessionStatus("API unavailable");
    }
  }, []);

  // Load document library
  const loadDocuments = useCallback(async (isInitial = false) => {
    try {
      const data = await apiFetch("/documents");
      const docs = data?.documents || [];
      setDocuments(docs);

      // On initial load, default to selecting all indexed documents
      if (isInitial && docs.length > 0) {
        const indexedIds = docs
          .filter((d) => d.status === "indexed")
          .map((d) => d.document_id);
        setSelectedDocIds(indexedIds);
      }
    } catch (err) {
      console.error("Failed to load documents:", err);
    }
  }, []);

  const loadConversations = useCallback(async () => {
    const data = await apiFetch("/conversations");
    const items = data?.conversations || [];
    setConversations(items);
    return items;
  }, []);

  const openConversation = useCallback(async (conversationId) => {
    setChatError("");
    try {
      const conversation = await apiFetch(`/conversations/${conversationId}`);
      setActiveConversationId(conversation.conversation_id);
      setMessages(conversation.messages || []);
      setActiveTab("conversations");
    } catch (err) {
      setChatError(`Could not open conversation: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    async function init() {
      await loadSession();
      await loadDocuments(true);
      try {
        const items = await loadConversations();
          const rememberedId = initialConversationId.current;
        const initial = items.find((item) => item.conversation_id === rememberedId) || items[0];
        if (initial) await openConversation(initial.conversation_id);
          else setActiveConversationId(null);
      } catch (err) {
        setChatError(`Failed to load conversation history: ${err.message}`);
      }
    }
    init();
  }, [loadSession, loadDocuments, loadConversations, openConversation]);

  useEffect(() => {
    if (activeConversationId) {
      window.localStorage.setItem("little-rag-active-conversation", activeConversationId);
    } else {
      window.localStorage.removeItem("little-rag-active-conversation");
    }
  }, [activeConversationId]);

  // Selection handlers
  function handleToggleSelect(docId) {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  }

  function handleSelectAll(ids) {
    setSelectedDocIds(ids || documents.map((d) => d.document_id));
  }

  function handleDeselectAll() {
    setSelectedDocIds([]);
  }

  function handleResetScope() {
    setSelectedDocIds(documents.map((d) => d.document_id));
  }

  // Upload handler
  async function handleUpload(file) {
    setUploading(true);
    setUploadError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const result = await apiFetch("/documents", {
        method: "POST",
        body: formData,
      });

      // Refresh data
      await loadDocuments(false);
      await loadSession();

      // Ensure newly uploaded document is included in scope
      if (result?.document_id) {
        setSelectedDocIds((prev) =>
          prev.includes(result.document_id) ? prev : [...prev, result.document_id]
        );
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          text: `“${result.filename}” indexed successfully (${result.chunk_count} chunks ready).`,
        },
      ]);
    } catch (err) {
      setUploadError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  // Re-index handler
  async function handleReindex(documentId, filename) {
    setBusyDocIds((prev) => ({ ...prev, [documentId]: "reindexing" }));

    try {
      const updated = await apiFetch(`/documents/${documentId}/reindex`, {
        method: "POST",
      });

      await loadDocuments(false);
      await loadSession();

      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          text: `“${filename}” re-indexed successfully (${updated.chunk_count} chunks).`,
        },
      ]);
    } catch (err) {
      alert(`Re-indexing failed: ${err.message}`);
    } finally {
      setBusyDocIds((prev) => {
        const next = { ...prev };
        delete next[documentId];
        return next;
      });
    }
  }

  // Delete handler
  async function handleDeleteConfirm(documentId, filename) {
    setDeleting(true);
    setBusyDocIds((prev) => ({ ...prev, [documentId]: "deleting" }));

    try {
      await apiFetch(`/documents/${documentId}`, {
        method: "DELETE",
      });

      setConfirmDeleteDoc(null);
      setSelectedDocIds((prev) => prev.filter((id) => id !== documentId));

      await loadDocuments(false);
      await loadSession();

      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          text: `“${filename}” was removed from the library.`,
        },
      ]);
    } catch (err) {
      alert(`Deletion failed: ${err.message}`);
    } finally {
      setDeleting(false);
      setBusyDocIds((prev) => {
        const next = { ...prev };
        delete next[documentId];
        return next;
      });
    }
  }

  // Ask question handler
  async function handleAsk(query) {
    if (!query || asking) return;

    // Zero documents selected check
    if (selectedDocIds.length === 0) return;

    setChatError("");
    setAsking(true);

    try {
      let conversationId = activeConversationId;
      if (!conversationId) {
        const created = await apiFetch("/conversations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        conversationId = created.conversation_id;
        setActiveConversationId(conversationId);
      }

      const payload = { question: query };
      payload.conversation_id = conversationId;
      // If a subset of documents is selected, specify document_ids
      if (selectedDocIds.length < documents.length) {
        payload.document_ids = selectedDocIds;
      }

      const response = await apiFetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      setMessages((prev) => [
        ...prev,
      { role: "user", text: query, sources: [] },
      { role: "assistant", text: response.answer, sources: response.sources || [], timings_ms: response.timings_ms },
    ]);
    await loadConversations();
    return true;
    } catch (err) {
    setChatError(err.message || "Failed to generate an answer. Your existing conversation was not changed.");
    return false;
    } finally {
    setAsking(false);
    }
  }

  async function handleNewConversation() {
    try {
    setChatError("");
    const conversation = await apiFetch("/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    setConversations((prev) => [conversation, ...prev]);
    setActiveConversationId(conversation.conversation_id);
    setMessages([]);
    setActiveTab("conversations");
    } catch (err) {
    setChatError(`Could not create a new conversation: ${err.message}`);
    }
  }

  async function handleRenameConversation(conversation) {
    const title = window.prompt("Rename conversation", conversation.title);
    if (title === null || !title.trim()) return;
    try {
    const updated = await apiFetch(`/conversations/${conversation.conversation_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim() }),
    });
    setConversations((prev) =>
      prev.map((item) => item.conversation_id === updated.conversation_id ? updated : item)
    );
    } catch (err) {
    setChatError(`Could not rename conversation: ${err.message}`);
    }
  }

  async function handleDeleteConversation(conversation) {
    if (!window.confirm(`Delete "${conversation.title}" and its saved messages?`)) return;
    try {
    await apiFetch(`/conversations/${conversation.conversation_id}`, { method: "DELETE" });
    const remaining = conversations.filter(
      (item) => item.conversation_id !== conversation.conversation_id
    );
    setConversations(remaining);
    if (activeConversationId === conversation.conversation_id) {
      if (remaining.length) {
        await openConversation(remaining[0].conversation_id);
      } else {
        setActiveConversationId(null);
        setMessages([]);
      }
    }
    } catch (err) {
    setChatError(`Could not delete conversation: ${err.message}`);
    }
  }

  async function handleSummarizeDocument() {
    if (selectedDocIds.length !== 1 || summarizing) return;
    const documentId = selectedDocIds[0];
    const doc = documents.find((item) => item.document_id === documentId);
    if (!doc) return;

    setChatError("");
    setSummarizing(true);
    try {
    let conversationId = activeConversationId;
    if (!conversationId) {
      const created = await apiFetch("/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      conversationId = created.conversation_id;
      setActiveConversationId(conversationId);
    }
    const response = await apiFetch(`/documents/${documentId}/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId }),
    });
    setMessages((prev) => [
      ...prev,
      { role: "user", text: `Summarize ${doc.filename}`, sources: [] },
      { role: "assistant", text: response.answer, sources: response.sources || [] },
    ]);
    await loadConversations();
    } catch (err) {
    setChatError(`Document summary failed: ${err.message}`);
    } finally {
    setSummarizing(false);
    }
  }

  return (
    <div className="app-shell">
      {/* Mobile top bar */}
      <header className="mobile-header">
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={() => setMobileNavOpen(true)}
          aria-label="Open navigation"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>

        <span className="mobile-brand-title">SIFT</span>

        <button
          type="button"
          className="mobile-chat-toggle-btn"
          onClick={() => setMobileAssistantOpen((prev) => !prev)}
          aria-label="Toggle assistant"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          
        </button>
      </header>

      <div className="app-workspace-layout">
        {/* Left Navigation Rail (~220-245px) */}
        <NavRail
          documentCount={documents.length}
          chunksCount={chunksCount}
          sessionStatus={sessionStatus}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          mobileOpen={mobileNavOpen}
          setMobileOpen={setMobileNavOpen}
          conversations={conversations}
          activeConversationId={activeConversationId}
          onOpenConversation={openConversation}
          onNewConversation={handleNewConversation}
          onRenameConversation={handleRenameConversation}
          onDeleteConversation={handleDeleteConversation}
        />

        {/* Center Document Library (~54-60%) */}
        <DocumentLibrary
          documents={documents}
          selectedDocIds={selectedDocIds}
          onToggleSelect={handleToggleSelect}
          onSelectAll={handleSelectAll}
          onDeselectAll={handleDeselectAll}
          onUpload={handleUpload}
          uploading={uploading}
          uploadError={uploadError}
          setUploadError={setUploadError}
          onReindex={handleReindex}
          onDeleteRequest={setConfirmDeleteDoc}
          busyDocIds={busyDocIds}
          onOpenMobileAssistant={() => setMobileAssistantOpen(true)}
          mobileAssistantCount={messages.length}
        />

        {/* Right Assistant Panel (~32-36%, min 360px) */}
        <AssistantPanel
          messages={messages}
          onAsk={handleAsk}
          asking={asking}
          documents={documents}
          selectedDocIds={selectedDocIds}
          onResetScope={handleResetScope}
          onNewConversation={handleNewConversation}
          activeConversationId={activeConversationId}
          conversationTitle={conversations.find((item) => item.conversation_id === activeConversationId)?.title}
          onSummarizeDocument={handleSummarizeDocument}
          summarizing={summarizing}
          error={chatError}
          mobileOpen={mobileAssistantOpen}
          onCloseMobile={() => setMobileAssistantOpen(false)}
        />
      </div>

      {/* Delete Confirmation Modal */}
      {confirmDeleteDoc && (
        <DeleteModal
          doc={confirmDeleteDoc}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setConfirmDeleteDoc(null)}
          deleting={deleting}
        />
      )}
    </div>
  );
}
