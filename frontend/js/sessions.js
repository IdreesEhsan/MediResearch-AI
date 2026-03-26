// ============================================================
// frontend/js/sessions.js
// ============================================================
// Sessions page logic — handles:
//   - Loading and displaying past sessions
//   - Searching and filtering sessions
//   - Viewing session details
//   - Deleting sessions
//   - Continuing research from a past session
// ============================================================


// ── State ─────────────────────────────────────────────────────
let allSessions      = [];   // All loaded sessions
let filteredSessions = [];   // After filter/search applied
let currentPage      = 0;   // Current pagination page
let currentFocus     = 'all'; // Active focus filter
let deleteTargetId   = null; // Session ID pending deletion
const PAGE_SIZE      = 10;   // Sessions per page


// ── On Page Load ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await checkAPIHealth();
    await loadSessions();
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


// ── Load All Sessions ─────────────────────────────────────────
async function loadSessions() {
    showLoading(true);
    try {
        const data    = await listSessions(100, 0); // Load up to 100
        allSessions      = data.sessions || [];
        filteredSessions = [...allSessions];
        currentPage      = 0;

        updateStats();
        renderSessions();

    } catch (error) {
        showToast(`Failed to load sessions: ${error.message}`, 'danger');
        showLoading(false);
        showEmpty(true);
    }
}


// ── Update Stats ──────────────────────────────────────────────
function updateStats() {
    const total    = allSessions.length;
    const approved = allSessions.filter(s => s.hitl_approved).length;
    const scores   = allSessions
        .filter(s => s.confidence_score)
        .map(s => s.confidence_score);
    const avg      = scores.length
        ? Math.round(scores.reduce((a,b) => a+b, 0) / scores.length)
        : 0;
    const reports  = allSessions.filter(s => s.has_report).length;

    document.getElementById('totalSessions').textContent  = total;
    document.getElementById('approvedSessions').textContent = approved;
    document.getElementById('avgConfidence').textContent  = avg ? `${avg}%` : '--';
    document.getElementById('withReports').textContent    = reports;
}


// ── Render Sessions List ──────────────────────────────────────
function renderSessions() {
    const container = document.getElementById('sessionsList');
    const countEl   = document.getElementById('sessionCount');

    showLoading(false);

    if (filteredSessions.length === 0) {
        showEmpty(true);
        if (countEl) countEl.textContent = '0';
        return;
    }

    showEmpty(false);
    if (countEl) countEl.textContent = filteredSessions.length;

    // Paginate
    const start    = currentPage * PAGE_SIZE;
    const end      = start + PAGE_SIZE;
    const paginated = filteredSessions.slice(start, end);

    // Build HTML
    container.innerHTML = paginated.map(session => `
        <div class="session-card mb-3"
            onclick="viewSession('${session.session_id}')">

            <div class="d-flex justify-content-between align-items-start mb-2">

                <!-- Query text -->
                <div class="session-query flex-fill me-2">
                    ${escapeHTML(session.query)}
                </div>

                <!-- Delete button -->
                <button
                    class="btn btn-sm btn-outline-danger flex-shrink-0"
                    style="padding:0.2rem 0.5rem; font-size:0.75rem;"
                    onclick="event.stopPropagation(); promptDelete('${session.session_id}', '${escapeHTML(session.query)}')"
                    title="Delete session"
                >
                    <i class="bi bi-trash"></i>
                </button>
            </div>

            <!-- Meta info row -->
            <div class="session-meta">

                <!-- Focus area badge -->
                <span class="badge-focus ${getFocusBadgeClass(session.focus_area)}">
                    ${getFocusIcon(session.focus_area)} ${session.focus_area}
                </span>

                <!-- Confidence -->
                ${session.confidence_score ? `
                    <span class="${getConfidenceTextClass(session.confidence_score)}">
                        <i class="bi bi-graph-up"></i>
                        ${session.confidence_score}/100
                    </span>
                ` : ''}

                <!-- Approval status -->
                ${session.hitl_approved !== null ? `
                    <span class="${session.hitl_approved ? 'text-success' : 'text-danger'}">
                        <i class="bi bi-${session.hitl_approved ? 'check-circle-fill' : 'x-circle-fill'}"></i>
                        ${session.hitl_approved ? 'Approved' : 'Rejected'}
                    </span>
                ` : ''}

                <!-- Has report -->
                ${session.has_report ? `
                    <span class="text-primary">
                        <i class="bi bi-file-earmark-text-fill"></i>
                        Report ready
                    </span>
                ` : ''}

                <!-- Date -->
                <span class="ms-auto">
                    <i class="bi bi-calendar3"></i>
                    ${formatDate(session.created_at)}
                </span>

            </div>
        </div>
    `).join('');

    updatePagination();
}


// ── View Session Detail ───────────────────────────────────────
async function viewSession(session_id) {
    const modal     = new bootstrap.Modal(document.getElementById('sessionModal'));
    const modalBody = document.getElementById('sessionModalBody');
    const continueBtn = document.getElementById('continueResearchBtn');

    modalBody.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-medical"></div>
            <p class="text-muted mt-2">Loading session...</p>
        </div>
    `;
    modal.show();

    try {
        const session = await getSession(session_id);

        const score = session.confidence_score || 0;
        const confidenceClass = score >= 80 ? 'text-success' : score >= 60 ? 'text-warning' : 'text-danger';

        modalBody.innerHTML = `

            <div class="d-flex align-items-center gap-3 mb-4">
                <div class="confidence-circle ${score >= 80 ? 'high' : score >= 60 ? 'medium' : 'low'}">
                    <span>${score}</span>
                    <span class="confidence-label">/ 100</span>
                </div>
                <div class="flex-fill">
                    <div class="fw-bold fs-6">${escapeHTML(session.query)}</div>
                    <div class="text-muted small mt-1">
                        <span class="badge-focus ${getFocusBadgeClass(session.focus_area)} me-2">
                            ${getFocusIcon(session.focus_area)} ${session.focus_area}
                        </span>
                        ${formatDate(session.created_at)}
                    </div>
                    <div class="mt-1">
                        <span class="text-success small">
                            <i class="bi bi-check-circle-fill"></i> Completed
                        </span>
                    </div>
                </div>
            </div>

            <div class="divider"></div>

            <!-- Summary -->
            ${session.summary ? `
                <div class="mb-4">
                    <div class="section-title">
                        <i class="bi bi-card-text"></i> Research Summary
                    </div>
                    <div class="summary-box">
                        ${escapeHTML(session.summary)}
                    </div>
                </div>
            ` : ''}

            <!-- Final Report -->
            ${session.final_report ? `
                <div>
                    <div class="section-title">
                        <i class="bi bi-file-earmark-medical-fill"></i> Final Report
                    </div>
                    <div class="report-box">
                        ${markdownToHTML(session.final_report)}
                    </div>
                </div>
            ` : `
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle"></i>
                    No detailed final report available for this session.
                </div>
            `}
        `;

        continueBtn.onclick = () => {
            continueResearch(session.query, session.focus_area);
            modal.hide();
        };

    } catch (error) {
        modalBody.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-circle-fill"></i>
                Failed to load session: ${error.message}
            </div>
        `;
    }
}

// ── Continue Research ─────────────────────────────────────────
function continueResearch(query, focus_area) {
    // Save query to session storage for the research page
    sessionStorage.setItem('continueQuery',     query);
    sessionStorage.setItem('continueFocusArea', focus_area);

    // Navigate to research page
    window.location.href = 'index.html';
}


// ── Delete Session ────────────────────────────────────────────
function promptDelete(session_id, query) {
    deleteTargetId = session_id;

    // Update modal info
    const infoEl = document.getElementById('deleteSessionInfo');
    if (infoEl) infoEl.textContent = `Query: "${query}"`;

    // Show confirmation modal
    const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
    modal.show();
}


async function confirmDelete() {
    if (!deleteTargetId) return;

    try {
        await deleteSession(deleteTargetId);

        // Remove from local arrays
        allSessions      = allSessions.filter(s => s.session_id !== deleteTargetId);
        filteredSessions = filteredSessions.filter(s => s.session_id !== deleteTargetId);

        // Close modal
        bootstrap.Modal.getInstance(
            document.getElementById('deleteModal')
        ).hide();

        // Re-render
        updateStats();
        renderSessions();

        showToast('Session deleted successfully', 'success');
        deleteTargetId = null;

    } catch (error) {
        showToast(`Delete failed: ${error.message}`, 'danger');
    }
}


// ── Search ────────────────────────────────────────────────────
function handleSearch(event) {
    // Search on Enter key
    if (event.key === 'Enter') {
        searchSessionsHandler();
    }
}


async function searchSessionsHandler() {
    const query = document.getElementById('searchInput').value.trim();

    if (!query) {
        clearSearch();
        return;
    }

    showLoading(true);

    try {
        const data = await searchSessions(query);
        filteredSessions = data.sessions || [];
        currentPage      = 0;

        // Update list title
        document.getElementById('listTitle').textContent =
            `Results for "${query}"`;

        renderSessions();

    } catch (error) {
        showToast(`Search failed: ${error.message}`, 'danger');
        showLoading(false);
    }
}


function clearSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('listTitle').textContent = 'All Sessions';
    filteredSessions = [...allSessions];

    // Re-apply focus filter if active
    if (currentFocus !== 'all') {
        filteredSessions = allSessions.filter(
            s => s.focus_area === currentFocus
        );
    }

    currentPage = 0;
    renderSessions();
}


// ── Filter by Focus Area ──────────────────────────────────────
function filterByFocus(focus, btnEl) {
    currentFocus = focus;

    // Update button states
    document.querySelectorAll('.card-body .btn-sm').forEach(btn => {
        btn.classList.remove('active', 'btn-outline-primary');
    });
    if (btnEl) btnEl.classList.add('active');

    // Apply filter
    if (focus === 'all') {
        filteredSessions = [...allSessions];
    } else {
        filteredSessions = allSessions.filter(s => s.focus_area === focus);
    }

    // Update title
    document.getElementById('listTitle').textContent =
        focus === 'all' ? 'All Sessions' : `${focus.charAt(0).toUpperCase() + focus.slice(1)} Sessions`;

    currentPage = 0;
    renderSessions();
}


// ── Sort Sessions ─────────────────────────────────────────────
function sortSessions(sortBy) {
    switch (sortBy) {
        case 'newest':
            filteredSessions.sort((a, b) =>
                new Date(b.created_at) - new Date(a.created_at));
            break;
        case 'oldest':
            filteredSessions.sort((a, b) =>
                new Date(a.created_at) - new Date(b.created_at));
            break;
        case 'confidence':
            filteredSessions.sort((a, b) =>
                (b.confidence_score || 0) - (a.confidence_score || 0));
            break;
    }
    currentPage = 0;
    renderSessions();
}


// ── Pagination ────────────────────────────────────────────────
function changePage(direction) {
    const maxPage = Math.ceil(filteredSessions.length / PAGE_SIZE) - 1;
    currentPage   = Math.max(0, Math.min(currentPage + direction, maxPage));
    renderSessions();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}


function updatePagination() {
    const total    = filteredSessions.length;
    const maxPage  = Math.ceil(total / PAGE_SIZE) - 1;
    const start    = currentPage * PAGE_SIZE + 1;
    const end      = Math.min((currentPage + 1) * PAGE_SIZE, total);
    const paginationEl = document.getElementById('pagination');
    const infoEl   = document.getElementById('paginationInfo');
    const prevBtn  = document.getElementById('prevBtn');
    const nextBtn  = document.getElementById('nextBtn');

    if (total > PAGE_SIZE) {
        paginationEl.style.display = 'flex';
        if (infoEl) infoEl.textContent = `Showing ${start}–${end} of ${total}`;
        if (prevBtn) prevBtn.disabled = currentPage === 0;
        if (nextBtn) nextBtn.disabled = currentPage >= maxPage;
    } else {
        paginationEl.style.display = 'none';
    }
}


// ── UI Helpers ────────────────────────────────────────────────
function showLoading(show) {
    const el = document.getElementById('sessionsLoading');
    if (el) el.style.display = show ? 'block' : 'none';
}


function showEmpty(show) {
    const el = document.getElementById('sessionsEmpty');
    if (el) el.style.display = show ? 'block' : 'none';
    if (show) {
        const list = document.getElementById('sessionsList');
        if (list) list.innerHTML = '';
    }
}


function getFocusIcon(focusArea) {
    const icons = {
        disease: '🦠',
        drug:    '💊',
        news:    '📰',
        general: '🔬'
    };
    return icons[focusArea] || '🔬';
}


function getConfidenceTextClass(score) {
    if (score >= 80) return 'text-success';
    if (score >= 60) return 'text-warning';
    return 'text-danger';
}


function escapeHTML(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}