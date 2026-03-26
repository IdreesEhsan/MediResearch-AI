// ============================================================
// frontend/js/research.js
// ============================================================
// Research page logic — handles:
//   - Starting a new research session
//   - Polling agent progress
//   - Displaying HITL approval panel
//   - Submitting doctor approval/rejection
//   - Rendering the final report
//   - Downloading PDF/Word exports
// ============================================================

// Store API function from api.js
const apiStartResearch = window.apiStartResearch || window.startResearch;

document.addEventListener('DOMContentLoaded', async () => {
    await checkAPIHealth();

    // ── NEW: Load continue research context if coming from sessions page
    const continueQuery = sessionStorage.getItem('continueQuery');
    const continueFocus = sessionStorage.getItem('continueFocusArea');
    if (continueQuery) {
        document.getElementById('queryInput').value    = continueQuery;
        document.getElementById('focusArea').value     = continueFocus || 'general';
        sessionStorage.removeItem('continueQuery');
        sessionStorage.removeItem('continueFocusArea');
        showToast('Query loaded from previous session', 'info');
    }

    // Check if returning to a session in progress
    const savedSession = sessionStorage.getItem('currentSessionId');
    if (savedSession) {
        currentSessionId = savedSession;
        resumeSession(savedSession);
    }
});

// ── State ─────────────────────────────────────────────────────
// Tracks the current active research session
let currentSessionId = null;
let pollingInterval  = null;


// ── On Page Load ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Check API health on load
    await checkAPIHealth();

    // Check if returning to a session in progress
    const savedSession = sessionStorage.getItem('currentSessionId');
    if (savedSession) {
        currentSessionId = savedSession;
        resumeSession(savedSession);
    }
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


// ── Start Research ────────────────────────────────────────────
async function startResearch() {
    const query      = document.getElementById('queryInput').value.trim();
    const focus_area = document.getElementById('focusArea').value;

    // Validate input
    if (!query) {
        showToast('Please enter a research question', 'warning');
        document.getElementById('queryInput').focus();
        return;
    }

    if (query.length < 10) {
        showToast('Please enter a more detailed question (at least 10 characters)', 'warning');
        return;
    }

    try {
        // Disable start button
        const btn   = document.getElementById('startBtn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';

        // Show progress panel
        showState('loading');
        showProgressPanel();
        setLoadingMessage('Initializing research agents...', 'Connecting to knowledge base');

        // Call API to start research via api.js helper
        const response = await apiStartResearch(query, focus_area);
        currentSessionId = response.session_id;

        // Save session ID for page refresh recovery
        sessionStorage.setItem('currentSessionId', currentSessionId);

        showToast('Research started successfully!', 'success');

        // Start polling for status updates
        startPolling();

    } catch (error) {
        showToast(`Failed to start research: ${error.message}`, 'danger');
        resetStartButton();
        showState('welcome');
    }
}


// ── Rename to avoid conflict with api.js ──────────────────────


// ── Start Polling ─────────────────────────────────────────────
function startPolling() {
    // Clear any existing polling
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = pollResearchStatus(
        currentSessionId,

        // onUpdate — called every 3 seconds
        (status) => {
            updateAgentProgress(status.current_agent);
            updateLoadingMessage(status.current_agent);
        },

        // onPaused — HITL pause reached
        async (status) => {
            updateAgentProgress('hitl_node');
            await showHITLPanel();
        },

        // onCompleted — research finished
        async (status) => {
            updateAgentProgress('done');
            await showReportPanel();
        },

        // onError
        (error) => {
            showToast(`Research error: ${error.message}`, 'danger');
            showState('welcome');
            resetStartButton();
        }
    );
}


// ── Resume Session ────────────────────────────────────────────
async function resumeSession(session_id) {
    try {
        const status = await getResearchStatus(session_id);

        showProgressPanel();

        if (status.status === 'paused') {
            await showHITLPanel();
        } else if (status.status === 'completed') {
            await showReportPanel();
        } else if (status.status === 'running') {
            showState('loading');
            startPolling();
        }
    } catch (error) {
        // Session expired or not found — clear it
        sessionStorage.removeItem('currentSessionId');
    }
}


// ── Update Agent Progress ─────────────────────────────────────
function updateAgentProgress(currentAgent) {
    // Map of agent name → step order
    const agentOrder = [
        'memory_load',
        'search_agent',
        'rag_agent',
        'news_agent',
        'summarizer_agent',
        'factcheck_agent',
        'hitl_node',
        'report_agent',
        'export_agent'
    ];

    const currentIndex = agentOrder.indexOf(currentAgent);

    agentOrder.forEach((agent, index) => {
        const step  = document.getElementById(`step-${agent}`);
        const badge = step?.querySelector('.agent-status-badge');

        if (!step) return;

        // Reset classes
        step.className = 'agent-step';

        if (index < currentIndex) {
            // Completed
            step.classList.add('completed');
            if (badge) {
                badge.className = 'agent-status-badge badge bg-success';
                badge.textContent = '✓ Done';
            }
        } else if (index === currentIndex) {
            // Currently running
            step.classList.add('active');
            if (badge) {
                badge.className = 'agent-status-badge badge bg-primary';
                badge.textContent = '⟳ Running';
            }
        }
        // Future steps remain unchanged (Waiting)
    });
}


// ── Loading Message Updates ───────────────────────────────────
function updateLoadingMessage(currentAgent) {
    const messages = {
        'memory_load':      ['Loading prior context...', 'Checking session history'],
        'search_agent':     ['Searching the web...', 'Tavily AI search in progress'],
        'rag_agent':        ['Querying knowledge base...', 'CRAG validation running'],
        'news_agent':       ['Fetching latest news...', 'Filtering last 90 days'],
        'summarizer_agent': ['Synthesizing all sources...', 'Merging research findings'],
        'factcheck_agent':  ['Validating claims...', 'Cross-referencing sources'],
        'hitl_node':        ['Awaiting doctor review...', 'Research paused for approval'],
        'report_agent':     ['Generating report...', 'Writing final analysis'],
        'export_agent':     ['Creating PDF & Word...', 'Almost done!'],
    };

    const [main, sub] = messages[currentAgent] || ['Processing...', 'Please wait'];
    setLoadingMessage(main, sub);
}


function setLoadingMessage(main, sub) {
    const mainEl = document.getElementById('loadingMessage');
    const subEl  = document.getElementById('loadingSubMessage');
    if (mainEl) mainEl.textContent = main;
    if (subEl)  subEl.textContent  = sub;
}


// ── Show HITL Panel ───────────────────────────────────────────
async function showHITLPanel() {
    try {
        // Get current status for confidence score
        const status = await getResearchStatus(currentSessionId);

        // Update confidence display
        const score      = status.confidence_score || 0;
        const confidence = formatConfidence(score);

        const circle = document.getElementById('confidenceCircle');
        const scoreEl = document.getElementById('confidenceScore');
        const labelEl = document.getElementById('confidenceLabel');

        if (scoreEl) scoreEl.textContent = score;
        if (labelEl) labelEl.textContent = `${confidence.label} Confidence — Review carefully`;
        if (circle) {
            circle.className = `confidence-circle ${confidence.cssClass}`;
        }

        // Try to load summary from session
        try {
            const session = await getSession(currentSessionId);
            const preview = document.getElementById('summaryPreview');
            if (preview && session.summary) {
                preview.textContent = session.summary;
            }
        } catch (e) {
            // Summary not available yet — that's OK
        }

        // Show HITL panel hide loading
        showState('hitl');

        // Update progress badge
        const badge = document.getElementById('progressBadge');
        if (badge) {
            badge.textContent   = '⏸ Awaiting Approval';
            badge.className     = 'badge bg-warning text-dark ms-auto';
        }

        showToast('Research complete — doctor review required', 'warning');

    } catch (error) {
        showToast(`Error loading HITL panel: ${error.message}`, 'danger');
    }
}


// ── Submit HITL Decision ──────────────────────────────────────
async function submitApprovalDecision(decision) {
    const comments = document.getElementById('doctorComments').value.trim();
    const approveBtn = document.querySelector('.btn-success');
    const rejectBtn  = document.querySelector('.btn-danger');

    // Disable buttons during submission
    if (approveBtn) approveBtn.disabled = true;
    if (rejectBtn)  rejectBtn.disabled  = true;

    try {
        showToast(
            decision === 'approved'
                ? 'Approving and generating report...'
                : 'Rejecting and sending for revision...',
            'info'
        );

        await submitApproval(currentSessionId, decision, comments);

        if (decision === 'approved') {
            // Show loading while report generates
            showState('loading');
            setLoadingMessage('Generating final report...', 'Report and export files being created');

            // Resume polling to wait for completion
            pollingInterval = pollResearchStatus(
                currentSessionId,
                (status) => updateAgentProgress(status.current_agent),
                null,
                async () => {
                    updateAgentProgress('done');
                    await showReportPanel();
                },
                (error) => showToast(error.message, 'danger')
            );

        } else {
            // Rejected — go back to loading for re-research
            showState('loading');
            setLoadingMessage('Revising based on doctor notes...', 'Agents are re-running');
            startPolling();
            showToast('Sent back for revision', 'warning');
        }

    } catch (error) {
        showToast(`Approval failed: ${error.message}`, 'danger');
        if (approveBtn) approveBtn.disabled = false;
        if (rejectBtn)  rejectBtn.disabled  = false;
    }
}


// ── Show Report Panel ─────────────────────────────────────────
async function showReportPanel() {
    try {
        const report = await getReport(currentSessionId);

        // Update confidence
        const score      = report.confidence_score || 0;
        const confidence = formatConfidence(score);

        const circle  = document.getElementById('reportConfidenceCircle');
        const scoreEl = document.getElementById('reportConfidenceScore');
        if (scoreEl) scoreEl.textContent = score;
        if (circle) circle.className = `confidence-circle ${confidence.cssClass}`;

        // Update meta info
        const queryEl = document.getElementById('reportQuery');
        const metaEl  = document.getElementById('reportMeta');
        if (queryEl) queryEl.textContent = report.query;
        if (metaEl) {
            metaEl.textContent =
                `${report.focus_area} · Confidence: ${score}/100 · ${report.sources?.length || 0} sources`;
        }

        // Render report content
        const contentEl = document.getElementById('reportContent');
        if (contentEl) {
            contentEl.innerHTML = markdownToHTML(report.final_report);
        }

        // Show report panel
        showState('report');

        // Update progress to all completed
        updateAgentProgress('done');

        const badge = document.getElementById('progressBadge');
        if (badge) {
            badge.textContent = '✅ Complete';
            badge.className   = 'badge bg-success ms-auto';
        }

        // Clear saved session
        sessionStorage.removeItem('currentSessionId');
        resetStartButton();

        showToast('Research complete! Report ready.', 'success');

    } catch (error) {
        showToast(`Error loading report: ${error.message}`, 'danger');
    }
}


// ── Download Export ───────────────────────────────────────────
async function downloadExport(format) {
    const btnId = format === 'pdf' ? 'exportPdfBtn' : 'exportWordBtn';
    const btn   = document.getElementById(btnId);

    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Generating...`;
    }

    try {
        // Request export generation
        if (format === 'pdf') {
            await exportPDF(currentSessionId);
        } else {
            await exportWord(currentSessionId);
        }

        // Trigger browser download
        const url = getDownloadURL(currentSessionId, format);
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


// ── UI State Manager ──────────────────────────────────────────
function showState(state) {
    // Hide all panels
    document.getElementById('welcomeState').style.display = 'none';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('hitlPanel').style.display    = 'none';
    document.getElementById('reportPanel').style.display  = 'none';

    // Show requested state
    switch (state) {
        case 'welcome':
            document.getElementById('welcomeState').style.display = 'block';
            break;
        case 'loading':
            document.getElementById('loadingState').style.display = 'block';
            break;
        case 'hitl':
            document.getElementById('hitlPanel').style.display = 'block';
            break;
        case 'report':
            document.getElementById('reportPanel').style.display = 'block';
            break;
    }
}


// ── Show Progress Panel ───────────────────────────────────────
function showProgressPanel() {
    document.getElementById('progressCard').style.display = 'block';
}


// ── Reset Start Button ────────────────────────────────────────
function resetStartButton() {
    const btn    = document.getElementById('startBtn');
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-play-fill"></i> Start Research';
}