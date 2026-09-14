import React from 'react';
import { Moon, Sun, Database, Sparkles } from 'lucide-react';

export default function TopBar({ activeTab }) {
  return (
    <header className="nori-topbar">
      <div className="topbar-left">
        <span className="topbar-title">
          {activeTab === 'knowledge-base' ? 'Knowledge Base' : 'Ingested Sources'}
        </span>
        <div className="topbar-divider"></div>
        <nav className="topbar-nav-links">
          <a href="#" className="nav-link">Overview</a>
          <a href="#" className="nav-link">Docs</a>
          <a href="#" className="nav-link">Supabase DB</a>
          <a href="#" className="nav-link">API Reference</a>
          <span className="free-plan-badge bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block mr-1"></span>
            Supabase Connected
          </span>
        </nav>
      </div>

      <div className="topbar-right">
        {/* Dark / Light Mode Toggle Button */}
        <button className="icon-circle-btn" title="Toggle Theme">
          <Moon size={15} />
        </button>

        {/* User Profile Pill */}
        <div className="user-profile-pill">
          <div className="avatar-circle bg-indigo-600 text-white font-semibold">ZR</div>
          <span className="username-text font-medium text-gray-800">Zyme Admin</span>
        </div>
      </div>
    </header>
  );
}
