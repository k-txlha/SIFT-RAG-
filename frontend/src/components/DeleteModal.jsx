import React from "react";

export default function DeleteModal({ doc, onConfirm, onCancel, deleting }) {
  if (!doc) return null;

  return (
    <div className="modal-backdrop" onClick={onCancel} role="dialog" aria-modal="true">
      <div
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-danger-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#DC2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
          </div>
          <div>
            <h3 className="modal-title">Delete Document?</h3>
            <p className="modal-subtitle">This action cannot be undone.</p>
          </div>
        </div>

        <div className="modal-body">
          <p>
            Are you sure you want to delete <strong>“{doc.filename}”</strong>?
            All indexed chunks ({doc.chunk_count || 0} chunks) and the stored source file will be permanently removed from this session.
          </p>
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="modal-btn cancel-btn"
            onClick={onCancel}
            disabled={deleting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="modal-btn delete-btn"
            onClick={() => onConfirm(doc.document_id, doc.filename)}
            disabled={deleting}
          >
            {deleting ? (
              <>
                <span className="spinner-icon-sm" />
                <span>Deleting...</span>
              </>
            ) : (
              "Delete document"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
