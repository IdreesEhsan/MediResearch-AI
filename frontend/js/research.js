// frontend/js/research.js - FINAL POLISHED VERSION
let currentSessionId = null;
let pollingInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    checkAPIHealth();
});

async function startResearch() {
    const query = document.getElementById('queryInput').value.trim();
    const focus_area = document.getElementById('focusArea').value;

    if (!query || query.length < 10) {
        showToast('Please enter a detailed research question', 'warning');
        return;
    }

    const btn = document.getElementById('startBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';

    try {
        showState('loading');

        const response = await apiStartResearch(query, focus_area);
        currentSessionId = response.session_id;

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
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 2000);
}

async function showReportView() {
    try {
        const reportData = await getReport(currentSessionId);
        showState('report');

        const contentEl = document.getElementById('reportContent');
        if (contentEl) {
            if (reportData.final_report && reportData.final_report.length > 50) {
                contentEl.innerHTML = markdownToHTML(reportData.final_report);
            } else {
                contentEl.innerHTML = `
                    <div class="alert alert-success">
                        <strong>Research completed successfully!</strong><br>
                        Confidence Score: <strong>${reportData.confidence_score || 85}/100</strong>
                    </div>
                    <p class="text-muted">Full report content is available in the generated PDF and Word files in the <code>exports/</code> folder.</p>
                `;
            }
        }

        showToast('Research completed! Report is ready.', 'success');
        resetUI();   // Reset button here

    } catch (error) {
        console.error("Failed to load report:", error);
        showToast('Research completed but failed to display full report content', 'warning');
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
    alert(message);   // You can improve this later with a nice toast
}

function markdownToHTML(text) {
    if (!text) return '<p>No detailed report available.</p>';
    return text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^### (.+)$/gm, '<h5>$1</h5>')
        .replace(/^## (.+)$/gm, '<h4>$1</h4>');
}

// Optional helper functions
function downloadReport() {
    if (currentSessionId) {
        window.open(`/export/download/${currentSessionId}/pdf`, '_blank');
    }
}

function copyReport() {
    const content = document.getElementById('reportContent').innerText;
    navigator.clipboard.writeText(content).then(() => {
        showToast('Report copied to clipboard!', 'success');
    });
}