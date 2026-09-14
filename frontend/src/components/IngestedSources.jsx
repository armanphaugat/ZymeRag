import React, { useState } from 'react';
import { Search, Plus, ExternalLink, Info, Trash2, AlertCircle } from 'lucide-react';
import SourceMetadataModal from './SourceMetadataModal';
import DeleteConfirmModal from './DeleteConfirmModal';

export default function IngestedSources({ onNavigateToAdd }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSource, setSelectedSource] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Vector sources in ZymeRag Supabase database
  const [sources, setSources] = useState([
    { 
      id: '2cc26028-f178-4585-9716-b9c919325d74', 
      name: 'ZymeRag Multimodal Architecture Whitepaper.pdf', 
      type: 'Pdf', 
      status: 'Ingested', 
      chunks: 42,
      url: 'https://arxiv.org/pdf/2312.10997.pdf' 
    },
    { 
      id: '34a819b2-10cf-41a2-8902-881ab71029c1', 
      name: 'https://docs.zymerag.io/api/v1/endpoints', 
      type: 'Url', 
      status: 'Ingested', 
      chunks: 18,
      url: 'https://github.com/armanphaugat/ZymeRag'
    },
    { 
      id: '401b9201-3829-43c9-901e-7bba12984620', 
      name: 'Supabase Vector Indexing Guide.docx', 
      type: 'Docx', 
      status: 'Ingested', 
      chunks: 29,
      url: 'https://supabase.com/docs/guides/ai'
    },
    { 
      id: '5561a09e-711e-4509-b682-124619cd01a2', 
      name: 'https://github.com/armanphaugat/ZymeRag/README.md', 
      type: 'Url', 
      status: 'Ingested', 
      chunks: 14,
      url: 'https://github.com/armanphaugat/ZymeRag'
    },
    { 
      id: '61a20b55-8d21-49b9-81a1-9a716c0291ba', 
      name: 'Multimodal Image Diagram v2.png', 
      type: 'Image', 
      status: 'Ingested', 
      chunks: 5,
      url: 'https://raw.githubusercontent.com/armanphaugat/ZymeRag/main/README.md'
    },
    { 
      id: '7100b41c-a991-4c12-b01a-cc91823901b2', 
      name: 'Executive Audio Summary Q3.mp3', 
      type: 'Audio', 
      status: 'Ingested', 
      chunks: 36,
      url: 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf'
    },
    { 
      id: '89100a91-bc10-410a-912a-091a02930920', 
      name: 'Financial Operations Report 2026.pdf', 
      type: 'Pdf', 
      status: 'Ingested', 
      chunks: 88,
      url: 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf'
    },
    { 
      id: '9180ab21-00aa-4509-b001-aa1102940291', 
      name: 'Server FAQ & Guidelines 2026.docx', 
      type: 'Docx', 
      status: 'Ingested', 
      chunks: 12,
      url: 'https://github.com/armanphaugat/ZymeRag'
    }
  ]);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);

    try {
      const formData = new FormData();
      formData.append('id', deleteTarget.id);
      await fetch('http://localhost:8000/delete/delete_content', {
        method: 'DELETE',
        body: formData
      });
      setSources(prev => prev.filter(s => s.id !== deleteTarget.id));
    } catch (err) {
      setSources(prev => prev.filter(s => s.id !== deleteTarget.id));
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  const filteredSources = sources.filter(s => 
    s.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getTargetUrl = (item) => {
    if (item.url) return item.url;
    if (item.name.startsWith('http://') || item.name.startsWith('https://')) return item.name;
    return 'https://github.com/armanphaugat/ZymeRag';
  };

  return (
    <div className="workspace-container">
      {/* Workspace Header */}
      <div className="workspace-header">
        <div>
          <div className="title-row">
            <h1 className="workspace-title">Ingested Sources</h1>
            <span className="count-badge-pill">{sources.length}</span>
          </div>
          <p className="workspace-subtitle">
            Search, inspect, and manage vector embeddings stored in Supabase pgvector
          </p>
        </div>

        <button className="primary-action-btn" onClick={onNavigateToAdd}>
          <Plus size={16} />
          <span>Ingest New Data</span>
        </button>
      </div>

      {/* Search Bar Row */}
      <div className="search-row">
        <div className="search-bar-box">
          <Search size={16} className="search-icon-svg" />
          <input 
            type="text" 
            placeholder="Search ingested files, URLs, or document names..." 
            className="search-input-field"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search-btn" onClick={() => setSearchQuery('')}>
              &times;
            </button>
          )}
        </div>
      </div>

      {/* Sources Data Table */}
      <div className="custom-table-card">
        <table className="custom-data-table">
          <thead>
            <tr>
              <th>Source Name</th>
              <th>Type</th>
              <th>Vector Chunks</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredSources.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty-table-cell">
                  <AlertCircle size={20} className="mx-auto mb-2 text-gray-400" />
                  No ingested sources found matching "{searchQuery}".
                </td>
              </tr>
            ) : (
              filteredSources.map((item) => {
                const targetUrl = getTargetUrl(item);
                return (
                  <tr key={item.id} className="table-row-item">
                    <td>
                      <div className="source-title-cell">
                        <span className="source-title-text">{item.name}</span>
                        <a 
                          href={targetUrl} 
                          target="_blank"
                          rel="noopener noreferrer"
                          className="link-external-icon"
                          title={`Open ${item.name} in new tab`}
                        >
                          <ExternalLink size={13} />
                        </a>
                      </div>
                    </td>
                    <td>
                      <span className={`type-tag type-${item.type.toLowerCase()}`}>
                        {item.type}
                      </span>
                    </td>
                    <td>
                      <span className="chunks-badge">{item.chunks} chunks</span>
                    </td>
                    <td>
                      <span className="status-badge-ingested">
                        <span className="pulse-dot-green"></span>
                        Ingested
                      </span>
                    </td>
                    <td>
                      <div className="table-actions-cell">
                        {/* High-End Inspect Button */}
                        <button 
                          className="action-pill-btn inspect-pill" 
                          title="Inspect Metadata"
                          onClick={() => setSelectedSource(item)}
                        >
                          <Info size={13} />
                          <span>Inspect</span>
                        </button>

                        {/* High-End Delete Button */}
                        <button 
                          className="action-pill-btn delete-pill" 
                          title="Delete Source"
                          onClick={() => setDeleteTarget(item)}
                        >
                          <Trash2 size={13} />
                          <span>Delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Metadata Inspector Modal */}
      {selectedSource && (
        <SourceMetadataModal 
          source={selectedSource} 
          onClose={() => setSelectedSource(null)} 
        />
      )}

      {/* Delete Warning Confirmation Modal */}
      {deleteTarget && (
        <DeleteConfirmModal 
          sourceName={deleteTarget.name}
          onConfirm={confirmDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={isDeleting}
        />
      )}
    </div>
  );
}
