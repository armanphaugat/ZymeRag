import React from 'react';
import { Zap, Upload, Database } from 'lucide-react';

export default function Header({ activeTab, setActiveTab }) {
  return (
    <header className="zymerag-header">
      <div className="header-container">
        {/* Brand Logo */}
        <div className="header-brand">
          <div className="brand-badge">
            <Zap size={18} className="fill-current text-white" />
          </div>
          <div className="brand-text">
            <span className="brand-name">ZymeRag</span>
            <span className="brand-sub">Multimodal RAG Engine</span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="header-tabs">
          <button 
            className={`tab-pill ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
          >
            <Upload size={15} />
            <span>Ingest Data</span>
          </button>
          <button 
            className={`tab-pill ${activeTab === 'sources' ? 'active' : ''}`}
            onClick={() => setActiveTab('sources')}
          >
            <Database size={15} />
            <span>Ingested Sources</span>
          </button>
        </nav>

        {/* Right Status Indicator & User Pill */}
        <div className="header-actions">
          <span className="connection-badge">
            <span className="green-pulse"></span>
            Supabase Connected
          </span>
          <div className="user-badge">
            <div className="user-avatar">ZR</div>
            <span className="user-name">Zyme Admin</span>
          </div>
        </div>
      </div>
    </header>
  );
}
