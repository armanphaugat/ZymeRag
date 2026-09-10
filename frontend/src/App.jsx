import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar.jsx';
import IngestionPage from './pages/IngestionPage.jsx';
import RuleReviewPage from './pages/RuleReviewPage.jsx';
import ApprovalsPage from './pages/ApprovalsPage.jsx';
import AuditPage from './pages/AuditPage.jsx';
import './index.css';

const PAGE_TITLES = {
  ingestion: 'Policy Ingestion',
  'rule-review': 'Rule Review',
  approvals: 'Approval Queue',
  audit: 'Audit Logs',
};

const API = 'http://localhost:8000';

function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const login = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const r = await fetch(`${API}/user/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const d = await r.json();
      if (r.ok && (d.access_token || d.token)) {
        const tok = d.access_token || d.token;
        localStorage.setItem('zymerag_token', tok);
        localStorage.setItem('zymerag_user', username);
        onLogin(username);
      } else {
        setError(d.detail || 'Invalid credentials');
      }
    } catch (e) { setError(`Cannot reach server: ${e.message}`); }
    setLoading(false);
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--d-navy)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'var(--d-white)', width: 380, padding: '40px 36px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 32 }}>
          <div style={{ width: 40, height: 40, background: 'var(--d-green)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 16, color: 'var(--d-navy)' }}>D</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--d-navy)' }}>ZymeRag</div>
            <div style={{ fontSize: 11, color: 'var(--d-gray-400)', textTransform: 'uppercase', letterSpacing: 1 }}>Policy Gateway</div>
          </div>
        </div>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--d-navy)', marginBottom: 6 }}>Sign In</h2>
        <p style={{ fontSize: 13, color: 'var(--d-gray-400)', marginBottom: 24 }}>Compliance Officer Portal</p>
        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
        <form onSubmit={login}>
          <div className="form-group">
            <label>Username</label>
            <input type="text" value={username} onChange={e => setUsername(e.target.value)} placeholder="compliance_officer_1" autoFocus />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••••" />
          </div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '10px' }} disabled={loading}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
        <p style={{ marginTop: 16, fontSize: 12, color: 'var(--d-gray-400)', textAlign: 'center' }}>
          No account? Token can also be set manually in localStorage as <code>zymerag_token</code>
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState('ingestion');
  const [user, setUser] = useState(() => localStorage.getItem('zymerag_user'));
  const [apiOk, setApiOk] = useState(null);

  useEffect(() => {
    fetch(`${API}/health`).then(r => setApiOk(r.ok)).catch(() => setApiOk(false));
  }, []);

  if (!user) return <LoginScreen onLogin={u => setUser(u)} />;

  const logout = () => { localStorage.removeItem('zymerag_token'); localStorage.removeItem('zymerag_user'); setUser(null); };

  return (
    <div className="layout">
      <Sidebar active={page} onNav={setPage} />
      <div className="main">
        <div className="topbar">
          <span className="topbar-title">{PAGE_TITLES[page]}</span>
          <div className="topbar-right">
            {apiOk === false && <span style={{ fontSize: 12, color: 'var(--block)', fontWeight: 600 }}>⚠ API Unreachable</span>}
            {apiOk === true && <span style={{ fontSize: 12, color: 'var(--allow)', fontWeight: 600 }}>● API Connected</span>}
            <span className="topbar-user">{user}</span>
            <button className="btn btn-outline btn-sm" onClick={logout}>Logout</button>
          </div>
        </div>
        {page === 'ingestion' && <IngestionPage />}
        {page === 'rule-review' && <RuleReviewPage />}
        {page === 'approvals' && <ApprovalsPage />}
        {page === 'audit' && <AuditPage />}
      </div>
    </div>
  );
}
