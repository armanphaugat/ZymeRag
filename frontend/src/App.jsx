import React, { useState } from 'react';
import Header from './components/Header';
import UploadContent from './components/UploadContent';
import IngestedSources from './components/IngestedSources';

export default function App() {
  const [activeTab, setActiveTab] = useState('upload');

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Top Header Navbar */}
      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Workspace Body */}
      <main className="max-w-6xl mx-auto px-6 py-6">
        {activeTab === 'upload' ? (
          <UploadContent onUploadSuccess={() => setActiveTab('sources')} />
        ) : (
          <IngestedSources onNavigateToAdd={() => setActiveTab('upload')} />
        )}
      </main>
    </div>
  );
}