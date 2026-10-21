import React, { useState } from "react";

export default function SourceCitation({ source, index }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`source-citation-card ${expanded ? "expanded" : ""}`}>
      <div
        className="source-card-header"
        onClick={() => setExpanded((prev) => !prev)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setExpanded((prev) => !prev);
        }}
      >
        <div className="source-title-left">
          <svg className="source-doc-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span className="source-filename" title={source.filename || source.source}>
            {source.filename || source.source}
          </span>
        </div>

        <div className="source-badges-right">
          {source.page_number && (
            <span className="source-badge page-badge">Page {source.page_number}</span>
          )}
          {source.chunk_index !== undefined && (
            <span className="source-badge chunk-badge">Chunk {source.chunk_index}</span>
          )}
          {source.retrieval_score !== undefined && (
            <span className="source-badge score-badge">Score {source.retrieval_score}</span>
          )}
          <svg className={`chevron-icon ${expanded ? "open" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
      </div>

      {expanded && source.text && (
        <div className="source-card-body">
          <blockquote className="source-quote">
            “{source.text}”
          </blockquote>
        </div>
      )}
    </div>
  );
}
