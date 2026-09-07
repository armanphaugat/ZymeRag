/**
 * ZymeRag Developer Dashboard - Core Application Engine
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

    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    const endpointCards = document.querySelectorAll('.endpoint-card');
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

    // Helper: Toast Notifications
    function showToast(message, type = 'info') {
        const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
        toastIcon.textContent = icons[type] || 'ℹ️';
        toastMessage.textContent = message;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3500);
    }

    // Helper: Syntax Highlighting for JSON
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

    // Helper: Format File Sizes
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Helper: UUID v4
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    genUuidBtn.addEventListener('click', () => {
        idempotentKeyInput.value = generateUUID();
        showToast('Generated new Idempotent Key', 'info');
    });

    // Navigation Tabs
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const target = btn.getAttribute('data-tab');
            document.getElementById(target).classList.add('active');
        });
    });

    // Endpoint Selection Cards Grid
    endpointCards.forEach(card => {
        card.addEventListener('click', () => {
            endpointCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectedEndpoint = card.getAttribute('data-endpoint');
            detectedEndpointBadge.textContent = card.querySelector('.ep-name').textContent;
        });
    });

    // Ping API Backend Connection
    async function pingBackend() {
        const baseUrl = serverUrlInput.value.replace(/\/$/, '');
        statusDot.className = 'pulse-dot';
        statusText.textContent = 'Pinging...';

        try {
            const startTime = performance.now();
            const res = await fetch(`${baseUrl}/openapi.json`, { method: 'GET' });
            const elapsed = Math.round(performance.now() - startTime);

            if (res.ok) {
                statusDot.className = 'pulse-dot online';
                statusText.textContent = `Online (${elapsed}ms)`;
            } else {
                statusDot.className = 'pulse-dot offline';
                statusText.textContent = `HTTP ${res.status}`;
            }
        } catch (err) {
            statusDot.className = 'pulse-dot offline';
            statusText.textContent = 'Offline';
        }
    }

    pingBtn.addEventListener('click', pingBackend);
    pingBackend();

    // Extension to Endpoint Mapper
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

    // Drag & Drop Handlers
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

        // Highlight matching endpoint card
        endpointCards.forEach(c => {
            if (c.getAttribute('data-endpoint') === selectedEndpoint) {
                c.classList.add('active');
                detectedEndpointBadge.textContent = c.querySelector('.ep-name').textContent;
            } else {
                c.classList.remove('active');
            }
        });

        // Set UI Preview
        previewFileName.textContent = file.name;
        previewFileSize.textContent = formatBytes(file.size);
        previewFileType.textContent = file.type || 'Binary Stream';
        filePreviewBanner.classList.remove('hidden');

        // Auto doc name
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

    // Form Submit: Ingestion Request
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

        // UI Loading
        submitUploadBtn.disabled = true;
        uploadBtnSpinner.classList.remove('hidden');
        uploadBtnText.textContent = 'Ingesting Document...';
        responseStatusBadge.className = 'status-badge status-idle';
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
                responseStatusBadge.className = 'status-badge status-success';
                responseStatusBadge.textContent = '200 OK';
                showToast('Document ingested successfully!', 'success');

                if (data.id) {
                    lastUploadedId = data.id;
                    quickActionBar.classList.remove('hidden');
                    addHistoryItem(docName, data.id, selectedEndpoint);
                }
            } else {
                responseStatusBadge.className = 'status-badge status-error';
                responseStatusBadge.textContent = `HTTP ${status}`;
                showToast(data.detail || 'Ingestion failed', 'error');
            }

            updateMetrics();
            addLogEntry('POST', selectedEndpoint, status, duration, data);

        } catch (err) {
            const duration = Math.round(performance.now() - startTime);
            responseStatusBadge.className = 'status-badge status-error';
            responseStatusBadge.textContent = 'Network Error';
            jsonResponseViewer.innerHTML = syntaxHighlightJSON({ error: err.message });
            showToast(`Request failed: ${err.message}`, 'error');
            addLogEntry('POST', selectedEndpoint, 'FAIL', duration, { error: err.message });
        } finally {
            submitUploadBtn.disabled = false;
            uploadBtnSpinner.classList.add('hidden');
            uploadBtnText.textContent = '🚀 Execute Ingestion';
        }
    });

    // Update Analytics Bar
    function updateMetrics() {
        statTotalIngested.textContent = totalIngestedCount;
        const rate = totalRequests > 0 ? Math.round((totalSuccessCount / totalRequests) * 100) : 100;
        statSuccessRate.textContent = `${rate}%`;
        const avg = totalRequests > 0 ? Math.round(totalLatencyMs / totalRequests) : 0;
        statAvgLatency.textContent = `${avg} ms`;
    }

    // Copy JSON Viewer
    copyJsonBtn.addEventListener('click', () => {
        if (rawLastResponse) {
            navigator.clipboard.writeText(JSON.stringify(rawLastResponse, null, 2));
            showToast('API Response JSON copied!', 'info');
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

    // Session History Management
    function addHistoryItem(name, id, endpoint) {
        sessionHistory.unshift({ name, id, endpoint, time: new Date().toLocaleTimeString() });
        renderHistory();
    }

    function renderHistory() {
        if (sessionHistory.length === 0) {
            historyList.innerHTML = '<div class="empty-history"><div class="empty-icon">📂</div><p>No documents uploaded in this session yet.</p></div>';
            return;
        }

        historyList.innerHTML = sessionHistory.map(item => `
            <div class="history-card-item">
                <div class="history-card-info">
                    <span class="history-doc-name">${escapeHtml(item.name)}</span>
                    <span class="history-doc-id">ID: ${item.id}</span>
                </div>
                <button class="btn btn-glass btn-sm" onclick="copyText('${item.id}')">Copy</button>
            </div>
        `).join('');
    }

    window.copyText = (text) => {
        navigator.clipboard.writeText(text);
        showToast(`Copied: ${text}`, 'info');
    };

    clearHistoryBtn.addEventListener('click', () => {
        sessionHistory = [];
        renderHistory();
    });

    // Delete Form Handler
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
                deleteStatusBadge.className = 'status-badge status-success';
                deleteStatusBadge.textContent = '200 OK';
                showToast('Content successfully deleted!', 'success');
            } else {
                deleteStatusBadge.className = 'status-badge status-error';
                deleteStatusBadge.textContent = `HTTP ${res.status}`;
                showToast(data.detail || 'Deletion failed', 'error');
            }

            updateMetrics();
            addLogEntry('DELETE', '/delete/delete_content', res.status, duration, data);
        } catch (err) {
            deleteStatusBadge.className = 'status-badge status-error';
            deleteStatusBadge.textContent = 'Error';
            deleteJsonViewer.innerHTML = syntaxHighlightJSON({ error: err.message });
            showToast(`Delete request failed: ${err.message}`, 'error');
        } finally {
            submitDeleteBtn.disabled = false;
            deleteBtnSpinner.classList.add('hidden');
        }
    });

    // Realtime Activity Logging
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
            logsTableBody.innerHTML = '<tr><td colspan="7" class="empty-logs">No API activity logs found.</td></tr>';
            return;
        }

        logsTableBody.innerHTML = filtered.map(log => `
            <tr>
                <td>${log.timestamp}</td>
                <td><strong style="color: ${log.method === 'DELETE' ? '#ef4444' : '#6366f1'}">${log.method}</strong></td>
                <td>${escapeHtml(log.endpoint)}</td>
                <td><span class="status-badge ${log.status === 200 ? 'status-success' : 'status-error'}">${log.status}</span></td>
                <td>${log.duration}</td>
                <td style="max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(log.response)}</td>
                <td><button class="btn-icon-sm" onclick="copyText('${escapeHtml(log.response).replace(/'/g, "\\'")}')">Copy JSON</button></td>
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
