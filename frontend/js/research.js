// frontend/js/research.js
let currentSessionId = null;
let pollingInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
    await checkAPIHealth();

    // Load query from sessions page if continuing
    const continueQuery = sessionStorage.getItem('continueQuery');
    const continueFocus = sessionStorage.getItem('continueFocusArea');
    if (continueQuery) {
        document.getElementById('queryInput').value = continueQuery;
        document.getElementById('focusArea').value = continueFocus || 'general';
        sessionStorage.removeItem('continueQuery');
        sessionStorage.removeItem('continueFocusArea');
    }

    const savedSession = sessionStorage.getItem('currentSessionId');
    if (savedSession) {
        currentSessionId = savedSession;
        resumeSession(savedSession);
    }
});

async function checkAPIHealth() {
    const dot = document.getElementById('apiStatusDot');
    const text = document.getElementById('apiStatusText');
    try {
        await checkHealth();
        if (dot) dot.style.background = '#34d399';
        if (text) text.textContent = 'API Online';
    } catch (error) {
        if (dot) dot.style.background = '#f87171';
        if (text) text.textContent = 'API Offline';
    }
}

async function startResearch() {
    const query = document.getElementById('queryInput').value.trim();
    const focus_area = document.getElementById('focusArea').value;

    if (!query || query.length < 10) {
        showToast('Please enter a detailed research question (at least 10 characters)', 'warning');
        return;
    }

    const btn = document.getElementById('startBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';

    try {
        showState('loading');
        showProgressPanel();
        setLoadingMessage('Initializing agents...', 'Connecting to knowledge base');

        const response = await apiStartResearch(query, focus_area);
        currentSessionId = response.session_id;
        sessionStorage.setItem('currentSessionId', currentSessionId);

        showToast('Research started!', 'success');
        startPolling();

    } catch (error) {
        showToast(`Failed to start research: ${error.message}`, 'danger');
        resetStartButton();
        showState('welcome');
    }
}

function showProgressPanel() {
    const panel = document.getElementById('progressCard');
    if (panel) panel.style.display = 'block';
}

function setLoadingMessage(main, sub = '') {
    const mainEl = document.getElementById('loadingMessage');
    const subEl = document.getElementById('loadingSubMessage');
    if (mainEl) mainEl.textContent = main;
    if (subEl) subEl.textContent = sub;
}

function showState(state) {
    document.getElementById('welcomeState').style.display = state === 'welcome' ? 'block' : 'none';
    document.getElementById('loadingState').style.display = state === 'loading' ? 'block' : 'none';
    document.getElementById('hitlPanel').style.display = state === 'hitl' ? 'block' : 'none';
    document.getElementById('reportPanel').style.display = state === 'report' ? 'block' : 'none';
}

function resetStartButton() {
    const btn = document.getElementById('startBtn');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-fill"></i> Start Research';
    }
}

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
        try {
            const status = await getResearchStatus(currentSessionId);

            if (status.current_agent) {
                updateLoadingMessage(status.current_agent);
            }

            if (status.status === 'paused') {
                clearInterval(pollingInterval);
                await showHITLPanel();
            } else if (status.status === 'completed') {
                clearInterval(pollingInterval);
                await showReportPanel();
            } else if (status.status === 'failed') {
                clearInterval(pollingInterval);
                showToast('Research failed', 'danger');
                showState('welcome');
            }
        } catch (error) {
            console.error("Polling error:", error);
        }
    }, 2500); // Poll every 2.5 seconds
}

function updateLoadingMessage(agent) {
    const messages = {
        'memory_load': 'Loading prior context...',
        'search_agent': 'Searching the web...',
        'rag_agent': 'Querying knowledge base...',
        'news_agent': 'Fetching latest news...',
        'summarizer_agent': 'Synthesizing all sources...',
        'factcheck_agent': 'Fact-checking claims...',
        'hitl_node': 'Waiting for doctor review...',
        'report_agent': 'Generating final report...',
        'export_agent': 'Creating PDF and Word files...'
    };
    setLoadingMessage(messages[agent] || 'Processing...', '');
}

async function showHITLPanel() {
    showState('hitl');
    showToast('Research paused for doctor approval', 'warning');
}

async function showReportPanel() {
    showState('report');
    showToast('Research completed! Report ready.', 'success');
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
    toast.style.cssText = `background:white; border-left:4px solid ${type==='success'?'#057a55':type==='danger'?'#c81e1e':'#1a56db'}; border-radius:8px; padding:12px 16px; box-shadow:0 4px 12px rgba(0,0,0,0.15); max-width:320px;`;
    toast.innerHTML = `<div style="display:flex; align-items:center; gap:8px;"><span>${type==='success'?'✅':type==='danger'?'❌':'ℹ️'}</span><span>${message}</span></div>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}