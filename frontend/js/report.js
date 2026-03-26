// ============================================================
// frontend/js/report.js
// ============================================================
// Report page logic — handles:
//   - Loading and displaying individual reports
//   - Downloading PDF/Word exports
//   - Copying report content
//   - Printing reports
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
    await checkAPIHealth();

    // Get session ID from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');

    if (!sessionId) {
        showError('No session ID provided');
        return;
    }

    await loadReport(sessionId);
});

// ── API Health Check ──────────────────────────────────────────
async function checkAPIHealth() {
    const dot  = document.getElementById('apiStatusDot');
    const text = document.getElementById('apiStatusText');

    try {
        const health = await checkHealth();
        if (dot) dot.style.background = '#34d399';
        if (text) text.textContent = 'API Online';
        console.log("✅ API Status: Online");
    } catch (error) {
        if (dot) dot.style.background = '#f87171';
        if (text) text.textContent = 'API Offline';
        console.warn("⚠️ API Status: Offline -", error.message);
        // Optional: show toast only once
        if (!window.apiStatusToastShown) {
            showToast('Cannot connect to API. Make sure backend is running on port 8000.', 'warning');
            window.apiStatusToastShown = true;
        }
    }
}

// ── Load Report ───────────────────────────────────────────────
async function loadReport(sessionId) {
    try {
        // Show loading state
        showLoading(true);
        hideError();

        // Fetch report data
        const report = await getReport(sessionId);

        // Update page title and meta
        document.title = `Report: ${report.query.substring(0, 50)}... — MediResearch AI`;
        document.getElementById('reportTitle').textContent = `Report: ${report.query}`;
        document.getElementById('reportSubtitle').textContent =
            `Generated on ${formatDate(report.created_at || new Date().toISOString())}`;

        // Update confidence score
        const score      = report.confidence_score || 0;
        const confidence = formatConfidence(score);

        const circle = document.getElementById('confidenceCircle');
        const scoreEl = document.getElementById('confidenceScore');
        const labelEl = document.getElementById('confidenceLabel');

        if (scoreEl) scoreEl.textContent = score;
        if (labelEl) labelEl.textContent = `${confidence.label} Confidence`;
        if (circle) circle.className = `confidence-circle mx-auto mb-2 ${confidence.cssClass}`;

        // Update focus area badge
        const focusBadge = document.getElementById('focusAreaBadge');
        if (focusBadge) {
            focusBadge.textContent = report.focus_area;
            focusBadge.className = `badge-focus ${getFocusBadgeClass(report.focus_area)}`;
        }

        // Update source count
        const sourceCount = document.getElementById('sourceCount');
        if (sourceCount) sourceCount.textContent = report.sources?.length || 0;

        // Update session ID
        const sessionIdShort = document.getElementById('sessionIdShort');
        if (sessionIdShort) sessionIdShort.textContent = sessionId.substring(0, 8) + '...';

        // Render report content
        const reportBody = document.getElementById('reportBody');
        if (reportBody) {
            reportBody.innerHTML = markdownToHTML(report.final_report);
        }

        // Render sources if available
        if (report.sources && report.sources.length > 0) {
            const sourcesCard = document.getElementById('sourcesCard');
            const sourcesList = document.getElementById('sourcesList');

            if (sourcesCard && sourcesList) {
                sourcesList.innerHTML = report.sources.map((source, i) =>
                    `<li><a href="${source}" target="_blank" rel="noopener">${source}</a></li>`
                ).join('');
                sourcesCard.style.display = 'block';
            }
        }

        // Hide loading, show content
        showLoading(false);

        showToast('Report loaded successfully', 'success');

    } catch (error) {
        showLoading(false);
        showError(`Failed to load report: ${error.message}`);
        console.error('Report loading error:', error);
    }
}

// ── Download Report ───────────────────────────────────────────
async function downloadReport(format) {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');

    if (!sessionId) {
        showToast('No session ID available', 'danger');
        return;
    }

    const btnId = format === 'pdf' ? 'pdfBtn' : 'wordBtn';
    const btn   = document.getElementById(btnId);

    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Generating...`;
    }

    try {
        // Request export generation
        if (format === 'pdf') {
            await exportPDF(sessionId);
        } else {
            await exportWord(sessionId);
        }

        // Trigger browser download
        const url = getDownloadURL(sessionId, format);
        window.open(url, '_blank');

        showToast(`${format.toUpperCase()} downloaded successfully!`, 'success');

    } catch (error) {
        showToast(`Export failed: ${error.message}`, 'danger');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = format === 'pdf'
                ? '<i class="bi bi-file-earmark-pdf-fill text-danger"></i> Download PDF'
                : '<i class="bi bi-file-earmark-word-fill text-primary"></i> Download Word';
        }
    }
}

// ── Copy Report ───────────────────────────────────────────────
async function copyReport() {
    const reportBody = document.getElementById('reportBody');

    if (!reportBody) {
        showToast('No report content to copy', 'warning');
        return;
    }

    try {
        // Get plain text content (remove HTML tags)
        const textContent = reportBody.textContent || reportBody.innerText || '';

        await navigator.clipboard.writeText(textContent);

        const copyBtn = document.getElementById('copyBtn');
        if (copyBtn) {
            const originalHTML = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
            copyBtn.classList.add('btn-success');
            copyBtn.classList.remove('btn-sm');

            setTimeout(() => {
                copyBtn.innerHTML = originalHTML;
                copyBtn.classList.remove('btn-success');
                copyBtn.classList.add('btn-sm');
            }, 2000);
        }

        showToast('Report copied to clipboard', 'success');

    } catch (error) {
        showToast('Failed to copy report', 'danger');
        console.error('Copy error:', error);
    }
}

// ── Print Report ──────────────────────────────────────────────
function printReport() {
    window.print();
}

// ── UI Helpers ────────────────────────────────────────────────
function showLoading(show) {
    const loadingEl = document.getElementById('loadingState');
    const contentEl  = document.getElementById('reportContent');

    if (loadingEl) loadingEl.style.display = show ? 'block' : 'none';
    if (contentEl) contentEl.style.display = show ? 'none' : 'block';
}

function showError(message) {
    const errorEl = document.getElementById('errorState');
    const errorMsg = document.getElementById('errorMessage');

    if (errorMsg) errorMsg.textContent = message;
    if (errorEl) errorEl.style.display = 'block';

    const loadingEl = document.getElementById('loadingState');
    const contentEl  = document.getElementById('reportContent');

    if (loadingEl) loadingEl.style.display = 'none';
    if (contentEl) contentEl.style.display = 'none';
}

function hideError() {
    const errorEl = document.getElementById('errorState');
    if (errorEl) errorEl.style.display = 'none';
}
