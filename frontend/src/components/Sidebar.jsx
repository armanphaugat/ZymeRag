import React from 'react';
import { 
  Zap, 
  Settings, 
  Database, 
  FolderOpen, 
  Search,
  BarChart3, 
  User, 
  ShieldCheck, 
  ChevronDown, 
  ChevronLeft 
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab }) {
  return (
    <aside className="nori-sidebar">
      {/* ZymeRag Brand Header */}
      <div className="sidebar-brand-box">
        <div className="brand-logo">
          {/* ZymeRag Gradient Badge */}
          <div className="nori-avatar bg-gradient-to-tr from-violet-600 to-indigo-500 text-white flex items-center justify-center rounded-lg shadow-sm">
            <Zap size={20} className="fill-current text-white" />
          </div>
          <div className="flex flex-col">
            <span className="nori-brand-name font-bold text-gray-900 tracking-tight">ZymeRag</span>
            <span className="text-[10px] text-violet-600 font-semibold uppercase tracking-wider">Multimodal RAG</span>
          </div>
        </div>

        {/* Knowledge Vault Selector Dropdown */}
        <div className="bot-selector-pill cursor-pointer hover:bg-gray-100 transition-colors">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-indigo-600 flex items-center justify-center text-[10px] text-white font-bold">Z</div>
            <span className="text-xs font-semibold text-gray-700">Zyme Vector Vault</span>
          </div>
          <ChevronDown size={14} className="text-gray-400" />
        </div>
      </div>

      {/* Navigation Sections */}
      <div className="sidebar-menu-sections">
        {/* KNOWLEDGE ENGINE */}
        <div className="menu-group">
          <div className="menu-section-header">KNOWLEDGE ENGINE</div>
          <button 
            className={`menu-item ${activeTab === 'knowledge-base' ? 'active' : ''}`}
            onClick={() => setActiveTab('knowledge-base')}
          >
            <Database size={16} />
            <span>Knowledge Base</span>
          </button>
          <button 
            className={`menu-item ${activeTab === 'ingested-sources' ? 'active' : ''}`}
            onClick={() => setActiveTab('ingested-sources')}
          >
            <FolderOpen size={16} />
            <span>Ingested Sources</span>
          </button>
          <button className="menu-item opacity-75 hover:opacity-100">
            <Search size={16} />
            <span>Vector Search</span>
          </button>
          <button className="menu-item opacity-75 hover:opacity-100">
            <BarChart3 size={16} />
            <span>Analytics & DB Stats</span>
          </button>
        </div>

        {/* SYSTEM & CONFIG */}
        <div className="menu-group">
          <div className="menu-section-header">SYSTEM & CONFIG</div>
          <button className="menu-item opacity-75 hover:opacity-100">
            <Settings size={16} />
            <span>Embedding Models</span>
          </button>
          <button className="menu-item opacity-75 hover:opacity-100">
            <ShieldCheck size={16} />
            <span>Supabase Connection</span>
          </button>
          <button className="menu-item opacity-75 hover:opacity-100">
            <User size={16} />
            <span>API Keys</span>
          </button>
        </div>
      </div>

      {/* Collapse Footer */}
      <div className="sidebar-footer">
        <button className="collapse-btn">
          <ChevronLeft size={16} />
          <span>Collapse Sidebar</span>
        </button>
      </div>
    </aside>
  );
}
