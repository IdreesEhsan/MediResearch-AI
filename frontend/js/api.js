// ============================================================
// frontend/js/api.js
// ============================================================
// Central API client — all calls to the FastAPI backend
// are made through this file.
//
// This keeps API logic in one place — if the base URL
// changes you only need to update it here.
// ============================================================

// ── Base URL ──────────────────────────────────────────────────
// Change this if your API runs on a different port
const API_BASE = 'http://localhost:8000';


// ── Generic fetch wrapper ─────────────────────────────────────
/**
 * Makes an API call and returns parsed JSON.
 * Throws an error with the API's message if the call fails.
 *
 * @param {string} endpoint  - API path e.g. '/health'
 * @param {string} method    - HTTP method (GET, POST, DELETE)
 * @param {object} body      - Request body for POST requests
 * @returns {Promise<object>} - Parsed JSON response
 */
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };

    // Only add body for POST/PUT/PATCH requests
    if (body && method !== 'GET') {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);

        // Parse response JSON
        const data = await response.json();

        // Throw error if response is not OK (4xx or 5xx)
        if (!response.ok) {
            throw new Error(data.detail || `API error: ${response.status}`);
        }

        return data;

    } catch (error) {
        // Re-throw with a clear message
        if (error.message.includes('Failed to fetch')) {
            throw new Error('Cannot connect to API. Make sure the server is running on port 8000.');
        }
        throw error;
    }
}


// ════════════════════════════════════════════════════════════
// RESEARCH API
// ════════════════════════════════════════════════════════════

/**
 * Start a new research session.
 *
 * @param {string} query      - Medical research question
 * @param {string} focus_area - general / disease / drug / news
 * @returns {Promise<{session_id, status, message}>}
 */
async function apiStartResearch(query, focus_area) {
    return await apiCall('/research/start', 'POST', { query, focus_area });
}


/**
 * Get the current status of a research session.
 *
 * @param {string} session_id
 * @returns {Promise<{session_id, status, current_agent, confidence_score}>}
 */
async function getResearchStatus(session_id) {
    return await apiCall(`/research/${session_id}/status`);
}


/**
 * Submit doctor's HITL approval or rejection.
 *
 * @param {string} session_id
 * @param {string} decision  - 'approved' or 'rejected'
 * @param {string} comments  - Doctor's notes
 * @returns {Promise<{session_id, decision, message}>}
 */
async function submitApproval(session_id, decision, comments = '') {
    return await apiCall(`/research/${session_id}/approve`, 'POST', {
        decision,
        comments
    });
}


/**
 * Get the final research report for a completed session.
 *
 * @param {string} session_id
 * @returns {Promise<{final_report, confidence_score, sources, ...}>}
 */
async function getReport(session_id) {
    return await apiCall(`/research/${session_id}/report`);
}


// ════════════════════════════════════════════════════════════
// SESSION API
// ════════════════════════════════════════════════════════════

/**
 * List all past research sessions.
 *
 * @param {number} limit  - Max sessions to return (default 20)
 * @param {number} offset - Pagination offset (default 0)
 * @returns {Promise<{sessions, total}>}
 */
async function listSessions(limit = 20, offset = 0) {
    return await apiCall(`/sessions?limit=${limit}&offset=${offset}`);
}


/**
 * Search sessions by keyword.
 *
 * @param {string} query - Search keyword
 * @returns {Promise<{sessions, total}>}
 */
async function searchSessions(query) {
    return await apiCall(`/sessions/search?q=${encodeURIComponent(query)}`);
}


/**
 * Get full details of a specific past session.
 *
 * @param {string} session_id
 * @returns {Promise<SessionDetailResponse>}
 */
async function getSession(session_id) {
    return await apiCall(`/sessions/${session_id}`);
}


/**
 * Delete a session from the database.
 *
 * @param {string} session_id
 * @returns {Promise<{session_id, deleted}>}
 */
async function deleteSession(session_id) {
    return await apiCall(`/sessions/${session_id}`, 'DELETE');
}


// ════════════════════════════════════════════════════════════
// EXPORT API
// ════════════════════════════════════════════════════════════

/**
 * Generate a PDF report for a session.
 *
 * @param {string} session_id
 * @returns {Promise<{file_path, download_url, status}>}
 */
async function exportPDF(session_id) {
    return await apiCall('/export/pdf', 'POST', { session_id });
}


/**
 * Generate a Word document for a session.
 *
 * @param {string} session_id
 * @returns {Promise<{file_path, download_url, status}>}
 */
async function exportWord(session_id) {
    return await apiCall('/export/word', 'POST', { session_id });
}


/**
 * Check export status for a session.
 *
 * @param {string} session_id
 * @returns {Promise<{pdf_ready, word_ready, pdf_path, word_path}>}
 */
async function getExportStatus(session_id) {
    return await apiCall(`/export/status/${session_id}`);
}


/**
 * Get direct download URL for an export file.
 *
 * @param {string} session_id
 * @param {string} format - 'pdf' or 'word'
 * @returns {string} - Full download URL
 */
function getDownloadURL(session_id, format) {
    return `${API_BASE}/export/download/${session_id}/${format}`;
}


// ════════════════════════════════════════════════════════════
// HEALTH CHECK
// ════════════════════════════════════════════════════════════

/**
 * Check API health and service connectivity.
 *
 * @returns {Promise<{status, version, services}>}
 */
async function checkHealth() {
    return await apiCall('/health');
}


// ════════════════════════════════════════════════════════════
// POLLING HELPER
// ════════════════════════════════════════════════════════════

/**
 * Poll research status every N seconds until a condition is met.
 * Automatically stops when status is 'paused', 'completed', or 'failed'.
 *
 * @param {string}   session_id    - Session to poll
 * @param {function} onUpdate      - Called on every status update
 * @param {function} onPaused      - Called when HITL pause is reached
 * @param {function} onCompleted   - Called when research completes
 * @param {function} onError       - Called on error
 * @param {number}   intervalMs    - Polling interval in ms (default 3000)
 */
function pollResearchStatus(
    session_id,
    onUpdate,
    onPaused,
    onCompleted,
    onError,
    intervalMs = 3000
) {
    const interval = setInterval(async () => {
        try {
            const status = await getResearchStatus(session_id);

            // Call update handler on every poll
            if (onUpdate) onUpdate(status);

            // Check for terminal states
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

    // Return the interval ID so caller can cancel if needed
    return interval;
}


// ════════════════════════════════════════════════════════════
// UTILITY HELPERS
// ════════════════════════════════════════════════════════════

/**
 * Format a confidence score into a human readable label.
 *
 * @param {number} score - 0 to 100
 * @returns {object} - { label, class }
 */
function formatConfidence(score) {
    if (score >= 80) return { label: 'High',   cssClass: 'high',   color: '#057a55' };
    if (score >= 60) return { label: 'Medium', cssClass: 'medium', color: '#c27803' };
    return               { label: 'Low',    cssClass: 'low',    color: '#c81e1e' };
}


/**
 * Format an ISO date string into a readable format.
 *
 * @param {string} isoString - ISO date string
 * @returns {string} - e.g. "March 19, 2026 at 14:30"
 */
function formatDate(isoString) {
    if (!isoString) return 'Unknown date';
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
        year:  'numeric',
        month: 'long',
        day:   'numeric',
        hour:  '2-digit',
        minute: '2-digit'
    });
}


/**
 * Get the Bootstrap badge class for a focus area.
 *
 * @param {string} focusArea - general / disease / drug / news
 * @returns {string} - CSS class name
 */
function getFocusBadgeClass(focusArea) {
    const map = {
        disease: 'badge-disease',
        drug:    'badge-drug',
        news:    'badge-news',
        general: 'badge-general'
    };
    return map[focusArea] || 'badge-general';
}


/**
 * Convert Markdown text to basic HTML for display.
 * Simple parser — handles headings, bold, bullets, dividers.
 *
 * @param {string} markdown - Markdown string
 * @returns {string} - HTML string
 */
function markdownToHTML(markdown) {
    if (!markdown) return '';

    let html = markdown
        // H1
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        // H2
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        // H3
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        // Bold
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Bullet points
        .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
        // Horizontal rule
        .replace(/^---$/gm, '<hr>')
        // Line breaks
        .replace(/\n\n/g, '</p><p>')
        // Wrap consecutive li in ul
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

    return `<div class="report-content"><p>${html}</p></div>`;
}


/**
 * Show a toast notification.
 *
 * @param {string} message - Message to show
 * @param {string} type    - 'success', 'danger', 'warning', 'info'
 */
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 8px;
        `;
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.style.cssText = `
        background: white;
        border-left: 4px solid ${
            type === 'success' ? '#057a55' :
            type === 'danger'  ? '#c81e1e' :
            type === 'warning' ? '#c27803' : '#1a56db'
        };
        border-radius: 8px;
        padding: 12px 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        font-size: 0.875rem;
        max-width: 320px;
        animation: slideIn 0.3s ease;
    `;
    toast.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px;">
            <span>${
                type === 'success' ? '✅' :
                type === 'danger'  ? '❌' :
                type === 'warning' ? '⚠️' : 'ℹ️'
            }</span>
            <span>${message}</span>
        </div>
    `;

    container.appendChild(toast);

    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}