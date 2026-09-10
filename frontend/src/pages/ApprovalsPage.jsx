import React, { useState, useEffect, useCallback } from 'react';

const API = 'http://localhost:8000';
function getToken() { return localStorage.getItem('zymerag_token') || ''; }
const headers = () => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` });

function riskLevel(args) {
  if (!args) return 'LOW';
  const amount = args.amount ?? args.value ?? 0;
  if (amount > 50000) return 'CRITICAL';
  if (amount > 10000) return 'HIGH';
  if (amount > 1000) return 'MEDIUM';
  return 'LOW';
}

function argDisplay(args) {
  if (!args) return '—';
  return Object.entries(args).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join('\n');
}

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ pending: 0, approved_today: 0, rejected_today: 0 });
  const [alert, setAlert] = useState(null);
  const [acting, setActing] = useState({});
  const [reason, setReason] = useState({});

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/actions/approvals`, { headers: headers() });
      if (r.ok) {
        const d = await r.json();
        const list = d.approvals || d || [];
        setApprovals(list);
        const today = new Date().toDateString();
        setStats({
          pending: list.filter(a => a.status === 'PENDING').length,
          approved_today: list.filter(a => a.status === 'APPROVED' && new Date(a.decided_at || a.created_at).toDateString() === today).length,
          rejected_today: list.filter(a => a.status === 'REJECTED' && new Date(a.decided_at || a.created_at).toDateString() === today).length,
        });
      }
    } catch { setApprovals([]); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchApprovals(); }, [fetchApprovals]);

  const decide = async (approvalId, decision) => {
    setActing(a => ({ ...a, [approvalId]: decision }));
    try {
      const r = await fetch(`${API}/actions/approvals/${approvalId}/decision`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ decision, decided_by: localStorage.getItem('zymerag_user') || 'compliance_officer_1', reason: reason[approvalId] || null }),
      });
      const d = await r.json();
      if (r.ok) {
        setAlert({ type: 'success', msg: `Action ${decision.toLowerCase()} successfully.` });
        fetchApprovals();
      } else {
        setAlert({ type: 'error', msg: d.detail || 'Decision failed' });
      }
    } catch (e) { setAlert({ type: 'error', msg: e.message }); }
    setActing(a => { const n = { ...a }; delete n[approvalId]; return n; });
  };

  const pending = approvals.filter(a => a.status === 'PENDING');
  const resolved = approvals.filter(a => a.status !== 'PENDING');

  return (
    <div className="page">
      <div className="page-header">
        <h1>Approval Queue</h1>
        <p>Escalated agent actions waiting for human reviewer decision. Decisions re-validate against current live policy before execution.</p>
      </div>

      <div className="stat-row">
        <div className="stat-box"><div className="stat-label">Pending</div><div className="stat-value orange">{stats.pending}</div></div>
        <div className="stat-box"><div className="stat-label">Approved Today</div><div className="stat-value green">{stats.approved_today}</div></div>
        <div className="stat-box"><div className="stat-label">Rejected Today</div><div className="stat-value red">{stats.rejected_today}</div></div>
      </div>

      {alert && (
        <div className={`alert alert-${alert.type}`}>
          {alert.msg}
          <button onClick={() => setAlert(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}>×</button>
        </div>
      )}

      {loading ? (
        <div className="loading-row"><div className="spinner" /><span>Loading approval queue…</span></div>
      ) : (
        <>
          <div className="section-heading">Pending Actions ({pending.length})</div>
          {pending.length === 0 ? (
            <div className="empty-state" style={{ border: '1px solid var(--d-gray-200)', background: 'var(--d-white)' }}>
              <div className="icon">✅</div><p>No pending approvals</p>
            </div>
          ) : pending.map(ap => {
            const payload = typeof ap.action_payload === 'string' ? JSON.parse(ap.action_payload) : ap.action_payload || {};
            const risk = riskLevel(payload.arguments);
            return (
              <div key={ap.approval_id} className="approval-card">
                <div>
                  <div className="ac-label">Agent</div>
                  <div className="ac-value">{payload.agent_id || ap.agent_id || '—'}</div>
                  <div className="ac-sub">Requested At</div>
                  <div style={{ fontSize: 12, color: 'var(--d-gray-500)' }}>{new Date(ap.created_at).toLocaleString()}</div>
                </div>

                <div>
                  <div className="ac-label">Operation Requested</div>
                  <div className="ac-value" style={{ fontSize: 15 }}>{(payload.operation || ap.operation || '—').toUpperCase()}</div>
                  <div className="ac-sub" style={{ marginBottom: 8 }}>Tool: {payload.tool || ap.tool || '—'}</div>
                  <div className="ac-label">Argument Details</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--d-gray-700)', whiteSpace: 'pre-line' }}>
                    {argDisplay(payload.arguments)}
                  </div>
                  {ap.source_clause && (
                    <><div className="ac-label" style={{ marginTop: 10 }}>Matched Policy Clause</div>
                    <div style={{ fontSize: 12, color: 'var(--d-gray-500)', fontStyle: 'italic' }}>{ap.source_clause}</div></>
                  )}
                  <div style={{ marginTop: 10 }}>
                    <label style={{ display: 'block', fontSize: 11, color: 'var(--d-gray-400)', marginBottom: 4 }}>Reviewer Note (optional)</label>
                    <input type="text" style={{ width: '100%' }} placeholder="Reason for decision…" value={reason[ap.approval_id] || ''} onChange={e => setReason(r => ({ ...r, [ap.approval_id]: e.target.value }))} />
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 10 }}>
                  <div>
                    <div className="ac-label" style={{ textAlign: 'right' }}>Risk Level</div>
                    <div className={`risk-${risk}`} style={{ textAlign: 'right' }}>{risk}</div>
                  </div>
                  <button className="btn btn-primary" onClick={() => decide(ap.approval_id, 'APPROVED')} disabled={!!acting[ap.approval_id]}>
                    {acting[ap.approval_id] === 'APPROVED' ? 'Processing…' : 'Approve'}
                  </button>
                  <button className="btn btn-danger" onClick={() => decide(ap.approval_id, 'REJECTED')} disabled={!!acting[ap.approval_id]}>
                    {acting[ap.approval_id] === 'REJECTED' ? 'Processing…' : 'Reject'}
                  </button>
                </div>
              </div>
            );
          })}

          {resolved.length > 0 && (
            <>
              <div className="section-heading" style={{ marginTop: 28 }}>Recent Decisions ({resolved.length})</div>
              <div className="card" style={{ padding: 0 }}>
                <div className="table-wrap">
                  <table>
                    <thead><tr>
                      <th>Approval ID</th><th>Agent</th><th>Operation</th><th>Status</th><th>Decided By</th><th>Decided At</th>
                    </tr></thead>
                    <tbody>
                      {resolved.slice(0, 20).map(ap => {
                        const payload = typeof ap.action_payload === 'string' ? JSON.parse(ap.action_payload) : ap.action_payload || {};
                        return (
                          <tr key={ap.approval_id}>
                            <td className="mono">{ap.approval_id?.slice(0, 12)}…</td>
                            <td>{payload.agent_id || '—'}</td>
                            <td style={{ fontWeight: 600 }}>{(payload.operation || '—').toUpperCase()}</td>
                            <td><span className={`badge badge-${ap.status.toLowerCase()}`}>{ap.status}</span></td>
                            <td>{ap.decided_by || '—'}</td>
                            <td>{ap.decided_at ? new Date(ap.decided_at).toLocaleString() : '—'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
