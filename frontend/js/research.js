// frontend/js/research.js - FINAL CLEAN VERSION
let currentSessionId = null;
let pollingInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    checkAPIHealth();
});

async function startResearch() {
    const query = document.getElementById('queryInput').value.trim();
    const focus_area = document.getElementById('focusArea').value;

    if (!query || query.length < 5) {
        showToast('Please enter a proper question', 'warning');
        return;
    }

    const btn = document.getElementById('startBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';

    try {
        showState('loading');

        const response = await apiStartResearch(query, focus_area);
        currentSessionId = response.session_id;

        // Handle non-medical queries
        if (response.session_id && response.session_id.startsWith("non_medical_")) {
            showToast(response.response || "This query is not medical-related.", 'info');
            resetUI();
            showState('welcome');
            return;
        }

        // Normal medical flow
        showToast('Research started successfully!', 'success');
        startPolling();

    } catch (error) {
        showToast(`Failed to start research: ${error.message}`, 'danger');
        resetUI();
    }
}

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
        try {
            const status = await getResearchStatus(currentSessionId);

            if (status.status === 'completed') {
                clearInterval(pollingInterval);
                await showReportView();
            }
        } catch (error) {
            console.error("Polling error:", error);
        }
    }, 2000);
}

async function showReportView() {
    try {
        const reportData = await getReport(currentSessionId);
        showState('report');

        const contentEl = document.getElementById('reportContent');
        if (contentEl) {
            if (reportData.final_report && reportData.final_report.length > 100) {
                contentEl.innerHTML = markdownToHTML(reportData.final_report);
            } else {
                contentEl.innerHTML = `
                    <div class="alert alert-success">
                        <strong>Research completed successfully!</strong><br><br>
                        Confidence: <strong>${reportData.confidence_score || 85}/100</strong>
                    </div>
                `;
            }
        }
        showToast('Research completed! Report is ready.', 'success');
        resetUI();

    } catch (error) {
        showToast('Research completed but failed to display full report', 'warning');
        resetUI();
    }
}

function showState(state) {
    document.getElementById('welcomeState').style.display = state === 'welcome' ? 'block' : 'none';
    document.getElementById('loadingState').style.display = state === 'loading' ? 'block' : 'none';
    document.getElementById('reportPanel').style.display = state === 'report' ? 'block' : 'none';
}

function resetUI() {
    const btn = document.getElementById('startBtn');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-fill"></i> Start Research';
    }
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
    const color = type === 'success' ? '#057a55' : type === 'danger' ? '#c81e1e' : '#1a56db';
    
    toast.style.cssText = `
        background: white;
        border-left: 4px solid ${color};
        border-radius: 8px;
        padding: 14px 18px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        font-size: 0.95rem;
        max-width: 340px;
    `;

    toast.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:1.3rem;">${type==='success' ? '✅' : type==='danger' ? '❌' : 'ℹ️'}</span>
            <span>${message}</span>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function markdownToHTML(text) {
    if (!text) return '<p>No detailed report available.</p>';
    return text.replace(/\n/g, '<br>');
}

// ====================== DOWNLOAD & COPY ======================
function downloadReport() {
    if (!currentSessionId) {
        showToast('No active session found. Please run a research first.', 'warning');
        return;
    }

    try {
        // Full absolute URL to avoid path issues
        const url = `http://localhost:8000/export/download/${currentSessionId}/pdf`;
        window.open(url, '_blank');
        showToast('Downloading PDF...', 'success');
    } catch (error) {
        showToast('Failed to start download. Please try again.', 'danger');
    }
}

function copyReport() {
    const contentEl = document.getElementById('reportContent');
    if (!contentEl) {
        showToast('No report content available', 'warning');
        return;
    }

    const text = contentEl.innerText || contentEl.textContent || '';

    if (!text || text.trim() === '') {
        showToast('No text to copy', 'warning');
        return;
    }

    navigator.clipboard.writeText(text).then(() => {
        showToast('Report copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy report to clipboard', 'danger');
    });
}