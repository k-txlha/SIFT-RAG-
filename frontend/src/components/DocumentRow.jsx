import React, { useState, useRef, useEffect } from "react";

export default function DocumentRow({
  doc,
  isSelected,
  onToggleSelect,
  onReindex,
  onDeleteRequest,
  isBusy,
  busyAction,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [menuOpen]);

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    const kb = (bytes / 1024).toFixed(1);
    if (kb < 1024) return `${kb} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
  }

  function formatDate(val) {
    if (!val) return "";
    try {
      const d = typeof val === "number" ? new Date(val * 1000) : new Date(val);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return "";
    }
  }

  const fileExt = (doc.file_type || "txt").toLowerCase();

  return (
    <div
      className={`doc-row ${isSelected ? "selected" : ""} ${isBusy ? "busy" : ""}`}
      onClick={(e) => {
        // Toggle selection on row click if not clicking interactive controls
        if (!e.target.closest("button") && !e.target.closest("input") && !e.target.closest(".action-menu")) {
          onToggleSelect(doc.document_id);
        }
      }}
    >
      <div className="row-col col-check">
        <input
          type="checkbox"
          className="doc-checkbox"
          checked={isSelected}
          onChange={() => onToggleSelect(doc.document_id)}
          aria-label={`Select ${doc.filename} for chat context`}
        />
      </div>

      <div className="row-col col-file">
        <div className={`file-icon-badge ${fileExt}`}>
          {fileExt === "pdf" && (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <path d="M9 13h6"></path>
              <path d="M9 17h3"></path>
            </svg>
          )}
          {fileExt === "docx" && (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
          )}
          {fileExt === "txt" && (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
          )}
        </div>

        <div className="doc-info">
          <div className="doc-title-row">
            <span className="doc-filename" title={doc.filename}>{doc.filename}</span>
          </div>
          <div className="doc-meta-row">
            <span>{formatBytes(doc.size_bytes)}</span>
            <span className="meta-sep">·</span>
            <span>{doc.chunk_count || 0} {doc.chunk_count === 1 ? "chunk" : "chunks"}</span>
          </div>
        </div>
      </div>

      <div className="row-col col-status">
        {doc.status === "indexed" ? (
          <span className="status-badge ready">
            <span className="status-dot-green" />
            <span>Ready</span>
          </span>
        ) : doc.status === "processing" ? (
          <span className="status-badge processing">
            <span className="spinner-icon-sm" />
            <span>Processing</span>
          </span>
        ) : (
          <span className="status-badge failed" title={doc.error_message || "Failed"}>
            <span className="status-dot-red" />
            <span>Failed</span>
          </span>
        )}
      </div>

      <div className="row-col col-date">
        <span className="doc-date-text">{formatDate(doc.created_at)}</span>
      </div>

      <div className="row-col col-actions" ref={menuRef}>
        <button
          type="button"
          className="overflow-action-btn"
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen((prev) => !prev);
          }}
          disabled={isBusy}
          title="Document actions"
          aria-expanded={menuOpen}
        >
          {isBusy ? (
            <span className="spinner-icon-sm" />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="12" r="2" />
              <circle cx="12" cy="5" r="2" />
              <circle cx="12" cy="19" r="2" />
            </svg>
          )}
        </button>

        {menuOpen && (
          <div className="action-dropdown-menu">
            <button
              type="button"
              className="dropdown-item"
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(false);
                onReindex(doc.document_id, doc.filename);
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10"></polyline>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
              </svg>
              <span>Re-index document</span>
            </button>
            <button
              type="button"
              className="dropdown-item delete-item"
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(false);
                onDeleteRequest(doc);
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              <span>Delete</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
