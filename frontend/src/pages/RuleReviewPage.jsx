import React, { useState, useEffect, useCallback } from 'react';

const API = 'http://localhost:8000';
function getToken() { return localStorage.getItem('zymerag_token') || ''; }
const headers = () => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` });

function EffectBadge({ e }) {
  const cls = e === 'ALLOW' ? 'badge-allow' : e === 'BLOCK' ? 'badge-block' : 'badge-escalate';
  return <span className={`badge ${cls}`}>{e}</span>;
}

function StatusBadge({ s }) {
  const cls = s === 'APPROVED' ? 'badge-approved' : s === 'REJECTED' ? 'badge-rejected' : 'badge-draft';
  return <span className={`badge ${cls}`}>{s}</span>;
}

export default function RuleReviewPage() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('DRAFT');
  const [alert, setAlert] = useState(null);
  const [acting, setActing] = useState({});
  const [stats, setStats] = useState({ draft: 0, approved: 0, rejected: 0 });

  const fetchRules = useCallback(async (status) => {
    setLoading(true);
    try {
      const url = status ? `${API}/rules?status=${status}` : `${API}/rules`;
      const r = await fetch(url, { headers: headers() });
      if (r.ok) {
        const d = await r.json();
        setRules(d.rules || d || []);
      }
    } catch { setRules([]); }
    setLoading(false);
  }, []);

  const fetchStats = useCallback(async () => {
    const statuses = ['DRAFT', 'APPROVED', 'REJECTED'];
    const counts = {};
    await Promise.all(statuses.map(async s => {
      try {
        const r = await fetch(`${API}/rules?status=${s}`, { headers: headers() });
        if (r.ok) { const d = await r.json(); counts[s.toLowerCase()] = (d.rules || d || []).length; }
      } catch { counts[s.toLowerCase()] = 0; }
    }));
    setStats(counts);
  }, []);

  useEffect(() => { fetchRules(filter); fetchStats(); }, [filter, fetchRules, fetchStats]);

  const act = async (ruleId, action) => {
    setActing(a => ({ ...a, [ruleId]: action }));
    try {
      const endpoint = `${API}/rules/${ruleId}/${action}`;
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ approved_by: localStorage.getItem('zymerag_user') || 'compliance_officer_1' }),
      });
      if (r.ok) {
        setAlert({ type: 'success', msg: `Rule ${ruleId.slice(0, 8)}… ${action}d successfully.` });
        fetchRules(filter); fetchStats();
      } else {
        const d = await r.json();
        setAlert({ type: 'error', msg: d.detail || `Failed to ${action} rule` });
      }
    } catch (e) { setAlert({ type: 'error', msg: e.message }); }
    setActing(a => { const n = { ...a }; delete n[ruleId]; return n; });
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Rule Review</h1>
        <p>Review LLM-extracted policy rules. Approve to activate in the enforcement gateway, or reject to discard.</p>
      </div>

      <div className="stat-row">
        <div className="stat-box"><div className="stat-label">Draft (Pending Review)</div><div className="stat-value" style={{ color: 'var(--draft)' }}>{stats.draft ?? '—'}</div></div>
        <div className="stat-box"><div className="stat-label">Approved (Active)</div><div className="stat-value green">{stats.approved ?? '—'}</div></div>
        <div className="stat-box"><div className="stat-label">Rejected</div><div className="stat-value red">{stats.rejected ?? '—'}</div></div>
      </div>

      {alert && (
        <div className={`alert alert-${alert.type}`}>
          {alert.msg}
          <button onClick={() => setAlert(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}>×</button>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="card-title">Policy Rules</span>
          <div style={{ display: 'flex', gap: 8 }}>
            {['DRAFT', 'APPROVED', 'REJECTED', ''].map(s => (
              <button key={s} className={`btn btn-sm ${filter === s ? 'btn-primary' : 'btn-outline'}`} onClick={() => setFilter(s)}>
                {s || 'All'}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="loading-row"><div className="spinner" /><span>Loading rules…</span></div>
        ) : rules.length === 0 ? (
          <div className="empty-state"><div className="icon">📋</div><p>No {filter || ''} rules found. Upload a policy document to start extraction.</p></div>
        ) : (
          rules.map(rule => {
            const scope = typeof rule.scope === 'string' ? JSON.parse(rule.scope) : rule.scope || {};
            const cond = typeof rule.condition === 'string' ? JSON.parse(rule.condition) : rule.condition || {};
            return (
              <div key={rule.rule_id} className="rule-card">
                <div className="rule-card-header">
                  <EffectBadge e={rule.effect} />
                  <StatusBadge s={rule.status} />
                  <span style={{ fontSize: 12, color: 'var(--d-gray-400)', fontFamily: 'var(--mono)' }}>{rule.rule_id?.slice(0, 12)}…</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--d-navy)' }}>
                    {scope.tool} › {scope.operation}
                  </span>
                </div>

                {rule.source_clause && (
                  <div className="rule-clause">"{rule.source_clause}"</div>
                )}

                <div className="rule-meta">
                  <div className="rule-meta-item"><strong>Condition:</strong>{cond.field} {cond.operator} {JSON.stringify(cond.value)}</div>
                  {rule.required_approval_role && <div className="rule-meta-item"><strong>Approver Role:</strong>{rule.required_approval_role}</div>}
                  {scope.flow_id && <div className="rule-meta-item"><strong>Flow:</strong>{scope.flow_id}</div>}
                  {rule.approved_by && <div className="rule-meta-item"><strong>Reviewed by:</strong>{rule.approved_by}</div>}
                </div>

                {rule.status === 'DRAFT' && (
                  <div className="btn-row" style={{ marginTop: 14 }}>
                    <button className="btn btn-primary" onClick={() => act(rule.rule_id, 'approve')} disabled={!!acting[rule.rule_id]}>
                      {acting[rule.rule_id] === 'approve' ? 'Approving…' : 'Approve'}
                    </button>
                    <button className="btn btn-danger" onClick={() => act(rule.rule_id, 'reject')} disabled={!!acting[rule.rule_id]}>
                      {acting[rule.rule_id] === 'reject' ? 'Rejecting…' : 'Reject'}
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
