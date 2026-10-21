import React, { useState, useMemo } from "react";
import UploadDropzone from "./UploadDropzone";
import DocumentRow from "./DocumentRow";

export default function DocumentLibrary({
  documents = [],
  selectedDocIds = [],
  onToggleSelect,
  onSelectAll,
  onDeselectAll,
  onUpload,
  uploading,
  uploadError,
  setUploadError,
  onReindex,
  onDeleteRequest,
  busyDocIds = {},
  onOpenMobileAssistant,
  mobileAssistantCount,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState("list"); // 'list' or 'grid'

  // Filter documents by search query
  const filteredDocs = useMemo(() => {
    if (!searchQuery.trim()) return documents;
    const query = searchQuery.toLowerCase().trim();
    return documents.filter(
      (doc) =>
        doc.filename.toLowerCase().includes(query) ||
        (doc.file_type && doc.file_type.toLowerCase().includes(query)) ||
        (doc.status && doc.status.toLowerCase().includes(query))
    );
  }, [documents, searchQuery]);

  const allFilteredSelected =
    filteredDocs.length > 0 &&
    filteredDocs.every((doc) => selectedDocIds.includes(doc.document_id));

  function handleMasterCheckboxChange() {
    if (allFilteredSelected) {
      onDeselectAll();
    } else {
      onSelectAll(filteredDocs.map((d) => d.document_id));
    }
  }

  return (
    <section className="document-library">
      {/* Top Breadcrumb */}
      <div className="breadcrumb-bar">
        <span className="crumb-root">Workspace</span>
        <span className="crumb-sep">/</span>
        <span className="crumb-current">Documents</span>

        {/* Mobile Assistant Toggle */}
        <button
          type="button"
          className="mobile-assistant-toggle-btn"
          onClick={onOpenMobileAssistant}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <span>Ask Assistant</span>
          {mobileAssistantCount > 0 && (
            <span className="mobile-assistant-badge">{mobileAssistantCount}</span>
          )}
        </button>
      </div>

      {/* Library Header */}
      <div className="library-header">
        <div className="library-title-group">
          <h1 className="library-title">Your documents</h1>
          <p className="library-subtitle">
            Upload and manage the sources your AI can learn from.
          </p>
        </div>

        <button
          type="button"
          className="btn-primary-upload"
          onClick={() => {
            const input = document.querySelector(".dropzone .hidden-file-input");
            if (input) input.click();
          }}
          disabled={uploading}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          <span>Upload files</span>
        </button>
      </div>

      {/* Upload Dropzone */}
      <UploadDropzone
        onUpload={onUpload}
        uploading={uploading}
        uploadError={uploadError}
        setUploadError={setUploadError}
      />

      {/* Controls Bar: All Documents Count, Search, View Mode */}
      <div className="library-controls-bar">
        <div className="controls-left">
          <span className="tab-pill-active">
            All documents <span className="count-pill">{documents.length}</span>
          </span>
          {selectedDocIds.length > 0 && selectedDocIds.length < documents.length && (
            <span className="selection-indicator">
              ({selectedDocIds.length} of {documents.length} selected for chat)
            </span>
          )}
        </div>

        <div className="controls-right">
          <div className="search-box">
            <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              placeholder="Search in documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
              >
                ×
              </button>
            )}
          </div>

          <div className="view-toggle">
            <button
              type="button"
              className={`view-btn ${viewMode === "list" ? "active" : ""}`}
              onClick={() => setViewMode("list")}
              title="List view"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="8" y1="6" x2="21" y2="6"></line>
                <line x1="8" y1="12" x2="21" y2="12"></line>
                <line x1="8" y1="18" x2="21" y2="18"></line>
                <line x1="3" y1="6" x2="3.01" y2="6"></line>
                <line x1="3" y1="12" x2="3.01" y2="12"></line>
                <line x1="3" y1="18" x2="3.01" y2="18"></line>
              </svg>
            </button>
            <button
              type="button"
              className={`view-btn ${viewMode === "grid" ? "active" : ""}`}
              onClick={() => setViewMode("grid")}
              title="Grid view"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Document Table / List */}
      <div className={`documents-container ${viewMode}`}>
        {/* Table Column Headers (List mode) */}
        {viewMode === "list" && (
          <div className="table-header-row">
            <div className="row-col col-check">
              <input
                type="checkbox"
                className="doc-checkbox"
                checked={allFilteredSelected}
                onChange={handleMasterCheckboxChange}
                disabled={filteredDocs.length === 0}
                aria-label="Select all documents"
                title="Select/deselect all"
              />
            </div>
            <div className="row-col col-file">
              <span className="th-label">Document name</span>
            </div>
            <div className="row-col col-status">
              <span className="th-label">Status</span>
            </div>
            <div className="row-col col-date">
              <span className="th-label">Date added</span>
            </div>
            <div className="row-col col-actions">
              <span className="th-label sr-only">Actions</span>
            </div>
          </div>
        )}

        {/* Content rows */}
        {filteredDocs.length === 0 ? (
          <div className="empty-documents-state">
            <div className="empty-icon-circle">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
            </div>
            <h3>{searchQuery ? "No matching documents" : "No documents yet"}</h3>
            <p className="empty-sub">
              {searchQuery
                ? `No documents matching "${searchQuery}". Try a different keyword.`
                : "Upload .txt, .pdf, or .docx files to populate your knowledge library."}
            </p>
            {searchQuery && (
              <button
                type="button"
                className="clear-search-link"
                onClick={() => setSearchQuery("")}
              >
                Clear search filter
              </button>
            )}
          </div>
        ) : (
          <div className="document-rows-wrapper">
            {filteredDocs.map((doc) => (
              <DocumentRow
                key={doc.document_id}
                doc={doc}
                isSelected={selectedDocIds.includes(doc.document_id)}
                onToggleSelect={onToggleSelect}
                onReindex={onReindex}
                onDeleteRequest={onDeleteRequest}
                isBusy={Boolean(busyDocIds[doc.document_id])}
                busyAction={busyDocIds[doc.document_id]}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
