import React, { useRef, useState } from "react";

export default function UploadDropzone({ onUpload, uploading, uploadError, setUploadError }) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  function handleFile(file) {
    if (!file) return;
    if (setUploadError) setUploadError("");

    const allowed = [".txt", ".pdf", ".docx"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();

    if (!allowed.includes(ext)) {
      if (setUploadError) {
        setUploadError(`Unsupported file format '${ext}'. Please upload .txt, .pdf, or .docx.`);
      }
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      if (setUploadError) {
        setUploadError("File exceeds the 2 MB maximum size limit.");
      }
      return;
    }

    if (file.size === 0) {
      if (setUploadError) {
        setUploadError("The selected file is empty.");
      }
      return;
    }

    onUpload(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (uploading) return;
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      handleFile(droppedFile);
    }
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!uploading) setIsDragging(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  return (
    <div className="dropzone-wrapper">
      <div
        className={`dropzone ${isDragging ? "dragging" : ""} ${uploading ? "uploading" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !uploading) {
            fileInputRef.current?.click();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden-file-input"
          accept=".txt,.pdf,.docx,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
          disabled={uploading}
        />

        <div className="dropzone-content">
          <div className="dropzone-icon-circle">
            {uploading ? (
              <span className="spinner-icon" />
            ) : (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
            )}
          </div>

          <div className="dropzone-text">
            <p className="dropzone-main-text">
              {uploading ? (
                <strong>Processing and indexing document...</strong>
              ) : (
                <>
                  <span className="drop-link">Drop your files here, or browse</span>
                </>
              )}
            </p>
            <p className="dropzone-sub-text">Supports .txt, .pdf, and .docx (up to 2 MB)</p>
          </div>
        </div>
      </div>

      {uploadError && (
        <div className="dropzone-error-alert" role="alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <span>{uploadError}</span>
          <button
            type="button"
            className="alert-close"
            onClick={() => setUploadError && setUploadError("")}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
