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
  const [isStale, setIsStale] = useState(false);

  // Authoritative fetch from server (initial load and manual refresh)
  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/rules`, { headers: headers() });
      if (r.ok) {
        const d = await r.json();
        const all = d.rules || d || [];
        setRules(all);
        setStats({
          draft: all.filter(r => r.status === 'DRAFT').length,
          approved: all.filter(r => r.status === 'APPROVED').length,
          rejected: all.filter(r => r.status === 'REJECTED').length,
        });
        setIsStale(false);
      }
    } catch {
      setRules([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  const act = async (ruleId, action) => {
    const targetRule = rules.find(r => r.rule_id === ruleId);
    if (!targetRule) return;

    // Snapshot for rollback on failure
    const prevRules = rules;
    const prevStats = stats;
    const prevStale = isStale;

    const newStatus = action === 'approve' ? 'APPROVED' : 'REJECTED';
    const oldStatusKey = targetRule.status ? targetRule.status.toLowerCase() : 'draft';
    const newStatusKey = action === 'approve' ? 'approved' : 'rejected';
    const approver = localStorage.getItem('zymerag_user') || 'compliance_officer_1';

    // 1. Optimistically update rules list
    setRules(prev => prev.map(r => r.rule_id === ruleId ? { ...r, status: newStatus, approved_by: approver } : r));

    // 2. Optimistically update local counters (mark as approximate/stale until refreshed)
    setStats(prev => ({
      ...prev,
      [oldStatusKey]: Math.max(0, (prev[oldStatusKey] ?? 1) - 1),
      [newStatusKey]: (prev[newStatusKey] ?? 0) + 1,
    }));
    setIsStale(true);

    // 3. Mark rule-level acting state (action-level spinner/disable on button only)
    setActing(a => ({ ...a, [ruleId]: action }));

    try {
      const endpoint = `${API}/rules/${ruleId}/${action}`;
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ approved_by: approver }),
      });

      if (r.ok) {
        setAlert({ type: 'success', msg: `Rule ${ruleId.slice(0, 8)}… ${action}d successfully.` });
      } else {
        const d = await r.json().catch(() => ({}));
        // Rollback state on API failure
        setRules(prevRules);
        setStats(prevStats);
        setIsStale(prevStale);
        setAlert({ type: 'error', msg: d.detail || `Failed to ${action} rule` });
      }
    } catch (e) {
      // Rollback state on network/exception failure
      setRules(prevRules);
      setStats(prevStats);
      setIsStale(prevStale);
      setAlert({ type: 'error', msg: e.message || `Failed to ${action} rule` });
    } finally {
      setActing(a => { const n = { ...a }; delete n[ruleId]; return n; });
    }
  };

  const displayedRules = filter ? rules.filter(r => r.status === filter) : rules;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Rule Review</h1>
        <p>Review LLM-extracted policy rules. Approve to activate in the enforcement gateway, or reject to discard.</p>
      </div>

      <div className="stat-row">
        <div className="stat-box">
          <div className="stat-label">
            Draft (Pending Review) {isStale && <span style={{ fontSize: 11, color: 'var(--d-gray-400)', fontWeight: 'normal' }}>(approx)</span>}
          </div>
          <div className="stat-value" style={{ color: 'var(--draft)' }}>
            {isStale && stats.draft !== null ? `~${stats.draft}` : (stats.draft ?? '—')}
          </div>
        </div>
        <div className="stat-box">
          <div className="stat-label">
            Approved (Active) {isStale && <span style={{ fontSize: 11, color: 'var(--d-gray-400)', fontWeight: 'normal' }}>(approx)</span>}
          </div>
          <div className="stat-value green">
            {isStale && stats.approved !== null ? `~${stats.approved}` : (stats.approved ?? '—')}
          </div>
        </div>
        <div className="stat-box">
          <div className="stat-label">
            Rejected {isStale && <span style={{ fontSize: 11, color: 'var(--d-gray-400)', fontWeight: 'normal' }}>(approx)</span>}
          </div>
          <div className="stat-value red">
            {isStale && stats.rejected !== null ? `~${stats.rejected}` : (stats.rejected ?? '—')}
          </div>
        </div>
      </div>

      {alert && (
        <div className={`alert alert-${alert.type}`}>
          {alert.msg}
          <button onClick={() => setAlert(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}>×</button>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="card-title">Policy Rules</span>
            <button 
              className="btn btn-outline btn-sm" 
              onClick={loadRules} 
              disabled={loading}
              title="Sync authoritative rules & counts from database"
            >
              ↻ Refresh
            </button>
          </div>
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
        ) : displayedRules.length === 0 ? (
          <div className="empty-state"><div className="icon">📋</div><p>No {filter || ''} rules found. Upload a policy document to start extraction.</p></div>
        ) : (
          displayedRules.map(rule => {
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
