import { useState, useRef, useEffect, useCallback } from "react";

/* ==========================================================================
   ZymeRag Developer Dashboard — single-file React port
   (Markup from index.html + styling from style.css + logic from app.js,
   all merged into one component.)
   ========================================================================== */

const ENDPOINTS = [
  { name: "PDF Document", route: "/upload/upload_pdf", icon: "📄" },
  { name: "DOCX Document", route: "/upload/upload_docx", icon: "📝" },
  { name: "Image File", route: "/upload/upload_image", icon: "🖼️" },
  { name: "CSV / Spreadsheet", route: "/upload/upload_csv", icon: "📊" },
  { name: "Audio File", route: "/upload/upload_audio", icon: "🎵" },
  { name: "Video File", route: "/upload/upload_video", icon: "🎬" },
];

const EXT_MAP = {
  pdf: "/upload/upload_pdf",
  docx: "/upload/upload_docx",
  png: "/upload/upload_image",
  jpg: "/upload/upload_image",
  jpeg: "/upload/upload_image",
  tiff: "/upload/upload_image",
  bmp: "/upload/upload_image",
  webp: "/upload/upload_image",
  csv: "/upload/upload_csv",
  xlsx: "/upload/upload_csv",
  xls: "/upload/upload_csv",
  mp3: "/upload/upload_audio",
  wav: "/upload/upload_audio",
  m4a: "/upload/upload_audio",
  mp4: "/upload/upload_video",
  m4v: "/upload/upload_video",
  mov: "/upload/upload_video",
};

function formatBytes(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function generateUUID() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function mapFileToEndpoint(file) {
  if (!file) return null;
  const ext = file.name.split(".").pop().toLowerCase();
  return EXT_MAP[ext] || "/upload/upload_pdf";
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[m]);
}

// Syntax-highlight a JSON-serializable value into safe HTML for display.
function syntaxHighlightJSON(value) {
  let json = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  json = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      let cls = "json-number";
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? "json-key" : "json-string";
      } else if (/true|false/.test(match)) {
        cls = "json-boolean";
      } else if (/null/.test(match)) {
        cls = "json-null";
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

const PLACEHOLDER_UPLOAD_JSON = "// Upload a document to view real-time API response payload...";
const PLACEHOLDER_DELETE_JSON = "// Execute a deletion request to view API results...";
const PLACEHOLDER_QUERY_JSON = "// Run a query to view the RAG response payload...";

export default function App() {
  /* ---------------- Global / connection state ---------------- */
  const [serverUrl, setServerUrl] = useState("http://localhost:8000");
  const [pingState, setPingState] = useState({ cls: "", text: "Check API" });

  const [activeTab, setActiveTab] = useState("uploadTab");

  const [totalIngestedCount, setTotalIngestedCount] = useState(0);
  const [totalSuccessCount, setTotalSuccessCount] = useState(0);
  const [totalRequests, setTotalRequests] = useState(0);
  const [totalLatencyMs, setTotalLatencyMs] = useState(0);

  const [toast, setToast] = useState({ visible: false, type: "info", message: "" });
  const toastTimer = useRef(null);

  /* ---------------- Upload tab state ---------------- */
  const [selectedEndpoint, setSelectedEndpoint] = useState("/upload/upload_pdf");
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [docName, setDocName] = useState("");
  const [idempotentKey, setIdempotentKey] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState({ cls: "status-idle", text: "Ready" });
  const [uploadTimeMs, setUploadTimeMs] = useState(null);
  const [uploadRawResponse, setUploadRawResponse] = useState(null);
  const [lastUploadedId, setLastUploadedId] = useState(null);
  const [sessionHistory, setSessionHistory] = useState([]);
  const fileInputRef = useRef(null);

  /* ---------------- Query tab state ---------------- */
  const [queryQuestion, setQueryQuestion] = useState("");
  const [queryIds, setQueryIds] = useState("");
  const [querying, setQuerying] = useState(false);
  const [queryStatus, setQueryStatus] = useState({ cls: "status-idle", text: "Ready" });
  const [queryTimeMs, setQueryTimeMs] = useState(null);
  const [queryRawResponse, setQueryRawResponse] = useState(null);

  /* ---------------- Delete tab state ---------------- */
  const [deleteId, setDeleteId] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteStatus, setDeleteStatus] = useState({ cls: "status-idle", text: "Ready" });
  const [deleteRawResponse, setDeleteRawResponse] = useState(null);

  /* ---------------- Logs tab state ---------------- */
  const [apiLogs, setApiLogs] = useState([]);
  const [logFilter, setLogFilter] = useState("");

  /* ---------------- Helpers ---------------- */
  const showToast = useCallback((message, type = "info") => {
    const icons = { info: "ℹ️", success: "✅", error: "❌", warning: "⚠️" };
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ visible: true, type, message, icon: icons[type] || "ℹ️" });
    toastTimer.current = setTimeout(() => setToast((t) => ({ ...t, visible: false })), 3500);
  }, []);

  const copyText = useCallback(
    (text) => {
      navigator.clipboard?.writeText(text).catch(() => {});
      showToast(`Copied: ${text}`, "info");
    },
    [showToast]
  );

  const updateMetrics = useCallback((success, duration) => {
    setTotalRequests((n) => n + 1);
    setTotalLatencyMs((n) => n + duration);
    if (success) setTotalSuccessCount((n) => n + 1);
  }, []);

  const addLogEntry = useCallback((method, endpoint, status, duration, response) => {
    setApiLogs((logs) => [
      {
        timestamp: new Date().toLocaleTimeString(),
        method,
        endpoint,
        status,
        duration: `${duration} ms`,
        response: JSON.stringify(response),
      },
      ...logs,
    ]);
  }, []);

  const totalRequestsRef = totalRequests;
  const successRate = totalRequestsRef > 0 ? Math.round((totalSuccessCount / totalRequestsRef) * 100) : 100;
  const avgLatency = totalRequestsRef > 0 ? Math.round(totalLatencyMs / totalRequestsRef) : 0;

  /* ---------------- Ping backend ---------------- */
  const pingBackend = useCallback(async () => {
    const baseUrl = serverUrl.replace(/\/$/, "");
    setPingState({ cls: "", text: "Pinging..." });
    try {
      const start = performance.now();
      const res = await fetch(`${baseUrl}/openapi.json`, { method: "GET" });
      const elapsed = Math.round(performance.now() - start);
      if (res.ok) {
        setPingState({ cls: "online", text: `Online (${elapsed}ms)` });
      } else {
        setPingState({ cls: "offline", text: `HTTP ${res.status}` });
      }
    } catch (err) {
      setPingState({ cls: "offline", text: "Offline" });
    }
  }, [serverUrl]);

  useEffect(() => {
    pingBackend();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---------------- File selection ---------------- */
  const handleFileSelection = useCallback(
    (file) => {
      if (!file) return;
      if (file.size > 10 * 1024 * 1024) {
        showToast("File exceeds maximum allowed limit of 10MB", "error");
        return;
      }
      setSelectedFile(file);
      const endpoint = mapFileToEndpoint(file);
      setSelectedEndpoint(endpoint);
      setDocName((prev) => {
        if (prev.trim()) return prev;
        const base = file.name.substring(0, file.name.lastIndexOf(".")) || file.name;
        return base;
      });
    },
    [showToast]
  );

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFileSelection(files[0]);
  };

  const removeFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  /* ---------------- Upload submit ---------------- */
  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    const baseUrl = serverUrl.replace(/\/$/, "");
    const name = docName.trim();
    const key = idempotentKey.trim();

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("name", name);
    if (key) formData.append("idempotent_key", key);

    setUploading(true);
    setUploadStatus({ cls: "status-idle", text: "Processing..." });

    const start = performance.now();
    let status = 0;
    let data = null;

    try {
      const res = await fetch(`${baseUrl}${selectedEndpoint}`, { method: "POST", body: formData });
      status = res.status;
      const duration = Math.round(performance.now() - start);
      setUploadTimeMs(duration);

      data = await res.json();
      setUploadRawResponse(data);

      if (res.ok) {
        setUploadStatus({ cls: "status-success", text: "200 OK" });
        showToast("Document ingested successfully!", "success");
        setTotalIngestedCount((n) => n + 1);
        if (data.id) {
          setLastUploadedId(data.id);
          setSessionHistory((h) => [
            { name, id: data.id, endpoint: selectedEndpoint, time: new Date().toLocaleTimeString() },
            ...h,
          ]);
        }
      } else {
        setUploadStatus({ cls: "status-error", text: `HTTP ${status}` });
        showToast(data.detail || "Ingestion failed", "error");
      }

      updateMetrics(res.ok, duration);
      addLogEntry("POST", selectedEndpoint, status, duration, data);
    } catch (err) {
      const duration = Math.round(performance.now() - start);
      setUploadStatus({ cls: "status-error", text: "Network Error" });
      setUploadRawResponse({ error: err.message });
      showToast(`Request failed: ${err.message}`, "error");
      addLogEntry("POST", selectedEndpoint, "FAIL", duration, { error: err.message });
    } finally {
      setUploading(false);
    }
  };

  /* ---------------- Query submit ---------------- */
  const handleQuerySubmit = async (e) => {
    e.preventDefault();
    const baseUrl = serverUrl.replace(/\/$/, "");
    const question = queryQuestion.trim();
    const ids = queryIds
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    if (!question || ids.length === 0) {
      showToast("Question and at least one Content ID are required", "error");
      return;
    }

    setQuerying(true);
    setQueryStatus({ cls: "status-idle", text: "Processing..." });

    const params = new URLSearchParams();
    params.append("question", question);
    ids.forEach((id) => params.append("ids", id));

    const start = performance.now();
    let status = 0;
    let data = null;

    try {
      const res = await fetch(`${baseUrl}/query/query?${params.toString()}`, { method: "GET" });
      status = res.status;
      const duration = Math.round(performance.now() - start);
      setQueryTimeMs(duration);

      data = await res.json();
      setQueryRawResponse(data);

      if (res.ok) {
        setQueryStatus({ cls: "status-success", text: "200 OK" });
        showToast("Query executed successfully!", "success");
      } else {
        setQueryStatus({ cls: "status-error", text: `HTTP ${status}` });
        showToast((data && data.detail) || "Query failed", "error");
      }

      updateMetrics(res.ok, duration);
      addLogEntry("GET", "/query/query", status, duration, data);
    } catch (err) {
      const duration = Math.round(performance.now() - start);
      setQueryStatus({ cls: "status-error", text: "Network Error" });
      setQueryRawResponse({ error: err.message });
      showToast(`Request failed: ${err.message}`, "error");
      addLogEntry("GET", "/query/query", "FAIL", duration, { error: err.message });
    } finally {
      setQuerying(false);
    }
  };

  /* ---------------- Delete submit ---------------- */
  const handleDeleteSubmit = async (e) => {
    e.preventDefault();
    const idToDelete = deleteId.trim();
    if (!idToDelete) return;

    const baseUrl = serverUrl.replace(/\/$/, "");
    setDeleting(true);

    const formData = new FormData();
    formData.append("id", idToDelete);

    const start = performance.now();

    try {
      const res = await fetch(`${baseUrl}/delete/delete_content`, { method: "DELETE", body: formData });
      const duration = Math.round(performance.now() - start);
      const data = await res.json();
      setDeleteRawResponse(data);

      if (res.ok) {
        setDeleteStatus({ cls: "status-success", text: "200 OK" });
        showToast("Content successfully deleted!", "success");
      } else {
        setDeleteStatus({ cls: "status-error", text: `HTTP ${res.status}` });
        showToast(data.detail || "Deletion failed", "error");
      }

      updateMetrics(res.ok, duration);
      addLogEntry("DELETE", "/delete/delete_content", res.status, duration, data);
    } catch (err) {
      setDeleteStatus({ cls: "status-error", text: "Error" });
      setDeleteRawResponse({ error: err.message });
      showToast(`Delete request failed: ${err.message}`, "error");
    } finally {
      setDeleting(false);
    }
  };

  const jumpToDeleteWithId = () => {
    if (lastUploadedId) {
      setDeleteId(lastUploadedId);
      setActiveTab("deleteTab");
    }
  };

  const filteredLogs = apiLogs.filter((log) => {
    const f = logFilter.toLowerCase().trim();
    if (!f) return true;
    return (
      log.endpoint.toLowerCase().includes(f) ||
      String(log.status).toLowerCase().includes(f) ||
      log.method.toLowerCase().includes(f)
    );
  });

  const detectedEndpointName =
    ENDPOINTS.find((ep) => ep.route === selectedEndpoint)?.name || "PDF Endpoint";

  const tabs = [
    { id: "uploadTab", label: "Document Ingestion" },
    { id: "queryTab", label: "Query Content" },
    { id: "deleteTab", label: "Delete Content" },
    { id: "logsTab", label: "API Activity Logs", counter: apiLogs.length },
  ];

  return (
    <div className="zymerag-root">
      <style>{CSS}</style>

      <div className="app-wrapper">
        <div className="ambient-glow glow-1"></div>
        <div className="ambient-glow glow-2"></div>

        {/* Header Navbar */}
        <header className="navbar">
          <div className="nav-brand">
            <div className="brand-logo">
              <span className="logo-spark">⚡</span>
            </div>
            <div className="brand-titles">
              <div className="brand-name">
                ZymeRag <span className="badge-version">v1.0</span>
              </div>
              <span className="brand-sub">Ingestion &amp; RAG API Test Suite</span>
            </div>
          </div>

          <div className="nav-actions">
            <div className="api-base-bar">
              <span className="server-label">Backend URL</span>
              <input
                type="text"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                placeholder="http://localhost:8000"
              />
              <button className="btn btn-glass btn-sm" title="Check Connection" onClick={pingBackend}>
                <span className={`pulse-dot ${pingState.cls}`}></span>
                <span>{pingState.text}</span>
              </button>
            </div>
            <a
              href={`${serverUrl.replace(/\/$/, "")}/docs`}
              target="_blank"
              rel="noreferrer"
              className="btn btn-outline btn-sm"
            >
              <span>Swagger API</span>
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                ></path>
              </svg>
            </a>
          </div>
        </header>

        {/* Metrics Bar */}
        <section className="analytics-bar">
          <div className="metric-card">
            <div className="metric-icon icon-purple">📥</div>
            <div className="metric-info">
              <span className="metric-label">Total Ingested</span>
              <span className="metric-value">{totalIngestedCount}</span>
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-icon icon-green">✅</div>
            <div className="metric-info">
              <span className="metric-label">Success Rate</span>
              <span className="metric-value">{successRate}%</span>
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-icon icon-blue">⚡</div>
            <div className="metric-info">
              <span className="metric-label">Avg Latency</span>
              <span className="metric-value">{avgLatency} ms</span>
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-icon icon-amber">🔌</div>
            <div className="metric-info">
              <span className="metric-label">Active Endpoints</span>
              <span className="metric-value">7 Routes</span>
            </div>
          </div>
        </section>

        {/* Tabs Nav */}
        <nav className="tabs-nav">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={`tab-btn ${activeTab === t.id ? "active" : ""}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
              {t.counter !== undefined && <span className="tab-counter">{t.counter}</span>}
            </button>
          ))}
        </nav>

        <main className="content-body">
          {/* TAB: UPLOAD */}
          <section className={`tab-content ${activeTab === "uploadTab" ? "active" : ""}`}>
            <div className="grid-container">
              <div className="panel main-panel">
                <div className="panel-header">
                  <div>
                    <h2>File Ingestion Console</h2>
                    <p className="panel-subtitle">
                      Upload files for document splitting, embedding generation, and vector database indexing.
                    </p>
                  </div>
                </div>

                <div className="endpoint-grid-title">Select Ingestion Endpoint</div>
                <div className="endpoint-grid">
                  {ENDPOINTS.map((ep) => (
                    <div
                      key={ep.route}
                      className={`endpoint-card ${selectedEndpoint === ep.route ? "active" : ""}`}
                      onClick={() => setSelectedEndpoint(ep.route)}
                    >
                      <div className="ep-icon">{ep.icon}</div>
                      <div className="ep-details">
                        <span className="ep-name">{ep.name}</span>
                        <span className="ep-route">{ep.route}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="dropzone-container">
                  <div
                    className={`dropzone ${dragOver ? "dragover" : ""}`}
                    onDragEnter={(e) => {
                      e.preventDefault();
                      setDragOver(true);
                    }}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragOver(true);
                    }}
                    onDragLeave={(e) => {
                      e.preventDefault();
                      setDragOver(false);
                    }}
                    onDrop={onDrop}
                  >
                    <input
                      type="file"
                      className="file-input"
                      ref={fileInputRef}
                      onChange={(e) => e.target.files.length > 0 && handleFileSelection(e.target.files[0])}
                    />
                    <div className="dropzone-body">
                      <div className="upload-cloud-icon">
                        <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="1.5"
                            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                          ></path>
                        </svg>
                      </div>
                      <h3>Drag &amp; Drop file to start ingestion</h3>
                      <p>
                        or <span className="highlight-link">browse files on your system</span>
                      </p>
                      <div className="format-chips">
                        <span className="chip">PDF</span>
                        <span className="chip">DOCX</span>
                        <span className="chip">PNG/JPG</span>
                        <span className="chip">CSV</span>
                        <span className="chip">MP3/WAV</span>
                        <span className="chip">MP4</span>
                        <span className="chip-limit">Max 10MB</span>
                      </div>
                    </div>
                  </div>

                  <div className={`selected-file-card ${selectedFile ? "" : "hidden"}`}>
                    <div className="file-thumb">📄</div>
                    <div className="file-info-main">
                      <div className="file-title">{selectedFile?.name}</div>
                      <div className="file-meta-row">
                        <span>{selectedFile ? formatBytes(selectedFile.size) : "0 KB"}</span> •{" "}
                        <span>{selectedFile?.type || "Binary Stream"}</span>
                      </div>
                    </div>
                    <span className="detected-badge">{detectedEndpointName}</span>
                    <button type="button" className="btn-icon-danger" title="Remove File" onClick={removeFile}>
                      ✕
                    </button>
                  </div>
                </div>

                <form className="upload-form" onSubmit={handleUploadSubmit}>
                  <div className="form-row">
                    <div className="field-group">
                      <label>
                        Document Name <span className="req">*</span>
                      </label>
                      <input
                        type="text"
                        value={docName}
                        onChange={(e) => setDocName(e.target.value)}
                        placeholder="e.g. Q3 Financial Operations Report"
                        required
                      />
                    </div>
                    <div className="field-group">
                      <div className="label-with-btn">
                        <label>
                          Idempotent Key <span className="opt">(Optional)</span>
                        </label>
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => {
                            setIdempotentKey(generateUUID());
                            showToast("Generated new Idempotent Key", "info");
                          }}
                        >
                          Generate UUID
                        </button>
                      </div>
                      <input
                        type="text"
                        value={idempotentKey}
                        onChange={(e) => setIdempotentKey(e.target.value)}
                        placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                      />
                    </div>
                  </div>

                  <div className="form-submit-row">
                    <button type="submit" className="btn btn-primary btn-lg" disabled={!selectedFile || uploading}>
                      {uploading && <span className="spinner"></span>}
                      <span>{uploading ? "Ingesting Document..." : "🚀 Execute Ingestion"}</span>
                    </button>
                  </div>
                </form>
              </div>

              <div className="panel side-panel">
                <div className="card card-response">
                  <div className="card-title-bar">
                    <div className="title-left">
                      <h3>API Response JSON</h3>
                      <span className={`status-badge ${uploadStatus.cls}`}>{uploadStatus.text}</span>
                    </div>
                    <span className="latency-tag">{uploadTimeMs != null ? `${uploadTimeMs} ms` : "-- ms"}</span>
                  </div>

                  <div className="code-viewer-container">
                    <div className="code-viewer-header">
                      <span className="code-lang">JSON</span>
                      <button
                        className="btn-icon-sm"
                        title="Copy JSON"
                        onClick={() => {
                          if (uploadRawResponse) {
                            navigator.clipboard?.writeText(JSON.stringify(uploadRawResponse, null, 2));
                            showToast("API Response JSON copied!", "info");
                          }
                        }}
                      >
                        📋 Copy
                      </button>
                    </div>
                    <pre className="code-block">
                      <code
                        className="json-code"
                        dangerouslySetInnerHTML={{
                          __html: uploadRawResponse
                            ? syntaxHighlightJSON(uploadRawResponse)
                            : escapeHtml(PLACEHOLDER_UPLOAD_JSON),
                        }}
                      />
                    </pre>
                  </div>

                  <div className={`action-buttons-row ${lastUploadedId ? "" : "hidden"}`}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => lastUploadedId && copyText(lastUploadedId)}
                    >
                      📋 Copy Generated ID
                    </button>
                    <button className="btn btn-danger-outline btn-sm" onClick={jumpToDeleteWithId}>
                      🗑️ Delete Content
                    </button>
                  </div>
                </div>

                <div className="card card-history">
                  <div className="card-title-bar">
                    <h3>Ingestion Session History</h3>
                    <button className="btn-link" onClick={() => setSessionHistory([])}>
                      Clear
                    </button>
                  </div>
                  <div className="history-list">
                    {sessionHistory.length === 0 ? (
                      <div className="empty-history">
                        <div className="empty-icon">📂</div>
                        <p>No documents uploaded in this session yet.</p>
                      </div>
                    ) : (
                      sessionHistory.map((item, idx) => (
                        <div className="history-card-item" key={idx}>
                          <div className="history-card-info">
                            <span className="history-doc-name">{item.name}</span>
                            <span className="history-doc-id">ID: {item.id}</span>
                          </div>
                          <button className="btn btn-glass btn-sm" onClick={() => copyText(item.id)}>
                            Copy
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* TAB: QUERY */}
          <section className={`tab-content ${activeTab === "queryTab" ? "active" : ""}`}>
            <div className="grid-container">
              <div className="panel main-panel">
                <div className="panel-header">
                  <div>
                    <h2>RAG Query Console</h2>
                    <p className="panel-subtitle">
                      Ask a question against one or more ingested content IDs and inspect the retrieval-augmented
                      answer.
                    </p>
                  </div>
                </div>

                <form className="upload-form" onSubmit={handleQuerySubmit}>
                  <div className="field-group">
                    <label>
                      Question <span className="req">*</span>
                    </label>
                    <input
                      type="text"
                      value={queryQuestion}
                      onChange={(e) => setQueryQuestion(e.target.value)}
                      placeholder="e.g. What were the Q3 operating expenses?"
                      required
                    />
                  </div>
                  <div className="field-group">
                    <label>
                      Content IDs <span className="req">*</span>
                      <span className="opt"> (comma-separated)</span>
                    </label>
                    <input
                      type="text"
                      value={queryIds}
                      onChange={(e) => setQueryIds(e.target.value)}
                      placeholder="e.g. c8b940e7-73d8-4f1a-b620-802d2bc4a54c, 91a2..."
                      required
                    />
                  </div>

                  <div className="form-submit-row">
                    <button type="submit" className="btn btn-primary btn-lg" disabled={querying}>
                      {querying && <span className="spinner"></span>}
                      <span>{querying ? "Querying..." : "🔍 Run Query"}</span>
                    </button>
                  </div>
                </form>
              </div>

              <div className="panel side-panel">
                <div className="card card-response">
                  <div className="card-title-bar">
                    <div className="title-left">
                      <h3>Query Response JSON</h3>
                      <span className={`status-badge ${queryStatus.cls}`}>{queryStatus.text}</span>
                    </div>
                    <span className="latency-tag">{queryTimeMs != null ? `${queryTimeMs} ms` : "-- ms"}</span>
                  </div>

                  <div className="code-viewer-container">
                    <div className="code-viewer-header">
                      <span className="code-lang">JSON</span>
                      <button
                        className="btn-icon-sm"
                        title="Copy JSON"
                        onClick={() => {
                          if (queryRawResponse) {
                            navigator.clipboard?.writeText(JSON.stringify(queryRawResponse, null, 2));
                            showToast("Query response JSON copied!", "info");
                          }
                        }}
                      >
                        📋 Copy
                      </button>
                    </div>
                    <pre className="code-block">
                      <code
                        className="json-code"
                        dangerouslySetInnerHTML={{
                          __html: queryRawResponse
                            ? syntaxHighlightJSON(queryRawResponse)
                            : escapeHtml(PLACEHOLDER_QUERY_JSON),
                        }}
                      />
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* TAB: DELETE */}
          <section className={`tab-content ${activeTab === "deleteTab" ? "active" : ""}`}>
            <div className="delete-workspace">
              <div className="panel delete-panel">
                <div className="panel-header">
                  <div>
                    <h2>Delete Ingested Content</h2>
                    <p className="panel-subtitle">
                      Permanently purge indexed documents, vector chunks, directory files (`Data/Content/` or
                      `Data/Feed/`), and database records.
                    </p>
                  </div>
                </div>

                <div className="warning-box">
                  <div className="warning-icon">⚠️</div>
                  <div className="warning-text">
                    <strong>Destructive Operation:</strong> This action permanently removes stored content files and
                    associated Supabase database entries (`contents` or `feeds` table).
                  </div>
                </div>

                <form className="delete-form" onSubmit={handleDeleteSubmit}>
                  <div className="field-group">
                    <label>
                      Document / Feed Content ID (UUID) <span className="req">*</span>
                    </label>
                    <div className="input-action-pair">
                      <input
                        type="text"
                        value={deleteId}
                        onChange={(e) => setDeleteId(e.target.value)}
                        placeholder="Enter UUID (e.g. c8b940e7-73d8-4f1a-b620-802d2bc4a54c)"
                        required
                      />
                      <button type="submit" className="btn btn-danger" disabled={deleting}>
                        {deleting && <span className="spinner"></span>}
                        <span>🗑️ Delete Content</span>
                      </button>
                    </div>
                  </div>
                </form>

                <div className="delete-result-box">
                  <div className="card-title-bar">
                    <h3>Deletion Status</h3>
                    <span className={`status-badge ${deleteStatus.cls}`}>{deleteStatus.text}</span>
                  </div>
                  <div className="code-viewer-container">
                    <pre className="code-block">
                      <code
                        className="json-code"
                        dangerouslySetInnerHTML={{
                          __html: deleteRawResponse
                            ? syntaxHighlightJSON(deleteRawResponse)
                            : escapeHtml(PLACEHOLDER_DELETE_JSON),
                        }}
                      />
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* TAB: LOGS */}
          <section className={`tab-content ${activeTab === "logsTab" ? "active" : ""}`}>
            <div className="panel logs-panel">
              <div className="panel-header logs-header-flex">
                <div>
                  <h2>Real-time API Activity Logs</h2>
                  <p className="panel-subtitle">
                    Inspect request payloads, HTTP status codes, latency timings, and curl equivalents.
                  </p>
                </div>
                <div className="logs-controls">
                  <input
                    type="text"
                    className="log-search-input"
                    placeholder="Filter by endpoint or status..."
                    value={logFilter}
                    onChange={(e) => setLogFilter(e.target.value)}
                  />
                  <button className="btn btn-secondary btn-sm" onClick={() => setApiLogs([])}>
                    Clear Logs
                  </button>
                </div>
              </div>

              <div className="table-wrapper">
                <table className="logs-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Method</th>
                      <th>Endpoint</th>
                      <th>Status</th>
                      <th>Latency</th>
                      <th>Response Preview</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredLogs.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="empty-logs">
                          No API activity recorded in this session. Perform an upload or deletion test above.
                        </td>
                      </tr>
                    ) : (
                      filteredLogs.map((log, idx) => (
                        <tr key={idx}>
                          <td>{log.timestamp}</td>
                          <td>
                            <strong style={{ color: log.method === "DELETE" ? "#ef4444" : "#6366f1" }}>
                              {log.method}
                            </strong>
                          </td>
                          <td>{log.endpoint}</td>
                          <td>
                            <span className={`status-badge ${log.status === 200 ? "status-success" : "status-error"}`}>
                              {log.status}
                            </span>
                          </td>
                          <td>{log.duration}</td>
                          <td
                            style={{
                              maxWidth: 320,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {log.response}
                          </td>
                          <td>
                            <button className="btn-icon-sm" onClick={() => copyText(log.response)}>
                              Copy JSON
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </main>
      </div>

      <div className={`toast ${toast.visible ? "" : "hidden"}`}>
        <span>{toast.icon || "ℹ️"}</span>
        <span>{toast.message}</span>
      </div>
    </div>
  );
}

/* ==========================================================================
   Styles (ported from style.css, `body` selector scoped to .zymerag-root)
   ========================================================================== */
const CSS = `
.zymerag-root {
    --bg-dark: #050811;
    --bg-surface: rgba(15, 22, 41, 0.65);
    --bg-surface-hover: rgba(23, 33, 59, 0.8);
    --bg-card: rgba(18, 26, 47, 0.7);

    --border-subtle: rgba(255, 255, 255, 0.07);
    --border-glow: rgba(99, 102, 241, 0.4);
    --border-active: #6366f1;

    --gradient-primary: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    --gradient-glow: rgba(99, 102, 241, 0.25);
    --gradient-danger: linear-gradient(135deg, #ef4444 0%, #f43f5e 100%);

    --primary: #6366f1;
    --primary-light: #818cf8;
    --purple: #a855f7;
    --pink: #ec4899;
    --success: #10b981;
    --success-bg: rgba(16, 185, 129, 0.12);
    --danger: #ef4444;
    --danger-bg: rgba(239, 68, 68, 0.12);
    --warning: #f59e0b;

    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;

    --font-main: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;

    --radius-sm: 8px;
    --radius-md: 14px;
    --radius-lg: 20px;
    --shadow-glass: 0 20px 50px rgba(0, 0, 0, 0.5);

    background-color: var(--bg-dark);
    color: var(--text-primary);
    font-family: var(--font-main);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    line-height: 1.5;
    overflow-x: hidden;
}

.zymerag-root * { box-sizing: border-box; }
.zymerag-root h1, .zymerag-root h2, .zymerag-root h3, .zymerag-root p, .zymerag-root ul { margin: 0; }

.app-wrapper {
    width: 100%;
    max-width: 1380px;
    padding: 24px 32px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    position: relative;
    z-index: 1;
}

.ambient-glow { position: absolute; border-radius: 50%; filter: blur(140px); pointer-events: none; z-index: -1; }
.glow-1 { top: -100px; left: -100px; width: 500px; height: 500px; background: rgba(99, 102, 241, 0.18); }
.glow-2 { bottom: -100px; right: -100px; width: 600px; height: 600px; background: rgba(168, 85, 247, 0.12); }

.navbar {
    display: flex; justify-content: space-between; align-items: center;
    background: var(--bg-surface); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle); padding: 16px 28px; border-radius: var(--radius-md);
    box-shadow: var(--shadow-glass);
}

.nav-brand { display: flex; align-items: center; gap: 16px; }
.brand-logo {
    width: 44px; height: 44px; background: var(--gradient-primary); border-radius: var(--radius-sm);
    display: flex; align-items: center; justify-content: center; font-size: 22px; box-shadow: 0 0 20px var(--gradient-glow);
}
.brand-titles .brand-name { font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; display: flex; align-items: center; gap: 8px; }
.badge-version { font-size: 11px; background: rgba(99, 102, 241, 0.2); color: var(--primary-light); padding: 2px 8px; border-radius: 12px; border: 1px solid rgba(99, 102, 241, 0.3); }
.brand-sub { font-size: 12px; color: var(--text-secondary); font-weight: 500; }

.nav-actions { display: flex; align-items: center; gap: 16px; }
.api-base-bar { display: flex; align-items: center; gap: 10px; background: rgba(0, 0, 0, 0.3); border: 1px solid var(--border-subtle); padding: 6px 14px; border-radius: var(--radius-sm); }
.server-label { font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; }
.api-base-bar input { background: transparent; border: none; color: var(--text-primary); font-family: var(--font-mono); font-size: 13px; width: 170px; outline: none; }

.analytics-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
@media (max-width: 900px) { .analytics-bar { grid-template-columns: repeat(2, 1fr); } }

.metric-card { background: var(--bg-surface); backdrop-filter: blur(16px); border: 1px solid var(--border-subtle); padding: 16px 20px; border-radius: var(--radius-md); display: flex; align-items: center; gap: 16px; }
.metric-icon { width: 44px; height: 44px; border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; font-size: 20px; }
.icon-purple { background: rgba(168, 85, 247, 0.15); border: 1px solid rgba(168, 85, 247, 0.3); }
.icon-green { background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); }
.icon-blue { background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3); }
.icon-amber { background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.3); }
.metric-info { display: flex; flex-direction: column; }
.metric-label { font-size: 12px; color: var(--text-secondary); font-weight: 500; }
.metric-value { font-size: 18px; font-weight: 700; color: #ffffff; font-family: var(--font-mono); }

.tabs-nav { display: flex; gap: 10px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px; flex-wrap: wrap; }
.tab-btn { background: transparent; border: none; color: var(--text-secondary); font-size: 14px; font-weight: 600; padding: 10px 20px; border-radius: var(--radius-sm); cursor: pointer; display: flex; align-items: center; gap: 10px; transition: all 0.2s ease; }
.tab-btn:hover { color: var(--text-primary); background: rgba(255, 255, 255, 0.04); }
.tab-btn.active { color: #ffffff; background: var(--gradient-primary); box-shadow: 0 4px 14px var(--gradient-glow); }
.tab-counter { background: rgba(255, 255, 255, 0.2); font-size: 11px; padding: 2px 7px; border-radius: 10px; }

.tab-content { display: none; }
.tab-content.active { display: block; animation: zr-fadeIn 0.35s ease-out; }
@keyframes zr-fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.grid-container { display: grid; grid-template-columns: 1.35fr 0.85fr; gap: 24px; }
@media (max-width: 1024px) { .grid-container { grid-template-columns: 1fr; } }

.panel { background: var(--bg-surface); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 28px; box-shadow: var(--shadow-glass); }
.panel-header h2 { font-size: 20px; font-weight: 700; }
.panel-subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

.endpoint-grid-title { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin: 22px 0 12px 0; }
.endpoint-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 22px; }
@media (max-width: 640px) { .endpoint-grid { grid-template-columns: 1fr 1fr; } }

.endpoint-card { background: rgba(0, 0, 0, 0.25); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px 14px; display: flex; align-items: center; gap: 12px; cursor: pointer; transition: all 0.2s ease; }
.endpoint-card:hover { border-color: rgba(99, 102, 241, 0.5); background: rgba(99, 102, 241, 0.08); }
.endpoint-card.active { border-color: var(--primary); background: rgba(99, 102, 241, 0.18); box-shadow: 0 0 14px var(--gradient-glow); }
.ep-icon { font-size: 22px; }
.ep-details { display: flex; flex-direction: column; overflow: hidden; }
.ep-name { font-size: 13px; font-weight: 600; }
.ep-route { font-size: 10px; font-family: var(--font-mono); color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.dropzone-container { margin-bottom: 24px; }
.dropzone { border: 2px dashed rgba(99, 102, 241, 0.3); border-radius: var(--radius-md); padding: 40px 20px; text-align: center; background: rgba(0, 0, 0, 0.2); position: relative; cursor: pointer; transition: all 0.25s ease; }
.dropzone:hover, .dropzone.dragover { border-color: var(--primary); background: rgba(99, 102, 241, 0.12); box-shadow: 0 0 20px var(--gradient-glow); }
.file-input { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.upload-cloud-icon { color: var(--primary-light); margin-bottom: 12px; }
.dropzone-body h3 { font-size: 16px; font-weight: 700; }
.dropzone-body p { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
.highlight-link { color: var(--primary-light); text-decoration: underline; font-weight: 600; }
.format-chips { display: flex; justify-content: center; flex-wrap: wrap; gap: 6px; margin-top: 16px; }
.chip { background: rgba(255, 255, 255, 0.06); color: var(--text-secondary); font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 6px; border: 1px solid var(--border-subtle); }
.chip-limit { background: rgba(239, 68, 68, 0.15); color: #fca5a5; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 6px; }

.selected-file-card { display: flex; align-items: center; gap: 16px; background: rgba(99, 102, 241, 0.12); border: 1px solid var(--border-glow); padding: 16px 20px; border-radius: var(--radius-sm); margin-top: 16px; }
.selected-file-card.hidden { display: none; }
.file-thumb { font-size: 28px; }
.file-info-main { flex: 1; overflow: hidden; }
.file-title { font-weight: 700; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.file-meta-row { font-size: 12px; color: var(--text-secondary); }
.detected-badge { background: var(--gradient-primary); color: #ffffff; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 20px; box-shadow: 0 0 10px var(--gradient-glow); white-space: nowrap; }
.btn-icon-danger { background: transparent; border: none; color: var(--text-muted); font-size: 18px; cursor: pointer; padding: 4px; }
.btn-icon-danger:hover { color: var(--danger); }

.upload-form, .delete-form { display: flex; flex-direction: column; gap: 20px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 640px) { .form-row { grid-template-columns: 1fr; } }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-group label { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.label-with-btn { display: flex; justify-content: space-between; align-items: center; }
.req { color: var(--danger); }
.opt { font-weight: 400; color: var(--text-muted); font-size: 11px; }
.field-group input { background: rgba(0, 0, 0, 0.35); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 11px 14px; color: var(--text-primary); font-family: var(--font-main); font-size: 14px; outline: none; transition: all 0.2s ease; width: 100%; }
.field-group input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--gradient-glow); }

.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 24px; border-radius: var(--radius-sm); font-size: 14px; font-weight: 700; cursor: pointer; border: none; transition: all 0.2s ease; }
.btn-primary { background: var(--gradient-primary); color: #ffffff; box-shadow: 0 4px 18px var(--gradient-glow); }
.btn-primary:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 24px var(--gradient-glow); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger { background: var(--gradient-danger); color: #ffffff; box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3); }
.btn-danger:hover:not(:disabled) { transform: translateY(-1px); }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-glass { background: rgba(255, 255, 255, 0.06); color: var(--text-primary); border: 1px solid var(--border-subtle); }
.btn-glass:hover { background: rgba(255, 255, 255, 0.12); }
.btn-secondary { background: rgba(255, 255, 255, 0.08); color: var(--text-primary); }
.btn-outline { background: transparent; border: 1px solid var(--border-subtle); color: var(--text-secondary); text-decoration: none; }
.btn-outline:hover { color: var(--text-primary); border-color: var(--text-secondary); }
.btn-danger-outline { background: transparent; border: 1px solid var(--danger); color: var(--danger); }
.btn-danger-outline:hover { background: var(--danger-bg); }
.btn-sm { padding: 7px 14px; font-size: 12px; }
.btn-lg { padding: 14px 28px; font-size: 15px; width: 100%; }
.btn-link { background: none; border: none; color: var(--primary-light); font-size: 12px; font-weight: 600; cursor: pointer; }
.btn-link:hover { text-decoration: underline; }
.btn-icon-sm { background: rgba(255, 255, 255, 0.08); border: none; color: var(--text-secondary); padding: 4px 10px; border-radius: 6px; font-size: 11px; cursor: pointer; }
.btn-icon-sm:hover { color: var(--text-primary); background: rgba(255, 255, 255, 0.15); }

.side-panel { display: flex; flex-direction: column; gap: 20px; padding: 20px; }
.card { background: rgba(10, 15, 30, 0.6); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 20px; }
.card-title-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px; }
.title-left { display: flex; align-items: center; gap: 10px; }
.card-title-bar h3 { font-size: 15px; font-weight: 700; }
.status-badge { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px; text-transform: uppercase; white-space: nowrap; }
.status-idle { background: rgba(255, 255, 255, 0.08); color: var(--text-muted); }
.status-success { background: var(--success-bg); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.3); }
.status-error { background: var(--danger-bg); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.3); }
.latency-tag { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); }

.code-viewer-container { background: #040711; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); overflow: hidden; }
.code-viewer-header { background: rgba(255, 255, 255, 0.03); padding: 8px 14px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); }
.code-lang { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }
.code-block { padding: 16px; max-height: 240px; overflow-y: auto; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; margin: 0; }
.json-code { color: #a7f3d0; white-space: pre-wrap; word-break: break-all; }
.json-key { color: #93c5fd; font-weight: 600; }
.json-string { color: #6ee7b7; }
.json-number { color: #fde047; }
.json-boolean { color: #f472b6; }
.json-null { color: #94a3b8; }

.action-buttons-row { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
.action-buttons-row.hidden { display: none; }

.history-list { display: flex; flex-direction: column; gap: 10px; max-height: 260px; overflow-y: auto; }
.empty-history { text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px; }
.empty-icon { font-size: 32px; margin-bottom: 6px; }
.history-card-item { background: rgba(0, 0, 0, 0.3); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.history-card-info { display: flex; flex-direction: column; gap: 2px; overflow: hidden; }
.history-doc-name { font-size: 13px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.history-doc-id { font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.delete-workspace { max-width: 800px; margin: 0 auto; }
.warning-box { background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: var(--radius-sm); padding: 16px 20px; display: flex; align-items: flex-start; gap: 14px; margin: 20px 0; }
.warning-icon { font-size: 22px; }
.warning-text { font-size: 13px; color: #fde68a; }
.input-action-pair { display: flex; gap: 12px; margin-top: 6px; flex-wrap: wrap; }
.input-action-pair input { flex: 1; min-width: 200px; }
.delete-result-box { margin-top: 24px; border-top: 1px solid var(--border-subtle); padding-top: 20px; }

.logs-header-flex { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 14px; }
.logs-controls { display: flex; gap: 12px; }
.log-search-input { background: rgba(0, 0, 0, 0.35); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 8px 14px; color: var(--text-primary); font-size: 13px; width: 260px; outline: none; }
.table-wrapper { overflow-x: auto; }
.logs-table { width: 100%; border-collapse: collapse; text-align: left; }
.logs-table th, .logs-table td { padding: 14px 16px; border-bottom: 1px solid var(--border-subtle); }
.logs-table th { font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; background: rgba(0, 0, 0, 0.3); }
.logs-table td { font-family: var(--font-mono); font-size: 12px; }
.empty-logs { text-align: center; color: var(--text-muted); padding: 32px; }

.pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-muted); }
.pulse-dot.online { background: var(--success); box-shadow: 0 0 10px var(--success); }
.pulse-dot.offline { background: var(--danger); }

.spinner { width: 16px; height: 16px; border: 2px solid rgba(255, 255, 255, 0.3); border-top-color: #ffffff; border-radius: 50%; animation: zr-spin 0.8s linear infinite; display: inline-block; }
@keyframes zr-spin { to { transform: rotate(360deg); } }

.toast { position: fixed; bottom: 30px; right: 30px; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(12px); border: 1px solid var(--primary); padding: 14px 24px; border-radius: var(--radius-md); box-shadow: var(--shadow-glass); display: flex; align-items: center; gap: 12px; z-index: 9999; font-size: 14px; font-weight: 600; animation: zr-slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.toast.hidden { display: none; }
@keyframes zr-slideUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
`;