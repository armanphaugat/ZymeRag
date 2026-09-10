import React, { useState, useEffect, useCallback } from 'react';

const API = 'http://localhost:8000';
function getToken() { return localStorage.getItem('zymerag_token') || ''; }
const headers = () => ({ Authorization: `Bearer ${getToken()}` });

function DecisionBadge({ d }) {
  let cls = 'badge-draft';
  if (d === 'ALLOW' || d === 'APPROVED' || d === 'RULE_APPROVED' || d === 'EXECUTED') cls = 'badge-allow';
  else if (d === 'BLOCK' || d === 'REJECTED' || d === 'RULE_REJECTED' || d === 'EXECUTION_FAILED') cls = 'badge-block';
  else if (d === 'ESCALATE') cls = 'badge-escalate';
  return <span className={`badge ${cls}`}>{d}</span>;
}

export default function AuditPage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [integrity, setIntegrity] = useState(null);
  const [filter, setFilter] = useState('');
  const [limit, setLimit] = useState(50);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [stats, setStats] = useState({ allow: 0, block: 0, escalate: 0, approved: 0, total: 0 });

  const fetchAudit = useCallback(async () => {
    setLoading(true);
    try {
      let url = `${API}/actions/audit?limit=${limit}`;
      const r = await fetch(url, { headers: headers() });
      if (r.ok) {
        const d = await r.json();
        const list = d.events || d || [];
        setEvents(list);
        setStats({
          total: list.length,
          allow: list.filter(e => e.decision === 'ALLOW' || e.decision === 'EXECUTED').length,
          block: list.filter(e => e.decision === 'BLOCK' || e.decision === 'REJECTED').length,
          escalate: list.filter(e => e.decision === 'ESCALATE').length,
          approved: list.filter(e => e.decision === 'APPROVED' || e.decision === 'RULE_APPROVED').length,
        });
      }
    } catch { setEvents([]); }
    setLoading(false);
  }, [limit]);

  const verifyIntegrity = useCallback(async () => {
    try {
      const r = await fetch(`${API}/actions/audit/verify`, { headers: headers() });
      if (r.ok) { const d = await r.json(); setIntegrity(d); }
    } catch {}
  }, []);

  useEffect(() => { fetchAudit(); }, [fetchAudit]);

  const filtered = filter
    ? events.filter(e =>
        e.decision === filter ||
        (e.tool || '').toLowerCase().includes(filter.toLowerCase()) ||
        (e.operation || '').toLowerCase().includes(filter.toLowerCase()) ||
        (e.agent_id || '').toLowerCase().includes(filter.toLowerCase()) ||
        (e.user_id || '').toLowerCase().includes(filter.toLowerCase())
      )
    : events;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Audit Logs</h1>
        <p>Immutable, SHA-256 hash-chained record of every gateway decision and human approval. Tamper-evident by design.</p>
      </div>

      <div className="stat-row">
        <div className="stat-box"><div className="stat-label">Total Events</div><div className="stat-value">{stats.total}</div></div>
        <div className="stat-box"><div className="stat-label">Allowed / Executed</div><div className="stat-value green">{stats.allow}</div></div>
        <div className="stat-box"><div className="stat-label">Blocked / Rejected</div><div className="stat-value red">{stats.block}</div></div>
        <div className="stat-box"><div className="stat-label">Escalated</div><div className="stat-value orange">{stats.escalate}</div></div>
        <div className="stat-box"><div className="stat-label">Human Approvals</div><div className="stat-value green">{stats.approved}</div></div>
      </div>

      {integrity && (
        <div className={`alert alert-${integrity.is_valid ? 'success' : 'error'}`}>
          Chain integrity: <strong>{integrity.status}</strong>
          {!integrity.is_valid && ` — Issues: ${(integrity.chain_issues || []).join(', ')}`}
          <button onClick={() => setIntegrity(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}>×</button>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="card-title">Event Log & Provenance</span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button className="btn btn-outline btn-sm" onClick={verifyIntegrity}>Verify Chain Integrity</button>
            <button className="btn btn-outline btn-sm" onClick={fetchAudit}>Refresh</button>
          </div>
        </div>

        <div className="filter-bar">
          <div className="form-group">
            <label>Search</label>
            <input type="text" style={{ width: 220 }} placeholder="Decision, actor, agent, tool…" value={filter} onChange={e => setFilter(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Decision Type</label>
            <select style={{ width: 160 }} value={filter} onChange={e => setFilter(e.target.value)}>
              <option value="">All Decisions</option>
              <option value="ALLOW">Allow</option>
              <option value="BLOCK">Block</option>
              <option value="ESCALATE">Escalate</option>
              <option value="APPROVED">Human Approved</option>
              <option value="REJECTED">Human Rejected</option>
              <option value="RULE_APPROVED">Rule Approved</option>
            </select>
          </div>
          <div className="form-group">
            <label>Limit</label>
            <select style={{ width: 100 }} value={limit} onChange={e => { setLimit(Number(e.target.value)); }}>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="loading-row"><div className="spinner" /><span>Loading audit events…</span></div>
        ) : filtered.length === 0 ? (
          <div className="empty-state"><div className="icon">🔍</div><p>No audit events found</p></div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action ID</th>
                  <th>Actor / Decided By</th>
                  <th>Agent ID</th>
                  <th>Operation</th>
                  <th>Decision</th>
                  <th>Matched Rule</th>
                  <th>SHA-256 Hash</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((ev, i) => {
                  const details = typeof ev.details === 'string' ? JSON.parse(ev.details || '{}') : ev.details || {};
                  const actor = details.decided_by || details.approved_by || ev.user_id || 'System';
                  const isHuman = !!(details.decided_by || details.approved_by || (ev.user_id && !ev.user_id.startsWith('agent_')));
                  const clause = details.source_clause || ev.source_clause || details.reason || '—';
                  const ruleId = ev.matched_rule_id || details.matched_rule_id;

                  return (
                    <tr key={ev.event_id || i} onClick={() => setSelectedEvent(ev)} style={{ cursor: 'pointer' }}>
                      <td className="mono" style={{ whiteSpace: 'nowrap', fontSize: 12 }}>
                        {ev.created_at ? new Date(ev.created_at).toLocaleString('en-GB', { hour12: false }).replace(',', '') : '—'}
                      </td>
                      <td className="mono" style={{ fontSize: 11 }}>{(ev.action_id || '—').slice(0, 12)}…</td>
                      <td>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          fontWeight: isHuman ? 700 : 400,
                          color: isHuman ? 'var(--d-navy)' : 'var(--d-gray-400)',
                          fontSize: 12
                        }}>
                          {isHuman && <span style={{ width: 6, height: 6, background: 'var(--d-green)', borderRadius: 0 }} />}
                          {actor}
                        </span>
                      </td>
                      <td style={{ fontWeight: 500, fontSize: 12 }}>{ev.agent_id || '—'}</td>
                      <td style={{ fontWeight: 600, textTransform: 'uppercase', whiteSpace: 'nowrap', fontSize: 12 }}>
                        {ev.tool ? `${ev.tool}:` : ''}{ev.operation || '—'}
                      </td>
                      <td><DecisionBadge d={ev.decision} /></td>
                      <td style={{ maxWidth: 160 }}>
                        {ruleId ? (
                          <span title={clause} className="mono" style={{ fontSize: 11 }}>{ruleId.slice(0, 10)}…</span>
                        ) : <span style={{ color: 'var(--d-gray-400)', fontSize: 12 }}>—</span>}
                      </td>
                      <td className="mono" style={{ color: 'var(--d-gray-400)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11 }}>
                        {ev.curr_hash ? ev.curr_hash.slice(0, 14) + '…' : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ marginTop: 10, fontSize: 12, color: 'var(--d-gray-400)', textAlign: 'right' }}>
          Showing {filtered.length} of {events.length} events (Click any row for raw event details)
        </div>
      </div>

      {selectedEvent && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 43, 73, 0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }} onClick={() => setSelectedEvent(null)}>
          <div style={{
            background: 'var(--d-white)', width: 680, maxHeight: '80vh', overflowY: 'auto',
            padding: 28, border: '2px solid var(--d-navy)'
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, borderBottom: '1px solid var(--d-gray-200)', paddingBottom: 12 }}>
              <h3 style={{ margin: 0, color: 'var(--d-navy)', fontSize: 16 }}>Audit Event Details</h3>
              <button className="btn btn-outline btn-sm" onClick={() => setSelectedEvent(null)}>Close</button>
            </div>
            <pre style={{
              background: 'var(--d-gray-100)', padding: 16, fontSize: 12, lineHeight: 1.5,
              fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all'
            }}>
              {JSON.stringify(selectedEvent, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
