import React, { useState } from 'react';
import { Database, X, CheckCircle2, Copy, Check } from 'lucide-react';

export default function SourceMetadataModal({ source, onClose }) {
  const [copied, setCopied] = useState(false);
  if (!source) return null;

  const recordId = source.id || '2cc26028-f178-4585-9716-b9c919325d74';

  const handleCopyId = () => {
    navigator.clipboard.writeText(recordId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-card metadata-modal-card">
        {/* Modal Header */}
        <div className="modal-header-styled">
          <div className="flex-header-title">
            <div className="modal-icon-badge badge-indigo">
              <Database size={18} />
            </div>
            <div>
              <h3 className="modal-title-text">Vector Record Inspector</h3>
              <p className="modal-subtitle-text">Metadata details stored in Supabase pgvector</p>
            </div>
          </div>
          <button onClick={onClose} className="modal-close-icon-btn">
            <X size={16} />
          </button>
        </div>

        {/* Modal Content */}
        <div className="modal-body-container">
          
          {/* Source Name Box */}
          <div className="metadata-info-box mb-4">
            <div className="info-label font-bold">SOURCE NAME</div>
            <div className="info-value-text font-bold break-all">{source.name}</div>
          </div>

          {/* 2-Column Grid: Type & Status */}
          <div className="metadata-grid-2col mb-4">
            <div className="metadata-info-box">
              <div className="info-label">INGESTION TYPE</div>
              <span className={`type-tag type-${source.type.toLowerCase()}`}>
                {source.type}
              </span>
            </div>

            <div className="metadata-info-box">
              <div className="info-label">STATUS</div>
              <span className="status-badge-ingested">
                <span className="pulse-dot-green"></span>
                Vector Ingested
              </span>
            </div>
          </div>

          {/* Database Record UUID Box */}
          <div className="metadata-info-box mb-4">
            <div className="flex-between mb-1">
              <div className="info-label">SUPABASE RECORD UUID</div>
              <button className="copy-uuid-btn" onClick={handleCopyId}>
                {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <div className="code-uuid-block font-mono">
              {recordId}
            </div>
          </div>

          {/* Storage & Embeddings Metrics Banner */}
          <div className="metrics-banner-box">
            <div className="metrics-header-row">
              <CheckCircle2 size={16} className="text-indigo-600" />
              <span className="metrics-title">EMBEDDING & VECTOR METRICS</span>
            </div>
            <p className="metrics-desc-text">
              Vectors embedded via <strong>sentence-transformers</strong> into Supabase <strong>pgvector</strong>. Document chunks are indexed and ready for hybrid RAG query retrieval.
            </p>
          </div>

        </div>

        {/* Modal Footer */}
        <div className="modal-footer-styled">
          <button onClick={onClose} className="primary-modal-btn">
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
