// ============================================================
// frontend/js/api.js
// ============================================================
// Central API client for MediResearch AI
// ============================================================

const API_BASE = 'http://localhost:8000';

// ── Generic API Call ─────────────────────────────────────────
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method: method,
        headers: { 'Content-Type': 'application/json' },
    };

    if (body && method !== 'GET') {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }
        return data;
    } catch (error) {
        if (error.message.includes('Failed to fetch')) {
            throw new Error('Cannot connect to backend. Make sure uvicorn is running on port 8000.');
        }
        throw error;
    }
}

// ── Health Check ─────────────────────────────────────────────
async function checkHealth() {
    return await apiCall('/health');
}

// ── RESEARCH ENDPOINTS ───────────────────────────────────────
async function apiStartResearch(query, focus_area) {
    return await apiCall('/research/start', 'POST', { query, focus_area });
}

async function getResearchStatus(session_id) {
    return await apiCall(`/research/${session_id}/status`);
}

async function submitApproval(session_id, decision, comments = '') {
    return await apiCall(`/research/${session_id}/approve`, 'POST', { 
        decision, 
        comments 
    });
}

async function getReport(session_id) {
    return await apiCall(`/research/${session_id}/report`);
}

// ── SESSION ENDPOINTS ────────────────────────────────────────
async function listSessions(limit = 20, offset = 0) {
    return await apiCall(`/sessions?limit=${limit}&offset=${offset}`);
}

async function searchSessions(query) {
    return await apiCall(`/sessions/search?q=${encodeURIComponent(query)}`);
}

async function getSession(session_id) {
    return await apiCall(`/sessions/${session_id}`);
}

async function deleteSession(session_id) {
    return await apiCall(`/sessions/${session_id}`, 'DELETE');
}

// ── EXPORT ENDPOINTS ─────────────────────────────────────────
async function exportPDF(session_id) {
    return await apiCall('/export/pdf', 'POST', { session_id });
}

async function exportWord(session_id) {
    return await apiCall('/export/word', 'POST', { session_id });
}

async function getExportStatus(session_id) {
    return await apiCall(`/export/status/${session_id}`);
}

function getDownloadURL(session_id, format) {
    return `${API_BASE}/export/download/${session_id}/${format}`;
}

// ── IMPROVED HEALTH CHECK FOR FRONTEND ───────────────────────
async function checkAPIHealth() {
    const dot  = document.getElementById('apiStatusDot');
    const text = document.getElementById('apiStatusText');

    try {
        await checkHealth();
        if (dot)  dot.style.background = '#34d399';
        if (text) text.textContent = 'API Online';
        console.log("✅ API Status: Online");
        return true;
    } catch (error) {
        if (dot)  dot.style.background = '#f87171';
        if (text) text.textContent = 'API Offline';
        console.warn("⚠️ API Status: Offline", error.message);
        return false;
    }
}

// ── Polling Helper (unchanged) ───────────────────────────────
function pollResearchStatus(session_id, onUpdate, onPaused, onCompleted, onError, intervalMs = 3000) {
    const interval = setInterval(async () => {
        try {
            const status = await getResearchStatus(session_id);
            if (onUpdate) onUpdate(status);

            if (status.status === 'paused') {
                clearInterval(interval);
                if (onPaused) onPaused(status);
            } else if (status.status === 'completed') {
                clearInterval(interval);
                if (onCompleted) onCompleted(status);
            } else if (status.status === 'failed') {
                clearInterval(interval);
                if (onError) onError(new Error(status.message || 'Research failed'));
            }
        } catch (error) {
            clearInterval(interval);
            if (onError) onError(error);
        }
    }, intervalMs);

    return interval;
}

// ── Utility Functions ────────────────────────────────────────
function formatConfidence(score) {
    if (score >= 80) return { label: 'High',   cssClass: 'high',   color: '#057a55' };
    if (score >= 60) return { label: 'Medium', cssClass: 'medium', color: '#c27803' };
    return { label: 'Low', cssClass: 'low', color: '#c81e1e' };
}

function formatDate(isoString) {
    if (!isoString) return 'Unknown date';
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
}

function getFocusBadgeClass(focusArea) {
    const map = {
        disease: 'badge-disease',
        drug:    'badge-drug',
        news:    'badge-news',
        general: 'badge-general'
    };
    return map[focusArea] || 'badge-general';
}

function markdownToHTML(markdown) {
    if (!markdown) return '';
    let html = markdown
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
        .replace(/^---$/gm, '<hr>')
        .replace(/\n\n/g, '</p><p>');

    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    return `<div class="report-content"><p>${html}</p></div>`;
}

function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed; top:80px; right:20px; z-index:9999; display:flex; flex-direction:column; gap:8px;';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.style.cssText = `
        background:white; border-left:4px solid ${
            type==='success'?'#057a55':type==='danger'?'#c81e1e':type==='warning'?'#c27803':'#1a56db'
        }; border-radius:8px; padding:12px 16px; box-shadow:0 4px 12px rgba(0,0,0,0.15);
        font-size:0.875rem; max-width:320px; animation:slideIn 0.3s ease;
    `;
    toast.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px;">
            <span>${type==='success'?'✅':type==='danger'?'❌':type==='warning'?'⚠️':'ℹ️'}</span>
            <span>${message}</span>
        </div>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}