import React from 'react';
import { AlertTriangle, X, Trash2 } from 'lucide-react';

export default function DeleteConfirmModal({ sourceName, onConfirm, onCancel, isDeleting }) {
  if (!sourceName) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal-card delete-modal-card">
        {/* Modal Header */}
        <div className="modal-header-styled modal-header-red">
          <div className="flex-header-title">
            <div className="modal-icon-badge badge-red">
              <AlertTriangle size={18} />
            </div>
            <div>
              <h3 className="modal-title-text text-red-900">Delete Ingested Source</h3>
              <p className="modal-subtitle-text text-red-700">Permanent database action</p>
            </div>
          </div>
          <button onClick={onCancel} className="modal-close-icon-btn" disabled={isDeleting}>
            <X size={16} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body-container">
          <p className="delete-prompt-text">
            Are you sure you want to permanently delete <strong className="highlight-source-name">{sourceName}</strong>?
          </p>

          <div className="warning-callout-box">
            <span className="warning-callout-title">⚠️ PERMANENT DELETION WARNING</span>
            <p className="warning-callout-desc">
              This action will remove all vector embeddings, document text chunks, and metadata from your <strong>Supabase pgvector database</strong>. This action cannot be undone.
            </p>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="modal-footer-styled">
          <button 
            type="button" 
            onClick={onCancel} 
            className="secondary-modal-btn"
            disabled={isDeleting}
          >
            Cancel
          </button>
          <button 
            type="button" 
            onClick={onConfirm} 
            className="danger-modal-btn"
            disabled={isDeleting}
          >
            {isDeleting ? (
              <span className="flex-center-gap">
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                Deleting...
              </span>
            ) : (
              <span className="flex-center-gap">
                <Trash2 size={14} />
                <span>Delete Permanently</span>
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
