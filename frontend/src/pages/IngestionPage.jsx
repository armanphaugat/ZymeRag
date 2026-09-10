import React, { useState, useRef, useCallback, useEffect } from 'react';

const API = 'http://localhost:8000';

function getToken() { return localStorage.getItem('zymerag_token') || ''; }

export default function IngestionPage() {
  const [file, setFile] = useState(null);
  const [name, setName] = useState('');
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [alert, setAlert] = useState(null);
  const [docs, setDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const fileRef = useRef();

  const fetchDocs = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const r = await fetch(`${API}/upload/documents`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (r.ok) { const d = await r.json(); setDocs(d.documents || d || []); }
    } catch { setDocs([]); }
    setLoadingDocs(false);
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer?.files?.[0] || e.target.files?.[0];
    if (f) { setFile(f); setName(f.name.replace(/\.[^.]+$/, '')); }
  }, []);

  const upload = async () => {
    if (!file) return;
    setUploading(true); setProgress(10); setAlert(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('name', name || file.name);
      setProgress(40);
      const r = await fetch(`${API}/upload/pdf`, {
        method: 'POST', body: fd,
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      setProgress(90);
      const d = await r.json();
      if (r.ok) {
        setAlert({ type: 'success', msg: `Document "${name}" ingested. ID: ${d.id || d.content_id || '—'}. Rule extraction running in background.` });
        setFile(null); setName('');
        fetchDocs();
      } else {
        setAlert({ type: 'error', msg: d.detail || 'Upload failed' });
      }
    } catch (e) {
      setAlert({ type: 'error', msg: `Network error: ${e.message}` });
    }
    setProgress(100);
    setTimeout(() => { setUploading(false); setProgress(0); }, 600);
  };

  const deleteDoc = async (id) => {
    if (!window.confirm('Delete this document and all its extracted rules?')) return;
    try {
      await fetch(`${API}/delete/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      fetchDocs();
    } catch {}
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Policy Ingestion</h1>
        <p>Upload policy documents. Text is extracted, chunked, embedded, and rule extraction runs offline.</p>
      </div>

      {alert && (
        <div className={`alert alert-${alert.type}`}>
          {alert.msg}
          <button onClick={() => setAlert(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}>×</button>
        </div>
      )}

      <div className="card">
        <div className="card-header"><span className="card-title">Upload Policy Document</span></div>

        <div
          className={`upload-zone${drag ? ' drag-over' : ''}`}
          onClick={() => fileRef.current.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <div className="icon">📄</div>
          {file ? (
            <><strong>{file.name}</strong><p>{(file.size / 1024).toFixed(1)} KB</p></>
          ) : (
            <><strong>Drop PDF here or click to browse</strong><p>Supported: PDF, DOCX</p></>
          )}
          <input ref={fileRef} type="file" accept=".pdf,.docx" style={{ display: 'none' }} onChange={onDrop} />
        </div>

        {uploading && <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>}

        <div style={{ display: 'flex', gap: 12, marginTop: 16, alignItems: 'flex-end' }}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label>Document Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Northfield Refund Policy v2" />
          </div>
          <button className="btn btn-primary" onClick={upload} disabled={!file || uploading}>
            {uploading ? 'Uploading…' : 'Upload & Ingest'}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Ingested Documents</span>
          <button className="btn btn-outline btn-sm" onClick={fetchDocs}>Refresh</button>
        </div>

        {loadingDocs ? (
          <div className="loading-row"><div className="spinner" /><span>Loading documents…</span></div>
        ) : docs.length === 0 ? (
          <div className="empty-state"><div className="icon">📂</div><p>No documents ingested yet</p></div>
        ) : (
          docs.map((doc, i) => (
            <div key={doc.content_id || doc.id || i} className="doc-row">
              <span style={{ fontSize: 20 }}>📄</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, color: 'var(--d-navy)', fontSize: 13 }}>{doc.name}</div>
                <div className="text-mono">{doc.content_id || doc.id} · {doc.chunks || '?'} chunks · {doc.file_type || 'pdf'}</div>
              </div>
              <span style={{ fontSize: 11, color: 'var(--d-gray-400)' }}>{doc.inserted_at ? new Date(doc.inserted_at).toLocaleDateString() : '—'}</span>
              <button className="btn btn-danger btn-sm" onClick={() => deleteDoc(doc.content_id || doc.id)}>Delete</button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
