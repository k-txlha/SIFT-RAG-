import { useState, useRef, useEffect } from "react";
import SourceCitation from "./SourceCitation";

const SUGGESTIONS = [
  "Summarize the selected documents.",
  "What are the main topics discussed across the documents?",
  "Compare the selected documents.",
  "Extract the key dates, figures, and names.",
];

function renderAnswer(text) {
  return text.split("\n").map((line, index) => {
    if (line.startsWith("## ")) {
      return <strong className="answer-section-heading" key={index}>{line.slice(3)}</strong>;
    }
    if (line.startsWith("- ")) {
      return <span className="answer-list-item" key={index}>• {line.slice(2)}<br /></span>;
    }
    return line
      ? <span key={index}>{line}<br /></span>
      : <br key={index} />;
  });
}

export default function AssistantPanel({
  messages = [],
  onAsk,
  asking,
  documents = [],
  selectedDocIds = [],
  onResetScope,
  onNewConversation,
  conversationTitle,
  onSummarizeDocument,
  summarizing = false,
  error = "",
  mobileOpen = false,
  onCloseMobile,
}) {
  const [question, setQuestion] = useState("");
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function handleSubmit(e, directQuery) {
    if (e) e.preventDefault();
    const query = (directQuery || question).trim();
    if (!query || asking) return;
    if (selectedDocIds.length === 0) return;

    const saved = await onAsk(query);
    if (saved !== false) setQuestion("");
  }

  function handleCopy(text) {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(text);
    }
  }

  const zeroSelected = documents.length > 0 && selectedDocIds.length === 0;
  const isSubset = selectedDocIds.length > 0 && selectedDocIds.length < documents.length;
  const scopeChipText = documents.length === 0
    ? "No documents in library"
    : zeroSelected
      ? "0 documents selected"
      : isSubset
        ? `Using ${selectedDocIds.length} of ${documents.length} documents`
        : `Using all ${documents.length} documents`;

  return (
    <aside className={`assistant-panel ${mobileOpen ? "mobile-open" : ""}`}>
      {/* Panel Header */}
      <div className="assistant-header">
        <div className="assistant-header-left">
          <div className="assistant-spark-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path>
            </svg>
          </div>
          <div>
            <h2 className="assistant-title">
              {conversationTitle || "Ask your knowledge"}
            </h2>
            <p className="assistant-scope-sub">{scopeChipText}</p>
          </div>
        </div>

        <div className="assistant-header-right">
          <button
            type="button"
            className="assistant-action-icon-btn"
            onClick={onNewConversation}
            title="Start a new conversation"
            aria-label="Start a new conversation"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>

          {mobileOpen && (
            <button
              type="button"
              className="assistant-close-mobile-btn"
              onClick={onCloseMobile}
              title="Close assistant"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="assistant-error" role="alert">
          {error}
        </div>
      )}

      {/* Messages or Empty State */}
      <div className="assistant-messages-container">
        {messages.length === 0 ? (
          <div className="assistant-empty-state">
            <div className="empty-spark-circle">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#5148F5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path>
              </svg>
            </div>
            <h3 className="empty-heading">What would you like to know?</h3>
            <p className="empty-description">
              Ask questions and get answers grounded in your selected documents.
            </p>

            <div className="suggestions-list">
              {SUGGESTIONS.map((suggestion, index) => (
                <button
                  key={index}
                  type="button"
                  className="suggestion-item-btn"
                  onClick={() => handleSubmit(null, suggestion)}
                  disabled={zeroSelected || documents.length === 0 || asking}
                >
                  <span className="suggestion-text">{suggestion}</span>
                  <svg className="suggestion-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                    <polyline points="12 5 19 12 12 19"></polyline>
                  </svg>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="messages-stream">
            {messages.map((msg, index) => (
              <div key={index} className={`chat-message ${msg.role}`}>
                <div className="chat-message-header">
                  <span className="chat-role-label">
                    {msg.role === "user" ? "You" : "Assistant"}
                  </span>
                  {msg.timings_ms && (
                    <span className="timing-chip" title="Retrieval and generation latency">
                      ⚡ {msg.timings_ms.total}ms
                    </span>
                  )}
                  {msg.role === "assistant" && (
                    <button
                      type="button"
                      className="copy-answer-btn"
                      onClick={() => handleCopy(msg.text)}
                      title="Copy response"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                      </svg>
                      <span>Copy</span>
                    </button>
                  )}
                </div>

                <div className="chat-message-content">
                  {renderAnswer(msg.text)}
                </div>

                {msg.sources && msg.sources.length > 0 && (
                  <div className="sources-container">
                    <div className="sources-header-bar">
                      <span className="sources-title">
                        Sources cited ({msg.sources.length})
                      </span>
                    </div>
                    <div className="sources-cards-list">
                      {msg.sources.map((source, sIdx) => (
                        <SourceCitation key={sIdx} source={source} index={sIdx} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {asking && (
              <div className="chat-message assistant thinking">
                <div className="chat-message-header">
                  <span className="chat-role-label">Assistant</span>
                </div>
                <div className="thinking-row">
                  <div className="thinking-dots">
                    <span />
                    <span />
                    <span />
                  </div>
                  <span className="thinking-text">Searching indexed documents & generating grounded response...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Composer Section */}
      <div className="assistant-composer-section">
        {selectedDocIds.length === 1 && (
          <button
            type="button"
            className="summarize-document-button"
            onClick={onSummarizeDocument}
            disabled={summarizing || asking}
          >
            {summarizing ? "Summarizing entire document..." : "Summarize selected document"}
          </button>
        )}
        {/* Scope chip */}
        <div className={`composer-scope-chip ${zeroSelected ? "warning" : ""}`}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
            <polyline points="2 17 12 22 22 17"></polyline>
            <polyline points="2 12 12 17 22 12"></polyline>
          </svg>
          <span className="scope-chip-label">{scopeChipText}</span>
          {isSubset && onResetScope && (
            <button
              type="button"
              className="scope-chip-clear"
              onClick={onResetScope}
              title="Reset scope to all documents"
            >
              Reset
            </button>
          )}
        </div>

        {zeroSelected ? (
          <div className="composer-disabled-hint">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>Select at least one document above to enable question answering.</span>
          </div>
        ) : null}

        <form className="composer-form" onSubmit={(e) => handleSubmit(e)}>
          <input
            ref={inputRef}
            type="text"
            className="composer-input"
            placeholder={
              zeroSelected
                ? "Select a document to ask questions..."
                : isSubset
                ? `Ask about selected documents...`
                : "Ask anything about your documents..."
            }
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={zeroSelected || documents.length === 0 || asking}
            maxLength={1000}
          />
          <button
            type="submit"
            className="composer-submit-btn"
            disabled={!question.trim() || zeroSelected || documents.length === 0 || asking}
            aria-label="Submit question"
          >
            {asking ? (
              <span className="spinner-icon-sm" />
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            )}
          </button>
        </form>
      </div>
    </aside>
  );
}
