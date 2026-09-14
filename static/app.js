/**
 * Nori AI Dashboard Engine - Left Sidebar & Workspace Controls
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const serverUrlInput = document.getElementById('serverUrlInput');
    const pingBtn = document.getElementById('pingBtn');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');

    const statTotalIngested = document.getElementById('statTotalIngested');
    const statSuccessRate = document.getElementById('statSuccessRate');
    const statAvgLatency = document.getElementById('statAvgLatency');

    const tabBtns = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');

    const sourceTiles = document.querySelectorAll('.source-tile');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const filePreviewBanner = document.getElementById('filePreviewBanner');
    const previewFileName = document.getElementById('previewFileName');
    const previewFileSize = document.getElementById('previewFileSize');
    const previewFileType = document.getElementById('previewFileType');
    const detectedEndpointBadge = document.getElementById('detectedEndpointBadge');
    const removeFileBtn = document.getElementById('removeFileBtn');

    const uploadForm = document.getElementById('uploadForm');
    const docNameInput = document.getElementById('docNameInput');
    const idempotentKeyInput = document.getElementById('idempotentKeyInput');
    const genUuidBtn = document.getElementById('genUuidBtn');
    const submitUploadBtn = document.getElementById('submitUploadBtn');
    const uploadBtnSpinner = document.getElementById('uploadBtnSpinner');
    const uploadBtnText = document.getElementById('uploadBtnText');

    const responseStatusBadge = document.getElementById('responseStatusBadge');
    const responseTime = document.getElementById('responseTime');
    const jsonResponseViewer = document.getElementById('jsonResponseViewer');
    const copyJsonBtn = document.getElementById('copyJsonBtn');
    const quickActionBar = document.getElementById('quickActionBar');
    const copyIdBtn = document.getElementById('copyIdBtn');
    const deleteIngestedBtn = document.getElementById('deleteIngestedBtn');

    const historyList = document.getElementById('historyList');
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');

    const deleteForm = document.getElementById('deleteForm');
    const deleteIdInput = document.getElementById('deleteIdInput');
    const submitDeleteBtn = document.getElementById('submitDeleteBtn');
    const deleteBtnSpinner = document.getElementById('deleteBtnSpinner');
    const deleteStatusBadge = document.getElementById('deleteStatusBadge');
    const deleteJsonViewer = document.getElementById('deleteJsonViewer');

    const logsTableBody = document.getElementById('logsTableBody');
    const logTabCounter = document.getElementById('logTabCounter');
    const logSearchInput = document.getElementById('logSearchInput');
    const clearLogsBtn = document.getElementById('clearLogsBtn');

    const toast = document.getElementById('toast');
    const toastIcon = document.getElementById('toastIcon');
    const toastMessage = document.getElementById('toastMessage');

    const queryForm = document.getElementById('queryForm');
    const queryQuestionInput = document.getElementById('queryQuestionInput');
    const queryIdsInput = document.getElementById('queryIdsInput');
    const submitQueryBtn = document.getElementById('submitQueryBtn');
    const queryBtnSpinner = document.getElementById('queryBtnSpinner');
    const queryBtnText = document.getElementById('queryBtnText');
    const queryStatusBadge = document.getElementById('queryStatusBadge');
    const queryResponseTime = document.getElementById('queryResponseTime');
    const queryJsonViewer = document.getElementById('queryJsonViewer');
    const copyQueryJsonBtn = document.getElementById('copyQueryJsonBtn');

    let rawLastQueryResponse = null;

    // App State
    let selectedFile = null;
    let selectedEndpoint = '/upload/upload_pdf';
    let lastUploadedId = null;
    let rawLastResponse = null;

    let totalIngestedCount = 0;
    let totalSuccessCount = 0;
    let totalRequests = 0;
    let totalLatencyMs = 0;

    let sessionHistory = [];
    let apiLogs = [];

    // Toast Notifications
    function showToast(message, type = 'info') {
        const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
        toastIcon.textContent = icons[type] || 'ℹ️';
        toastMessage.textContent = message;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3500);
    }

    // Syntax Highlighting for JSON
    function syntaxHighlightJSON(json) {
        if (typeof json !== 'string') {
            json = JSON.stringify(json, null, 2);
        }
        json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
            let cls = 'json-number';
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'json-key';
                } else {
                    cls = 'json-string';
                }
            } else if (/true|false/.test(match)) {
                cls = 'json-boolean';
            } else if (/null/.test(match)) {
                cls = 'json-null';
            }
            return '<span class="' + cls + '">' + match + '</span>';
        });
    }

    // Bytes Formatter
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // UUID Generator
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    genUuidBtn.addEventListener('click', () => {
        idempotentKeyInput.value = generateUUID();
        showToast('Generated new Idempotency Key', 'info');
    });

    // Navigation Pills / Sidebar Tabs
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const target = btn.getAttribute('data-tab');
            document.getElementById(target).classList.add('active');
        });
    });

    // Source Selection Tiles
    sourceTiles.forEach(tile => {
        tile.addEventListener('click', () => {
            sourceTiles.forEach(t => t.classList.remove('active'));
            tile.classList.add('active');
            selectedEndpoint = tile.getAttribute('data-endpoint');
            detectedEndpointBadge.textContent = tile.querySelector('.t-name').textContent;
        });
    });

    // Ping API Backend
    async function pingBackend() {
        const baseUrl = serverUrlInput.value.replace(/\/$/, '');
        statusDot.className = 'pulse-indicator';
        statusText.textContent = 'Pinging...';

        try {
            const startTime = performance.now();
            const res = await fetch(`${baseUrl}/openapi.json`, { method: 'GET' });
            const elapsed = Math.round(performance.now() - startTime);

            if (res.ok) {
                statusDot.className = 'pulse-indicator online';
                statusText.textContent = `System Online (${elapsed}ms)`;
            } else {
                statusDot.className = 'pulse-indicator offline';
                statusText.textContent = `HTTP ${res.status}`;
            }
        } catch (err) {
            statusDot.className = 'pulse-indicator offline';
            statusText.textContent = 'System Offline';
        }
    }

    pingBtn.addEventListener('click', pingBackend);
    pingBackend();

    // File Extension to Endpoint Mapper
    function mapFileToEndpoint(file) {
        if (!file) return null;
        const ext = file.name.split('.').pop().toLowerCase();

        const extMap = {
            'pdf': '/upload/upload_pdf',
            'docx': '/upload/upload_docx',
            'png': '/upload/upload_image', 'jpg': '/upload/upload_image', 'jpeg': '/upload/upload_image', 'tiff': '/upload/upload_image', 'bmp': '/upload/upload_image', 'webp': '/upload/upload_image',
            'csv': '/upload/upload_csv', 'xlsx': '/upload/upload_csv', 'xls': '/upload/upload_csv',
            'mp3': '/upload/upload_audio', 'wav': '/upload/upload_audio', 'm4a': '/upload/upload_audio',
            'mp4': '/upload/upload_video', 'm4v': '/upload/upload_video', 'mov': '/upload/upload_video'
        };

        return extMap[ext] || '/upload/upload_pdf';
    }

    // Drag & Drop Handling
    ['dragenter', 'dragover'].forEach(name => {
        dropzone.addEventListener(name, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        dropzone.addEventListener(name, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFileSelection(files[0]);
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFileSelection(e.target.files[0]);
    });

    function handleFileSelection(file) {
        if (file.size > 10 * 1024 * 1024) {
            showToast('File exceeds maximum allowed limit of 10MB', 'error');
            return;
        }

        selectedFile = file;
        selectedEndpoint = mapFileToEndpoint(file);

        // Highlight matching source tile
        sourceTiles.forEach(t => {
            if (t.getAttribute('data-endpoint') === selectedEndpoint) {
                t.classList.add('active');
                detectedEndpointBadge.textContent = t.querySelector('.t-name').textContent;
            } else {
                t.classList.remove('active');
            }
        });

        // Set Preview Details
        previewFileName.textContent = file.name;
        previewFileSize.textContent = formatBytes(file.size);
        previewFileType.textContent = file.type || 'Binary Document';
        filePreviewBanner.classList.remove('hidden');

        // Auto document title
        if (!docNameInput.value.trim()) {
            const baseName = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
            docNameInput.value = baseName;
        }

        submitUploadBtn.disabled = false;
    }

    removeFileBtn.addEventListener('click', () => {
        selectedFile = null;
        fileInput.value = '';
        filePreviewBanner.classList.add('hidden');
        submitUploadBtn.disabled = true;
    });

    // Form Submit: Ingest Document
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!selectedFile) return;

        const baseUrl = serverUrlInput.value.replace(/\/$/, '');
        const docName = docNameInput.value.trim();
        const idempotentKey = idempotentKeyInput.value.trim();

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('name', docName);
        if (idempotentKey) formData.append('idempotent_key', idempotentKey);

        // UI Loading State
        submitUploadBtn.disabled = true;
        uploadBtnSpinner.classList.remove('hidden');
        uploadBtnText.textContent = 'Ingesting Document to Knowledge Base...';
        responseStatusBadge.className = 'status-pill status-idle';
        responseStatusBadge.textContent = 'Processing...';

        const startTime = performance.now();
        let status = 0;
        let data = null;

        try {
            const res = await fetch(`${baseUrl}${selectedEndpoint}`, {
                method: 'POST',
                body: formData
            });

            status = res.status;
            const duration = Math.round(performance.now() - startTime);
            responseTime.textContent = `${duration} ms`;

            data = await res.json();
            rawLastResponse = data;
            jsonResponseViewer.innerHTML = syntaxHighlightJSON(data);

            totalRequests++;
            totalLatencyMs += duration;

            if (res.ok) {
                totalSuccessCount++;
                totalIngestedCount++;
                responseStatusBadge.className = 'status-pill status-success';
                responseStatusBadge.textContent = '200 OK';
                showToast('Document ingested successfully to Nori Knowledge Base!', 'success');

                if (data.id) {
                    lastUploadedId = data.id;
                    quickActionBar.classList.remove('hidden');
                    addHistoryItem(docName, data.id, selectedEndpoint);
                }
            } else {
                responseStatusBadge.className = 'status-pill status-error';
                responseStatusBadge.textContent = `HTTP ${status}`;
                showToast(data.detail || 'Ingestion failed', 'error');
            }

            updateMetrics();
            addLogEntry('POST', selectedEndpoint, status, duration, data);

        } catch (err) {
            const duration = Math.round(performance.now() - startTime);
            responseStatusBadge.className = 'status-pill status-error';
            responseStatusBadge.textContent = 'Network Error';
            jsonResponseViewer.innerHTML = syntaxHighlightJSON({ error: err.message });
            showToast(`Request failed: ${err.message}`, 'error');
            addLogEntry('POST', selectedEndpoint, 'FAIL', duration, { error: err.message });
        } finally {
            submitUploadBtn.disabled = false;
            uploadBtnSpinner.classList.add('hidden');
            uploadBtnText.textContent = '🚀 Ingest Document to Knowledge Base';
        }
    });

    // Update Analytics Metrics
    function updateMetrics() {
        statTotalIngested.textContent = totalIngestedCount;
        const rate = totalRequests > 0 ? Math.round((totalSuccessCount / totalRequests) * 100) : 100;
        statSuccessRate.textContent = `${rate}%`;
        const avg = totalRequests > 0 ? Math.round(totalLatencyMs / totalRequests) : 0;
        statAvgLatency.textContent = `${avg} ms`;
    }

    // Copy Response JSON
    copyJsonBtn.addEventListener('click', () => {
        if (rawLastResponse) {
            navigator.clipboard.writeText(JSON.stringify(rawLastResponse, null, 2));
            showToast('Response JSON copied to clipboard!', 'info');
        }
    });

    copyIdBtn.addEventListener('click', () => {
        if (lastUploadedId) {
            navigator.clipboard.writeText(lastUploadedId);
            showToast('Document ID copied!', 'info');
        }
    });

    deleteIngestedBtn.addEventListener('click', () => {
        if (lastUploadedId) {
            deleteIdInput.value = lastUploadedId;
            document.querySelector('[data-tab="deleteTab"]').click();
        }
    });

    // Session Knowledge History
    function addHistoryItem(name, id, endpoint) {
        sessionHistory.unshift({ name, id, endpoint, time: new Date().toLocaleTimeString() });
        renderHistory();
    }

    function renderHistory() {
        if (sessionHistory.length === 0) {
            historyList.innerHTML = '<div class="empty-state"><div class="e-icon">📂</div><p>No knowledge sources added in this session yet.</p></div>';
            return;
        }

        historyList.innerHTML = sessionHistory.map(item => `
            <div class="history-item-card">
                <div class="history-item-info">
                    <span class="history-item-title">${escapeHtml(item.name)}</span>
                    <span class="history-item-sub">ID: ${item.id}</span>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="copyText('${item.id}')">Copy</button>
            </div>
        `).join('');
    }

    window.copyText = (text) => {
        navigator.clipboard.writeText(text);
        showToast(`Copied ID: ${text}`, 'info');
    };

    clearHistoryBtn.addEventListener('click', () => {
        sessionHistory = [];
        renderHistory();
    });

    // Delete Form Handling
    deleteForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const idToDelete = deleteIdInput.value.trim();
        if (!idToDelete) return;

        const baseUrl = serverUrlInput.value.replace(/\/$/, '');
        submitDeleteBtn.disabled = true;
        deleteBtnSpinner.classList.remove('hidden');

        const formData = new FormData();
        formData.append('id', idToDelete);

        const startTime = performance.now();

        try {
            const res = await fetch(`${baseUrl}/delete/delete_content`, {
                method: 'DELETE',
                body: formData
            });

            const duration = Math.round(performance.now() - startTime);
            const data = await res.json();
            deleteJsonViewer.innerHTML = syntaxHighlightJSON(data);

            totalRequests++;
            totalLatencyMs += duration;

            if (res.ok) {
                totalSuccessCount++;
                deleteStatusBadge.className = 'status-pill status-success';
                deleteStatusBadge.textContent = '200 OK';
                showToast('Record purged successfully!', 'success');
            } else {
                deleteStatusBadge.className = 'status-pill status-error';
                deleteStatusBadge.textContent = `HTTP ${res.status}`;
                showToast(data.detail || 'Purge failed', 'error');
            }

            updateMetrics();
            addLogEntry('DELETE', '/delete/delete_content', res.status, duration, data);
        } catch (err) {
            deleteStatusBadge.className = 'status-pill status-error';
            deleteStatusBadge.textContent = 'Error';
            deleteJsonViewer.innerHTML = syntaxHighlightJSON({ error: err.message });
            showToast(`Delete request failed: ${err.message}`, 'error');
        } finally {
            submitDeleteBtn.disabled = false;
            deleteBtnSpinner.classList.add('hidden');
        }
    });

    // Activity Logging
    function addLogEntry(method, endpoint, status, duration, response) {
        apiLogs.unshift({
            timestamp: new Date().toLocaleTimeString(),
            method,
            endpoint,
            status,
            duration: `${duration} ms`,
            response: JSON.stringify(response)
        });

        logTabCounter.textContent = apiLogs.length;
        renderLogs();
    }

    function renderLogs() {
        const filter = logSearchInput.value.toLowerCase().trim();
        const filtered = apiLogs.filter(log => 
            !filter || 
            log.endpoint.toLowerCase().includes(filter) || 
            log.status.toString().includes(filter) ||
            log.method.toLowerCase().includes(filter)
        );

        if (filtered.length === 0) {
            logsTableBody.innerHTML = '<tr><td colspan="7" class="empty-table">No API activity logs match your filter.</td></tr>';
            return;
        }

        logsTableBody.innerHTML = filtered.map(log => `
            <tr>
                <td>${log.timestamp}</td>
                <td><strong style="color: ${log.method === 'DELETE' ? '#ef4444' : '#10b981'}">${log.method}</strong></td>
                <td>${escapeHtml(log.endpoint)}</td>
                <td><span class="status-pill ${log.status === 200 ? 'status-success' : 'status-error'}">${log.status}</span></td>
                <td>${log.duration}</td>
                <td style="max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(log.response)}</td>
                <td><button class="btn-code-action" onclick="copyText('${escapeHtml(log.response).replace(/'/g, "\\'")}')">Copy JSON</button></td>
            </tr>
        `).join('');
    }

    logSearchInput.addEventListener('input', renderLogs);

    clearLogsBtn.addEventListener('click', () => {
        apiLogs = [];
        logTabCounter.textContent = '0';
        renderLogs();
    });

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>"']/g, function(m) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
        });
    }
});
queryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const baseUrl = serverUrlInput.value.replace(/\/$/, '');
    const question = queryQuestionInput.value.trim();
    const ids = queryIdsInput.value.split(',').map(s => s.trim()).filter(Boolean);

    if (!question || ids.length === 0) {
        showToast('Question and at least one Content ID are required', 'error');
        return;
    }

    submitQueryBtn.disabled = true;
    queryBtnSpinner.classList.remove('hidden');
    queryBtnText.textContent = 'Querying...';
    queryStatusBadge.className = 'status-badge status-idle';
    queryStatusBadge.textContent = 'Processing...';

    const params = new URLSearchParams();
    params.append('question', question);
    ids.forEach(id => params.append('ids', id)); // repeated ids=... for FastAPI list parsing

    const startTime = performance.now();
    let status = 0;
    let data = null;

    try {
        const res = await fetch(`${baseUrl}/query/query?${params.toString()}`, {
            method: 'GET'
        });

        status = res.status;
        const duration = Math.round(performance.now() - startTime);
        queryResponseTime.textContent = `${duration} ms`;

        data = await res.json();
        rawLastQueryResponse = data;
        queryJsonViewer.innerHTML = syntaxHighlightJSON(data);

        totalRequests++;
        totalLatencyMs += duration;

        if (res.ok) {
            totalSuccessCount++;
            queryStatusBadge.className = 'status-badge status-success';
            queryStatusBadge.textContent = '200 OK';
            showToast('Query executed successfully!', 'success');
        } else {
            queryStatusBadge.className = 'status-badge status-error';
            queryStatusBadge.textContent = `HTTP ${status}`;
            showToast((data && data.detail) || 'Query failed', 'error');
        }

        updateMetrics();
        addLogEntry('GET', '/query/query', status, duration, data);

    } catch (err) {
        const duration = Math.round(performance.now() - startTime);
        queryStatusBadge.className = 'status-badge status-error';
        queryStatusBadge.textContent = 'Network Error';
        queryJsonViewer.innerHTML = syntaxHighlightJSON({ error: err.message });
        showToast(`Request failed: ${err.message}`, 'error');
        addLogEntry('GET', '/query/query', 'FAIL', duration, { error: err.message });
    } finally {
        submitQueryBtn.disabled = false;
        queryBtnSpinner.classList.add('hidden');
        queryBtnText.textContent = '🔍 Run Query';
    }
});

copyQueryJsonBtn.addEventListener('click', () => {
    if (rawLastQueryResponse) {
        navigator.clipboard.writeText(JSON.stringify(rawLastQueryResponse, null, 2));
        showToast('Query response JSON copied!', 'info');
    }
});
