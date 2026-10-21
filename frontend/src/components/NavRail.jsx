export default function NavRail({
  documentCount = 0,
  chunksCount = 0,
  sessionStatus = "Session ready",
  activeTab = "documents",
  setActiveTab,
  mobileOpen = false,
  setMobileOpen,
  conversations = [],
  activeConversationId,
  onOpenConversation,
  onNewConversation,
  onRenameConversation,
  onDeleteConversation,
}) {
  return (
    <>
      {mobileOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}
      <aside className={`nav-rail ${mobileOpen ? "open" : ""}`}>
        <div className="nav-brand">
          <div className="nav-logo-icon">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
          </div>
          <span className="brand-text">SIFT</span>
        </div>

        <nav className="nav-menu">
          <button
            type="button"
            className={`nav-item ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTab) setActiveTab("overview");
              if (setMobileOpen) setMobileOpen(false);
            }}
          >
            <svg
              className="nav-icon"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
            <span>Overview</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeTab === "documents" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTab) setActiveTab("documents");
              if (setMobileOpen) setMobileOpen(false);
            }}
          >
            <svg
              className="nav-icon"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
            <span>Documents</span>
            {documentCount > 0 && (
              <span className="nav-badge">{documentCount}</span>
            )}
          </button>

          <button
            type="button"
            className={`nav-item ${activeTab === "conversations" ? "active" : ""}`}
            onClick={() => {
              if (setActiveTab) setActiveTab("conversations");
              if (setMobileOpen) setMobileOpen(false);
            }}
          >
            <svg
              className="nav-icon"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <span>Conversations</span>
          </button>
        </nav>

        {activeTab === "conversations" && (
          <section
            className="conversation-history"
            aria-label="Conversation history"
          >
            <div className="conversation-history-heading">
              <span>History</span>
              <button type="button" onClick={onNewConversation}>
                New
              </button>
            </div>
            {conversations.length === 0 ? (
              <p className="conversation-history-empty">
                No saved conversations yet.
              </p>
            ) : (
              <div className="conversation-history-list">
                {conversations.map((conversation) => (
                  <div
                    className={`conversation-history-row ${
                      activeConversationId === conversation.conversation_id
                        ? "active"
                        : ""
                    }`}
                    key={conversation.conversation_id}
                  >
                    <button
                      type="button"
                      className="conversation-open-button"
                      onClick={() =>
                        onOpenConversation(conversation.conversation_id)
                      }
                      title={conversation.title}
                    >
                      {conversation.title}
                    </button>
                    <button
                      type="button"
                      className="conversation-row-action"
                      onClick={() => onRenameConversation(conversation)}
                      aria-label={`Rename ${conversation.title}`}
                      title="Rename"
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      className="conversation-row-action danger"
                      onClick={() => onDeleteConversation(conversation)}
                      aria-label={`Delete ${conversation.title}`}
                      title="Delete"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        <div className="nav-footer">
          <div className="session-card">
            <div className="session-status-row">
              <span
                className={`status-dot ${sessionStatus.toLowerCase().includes("ready") || sessionStatus.toLowerCase().includes("active") ? "ready" : ""}`}
              />
              <span className="session-status-text">{sessionStatus}</span>
            </div>
            <div className="session-meta">
              <span>
                {documentCount} {documentCount === 1 ? "file" : "files"}
              </span>
              <span className="dot-sep">·</span>
              <span>
                {chunksCount} {chunksCount === 1 ? "chunk" : "chunks"}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
