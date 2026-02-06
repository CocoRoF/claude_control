/**
 * Claude Control Dashboard - JavaScript Application
 */

// Global state
const state = {
    sessions: [],
    selectedSessionId: null,
    isLoading: false,
    healthStatus: 'connecting',
    sidebarCollapsed: false,
    // Session-specific data cache
    sessionData: {} // { sessionId: { input: '', output: '', status: '', statusText: '' } }
};

// Get or initialize session data
function getSessionData(sessionId) {
    if (!state.sessionData[sessionId]) {
        state.sessionData[sessionId] = {
            input: '',
            output: 'No output yet',
            status: '',
            statusText: ''
        };
    }
    return state.sessionData[sessionId];
}

// Save current session's input to cache
function saveCurrentSessionInput() {
    if (state.selectedSessionId) {
        const data = getSessionData(state.selectedSessionId);
        data.input = document.getElementById('command-input').value;
    }
}

// API base URL
const API_BASE = '';

// ========== Utility Functions ==========

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    state.sidebarCollapsed = !state.sidebarCollapsed;

    if (state.sidebarCollapsed) {
        sidebar.classList.add('collapsed');
    } else {
        sidebar.classList.remove('collapsed');
    }

    // Save state to localStorage
    localStorage.setItem('sidebarCollapsed', state.sidebarCollapsed);
}

function initSidebarState() {
    // Check if we're on mobile
    const isMobile = window.innerWidth <= 768;

    if (isMobile) {
        // On mobile, start collapsed by default or restore saved state
        const savedState = localStorage.getItem('sidebarCollapsed');
        state.sidebarCollapsed = savedState === null ? true : savedState === 'true';

        const sidebar = document.getElementById('sidebar');
        if (state.sidebarCollapsed) {
            sidebar.classList.add('collapsed');
        }
    }
}

// ========== API Functions ==========

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

// ========== Session Management ==========

async function loadSessions() {
    try {
        state.sessions = await apiCall('/api/sessions');
        renderSessionList();
        updateSessionStats();
        updateBatchSessionList();
        syncCompanySessions();
    } catch (error) {
        showError('Failed to load sessions: ' + error.message);
    }
}

function renderSessionList() {
    const container = document.getElementById('session-list');

    if (state.sessions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No sessions yet</p>
            </div>
        `;
        return;
    }

    container.innerHTML = state.sessions.map(session => `
        <div class="session-item ${session.session_id === state.selectedSessionId ? 'selected' : ''}"
             onclick="selectSession('${session.session_id}')">
            <span class="session-status-dot ${session.status}"></span>
            <div class="session-info">
                <div class="session-name">${session.session_name || 'Unnamed'}</div>
                <div class="session-id">${session.session_id.substring(0, 8)}...</div>
            </div>
            <div class="session-actions">
                <button class="btn btn-icon btn-sm" onclick="event.stopPropagation(); showDeleteConfirmation('${session.session_id}', '${session.session_name || session.session_id}')" title="Delete">
                    ✕
                </button>
            </div>
        </div>
    `).join('');
}

function updateSessionStats() {
    const total = state.sessions.length;
    const running = state.sessions.filter(s => s.status === 'running').length;
    const error = state.sessions.filter(s => s.status === 'error').length;

    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-running').textContent = running;
    document.getElementById('stat-error').textContent = error;
}

function selectSession(sessionId) {
    // Save current session's input before switching
    saveCurrentSessionInput();

    // Update selected session
    state.selectedSessionId = sessionId;
    renderSessionList();

    const session = state.sessions.find(s => s.session_id === sessionId);
    if (session) {
        showCommandPanel(session);
        showLogsPanel(session);
    }
}

function showCommandPanel(session) {
    document.getElementById('no-session-message').classList.add('hidden');
    document.getElementById('command-panel').classList.remove('hidden');

    const infoContainer = document.getElementById('selected-session-info');
    infoContainer.innerHTML = `
        <h4>${session.session_name || 'Unnamed Session'}</h4>
        <div class="session-meta">
            <span>ID: ${session.session_id.substring(0, 8)}...</span>
            <span>Status: ${session.status}</span>
            <span>Model: ${session.model || 'Default'}</span>
            ${session.pod_name ? `<span>Pod: ${session.pod_name}</span>` : ''}
        </div>
    `;

    // Restore session-specific input and output
    const sessionData = getSessionData(session.session_id);
    document.getElementById('command-input').value = sessionData.input;
    document.getElementById('command-output').textContent = sessionData.output;

    // Restore execution status
    const statusEl = document.getElementById('execution-status');
    statusEl.textContent = sessionData.statusText;
    statusEl.className = 'execution-status ' + sessionData.status;
}

function showLogsPanel(session) {
    document.getElementById('no-session-logs-message').classList.add('hidden');
    document.getElementById('logs-panel').classList.remove('hidden');

    // Update title
    document.getElementById('logs-session-title').textContent =
        `Logs: ${session.session_name || session.session_id.substring(0, 8)}`;

    // Load logs for selected session
    loadSessionLogs();
}

async function createSession() {
    const name = document.getElementById('new-session-name').value;
    const model = document.getElementById('new-session-model').value;
    const maxTurns = parseInt(document.getElementById('new-session-max-turns').value) || 50;
    const autonomous = document.getElementById('new-session-autonomous').checked;

    try {
        const payload = {
            session_name: name || undefined,
            model: model || undefined,
            max_turns: maxTurns,
            autonomous: autonomous
        };

        await apiCall('/api/sessions', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        hideCreateSessionModal();
        await loadSessions();
        showSuccess('Session created successfully');
    } catch (error) {
        showError('Failed to create session: ' + error.message);
    }
}

let sessionToDelete = null;

function showDeleteConfirmation(sessionId, sessionName) {
    sessionToDelete = sessionId;
    document.getElementById('delete-session-name').textContent = sessionName;
    document.getElementById('delete-session-modal').classList.remove('hidden');
}

function hideDeleteSessionModal() {
    sessionToDelete = null;
    document.getElementById('delete-session-modal').classList.add('hidden');
}

async function confirmDeleteSession() {
    if (!sessionToDelete) return;

    try {
        await apiCall(`/api/sessions/${sessionToDelete}`, {
            method: 'DELETE'
        });

        // Clean up session data cache
        delete state.sessionData[sessionToDelete];

        if (state.selectedSessionId === sessionToDelete) {
            state.selectedSessionId = null;
            // Hide command panel
            document.getElementById('no-session-message').classList.remove('hidden');
            document.getElementById('command-panel').classList.add('hidden');
            // Hide logs panel
            document.getElementById('no-session-logs-message').classList.remove('hidden');
            document.getElementById('logs-panel').classList.add('hidden');
            // Clear input field
            document.getElementById('command-input').value = '';
        }

        hideDeleteSessionModal();
        await loadSessions();
        showSuccess('Session deleted successfully');
    } catch (error) {
        showError('Failed to delete session: ' + error.message);
    }
}

// ========== Command Execution ==========

async function executeCommand() {
    if (!state.selectedSessionId) {
        showError('Please select a session first');
        return;
    }

    const prompt = document.getElementById('command-input').value.trim();
    if (!prompt) {
        showError('Please enter a prompt');
        return;
    }

    const timeout = parseInt(document.getElementById('command-timeout').value) || 600;
    const maxTurns = parseInt(document.getElementById('command-max-turns').value) || null;
    const skipPermissions = document.getElementById('skip-permissions').checked;

    setExecutionStatus('running', 'Executing...');

    try {
        const result = await apiCall(`/api/sessions/${state.selectedSessionId}/execute`, {
            method: 'POST',
            body: JSON.stringify({
                prompt: prompt,
                timeout: timeout,
                max_turns: maxTurns,
                skip_permissions: skipPermissions
            })
        });

        const sessionData = getSessionData(state.selectedSessionId);
        sessionData.input = prompt;

        if (result.success) {
            const statusText = `Completed in ${result.duration_ms}ms`;
            setExecutionStatus('success', statusText);
            const output = result.output || 'No output';
            document.getElementById('command-output').textContent = output;

            // Save to session data
            sessionData.output = output;
            sessionData.status = 'success';
            sessionData.statusText = statusText;
        } else {
            setExecutionStatus('error', 'Failed');
            const output = result.error || 'Unknown error';
            document.getElementById('command-output').textContent = output;

            // Save to session data
            sessionData.output = output;
            sessionData.status = 'error';
            sessionData.statusText = 'Failed';
        }
    } catch (error) {
        setExecutionStatus('error', 'Error');
        document.getElementById('command-output').textContent = error.message;

        // Save to session data
        const sessionData = getSessionData(state.selectedSessionId);
        sessionData.output = error.message;
        sessionData.status = 'error';
        sessionData.statusText = 'Error';
    }
}

function setExecutionStatus(status, text) {
    const statusEl = document.getElementById('execution-status');
    statusEl.textContent = text;
    statusEl.className = 'execution-status ' + status;
}

function clearOutput() {
    if (state.selectedSessionId) {
        const sessionData = getSessionData(state.selectedSessionId);
        sessionData.output = 'No output yet';
        sessionData.status = '';
        sessionData.statusText = '';
    }
    document.getElementById('command-output').textContent = 'No output yet';
    setExecutionStatus('', '');
}

// ========== Logs ==========

async function loadSessionLogs() {
    const sessionId = state.selectedSessionId;
    const levelFilter = document.getElementById('log-level-filter').value;
    const container = document.getElementById('logs-content');

    if (!sessionId) {
        container.innerHTML = `
            <div class="empty-state">
                <p>Select a session to view logs</p>
            </div>
        `;
        return;
    }

    // Show loading
    container.innerHTML = '<div class="loading">Loading logs...</div>';

    try {
        let url = `/api/command/logs/${sessionId}?limit=200`;
        if (levelFilter) {
            url += `&level=${levelFilter}`;
        }

        const result = await apiCall(url);

        if (result.entries.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No logs found</p>
                </div>
            `;
            return;
        }

        container.innerHTML = result.entries.map(entry => `
            <div class="log-entry">
                <span class="log-timestamp">${formatTimestamp(entry.timestamp)}</span>
                <span class="log-level ${entry.level}">${entry.level}</span>
                <span class="log-message">${escapeHtml(entry.message)}</span>
            </div>
        `).join('');

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        container.innerHTML = `
            <div class="empty-state">
                <p>Failed to load logs: ${error.message}</p>
            </div>
        `;
    }
}

// ========== Batch Execution ==========

function updateBatchSessionList() {
    const container = document.getElementById('batch-session-list');

    if (state.sessions.length === 0) {
        container.innerHTML = '<p class="text-muted">No sessions available</p>';
        return;
    }

    container.innerHTML = state.sessions
        .filter(s => s.status === 'running')
        .map(s => `
            <label class="batch-session-item">
                <input type="checkbox" value="${s.session_id}" checked>
                <span>${s.session_name || s.session_id.substring(0, 8)}</span>
            </label>
        `).join('');
}

function selectAllSessions() {
    document.querySelectorAll('#batch-session-list input[type="checkbox"]').forEach(cb => {
        cb.checked = true;
    });
}

function deselectAllSessions() {
    document.querySelectorAll('#batch-session-list input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
}

async function executeBatchCommand() {
    const selectedSessions = Array.from(
        document.querySelectorAll('#batch-session-list input[type="checkbox"]:checked')
    ).map(cb => cb.value);

    if (selectedSessions.length === 0) {
        showError('Please select at least one session');
        return;
    }

    const prompt = document.getElementById('batch-command-input').value.trim();
    if (!prompt) {
        showError('Please enter a command');
        return;
    }

    const timeout = parseInt(document.getElementById('batch-timeout').value) || 600;
    const parallel = document.getElementById('batch-parallel').checked;

    const resultsContainer = document.getElementById('batch-results');
    resultsContainer.innerHTML = '<div class="loading">Executing batch command...</div>';

    try {
        const result = await apiCall('/api/command/batch', {
            method: 'POST',
            body: JSON.stringify({
                session_ids: selectedSessions,
                prompt: prompt,
                timeout: timeout,
                parallel: parallel,
                skip_permissions: true
            })
        });

        renderBatchResults(result);
    } catch (error) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <p>Batch execution failed: ${error.message}</p>
            </div>
        `;
    }
}

function renderBatchResults(result) {
    const container = document.getElementById('batch-results');

    const summary = `
        <div class="batch-summary">
            <strong>Summary:</strong> ${result.successful}/${result.total_sessions} successful
            | Total time: ${result.total_duration_ms}ms
        </div>
    `;

    const results = result.results.map(r => `
        <div class="batch-result-item ${r.success ? 'success' : 'failed'}">
            <div class="batch-result-header">
                <strong>${getSessionName(r.session_id)}</strong>
                <span class="result-badge ${r.success ? 'success' : 'failed'}">${r.success ? 'Success' : 'Failed'}</span>
            </div>
            <div class="batch-result-output">
                ${escapeHtml(r.success ? (r.output || 'No output') : (r.error || 'Unknown error'))}
            </div>
            ${r.duration_ms ? `<small class="text-muted">Duration: ${r.duration_ms}ms</small>` : ''}}
        </div>
    `).join('');

    container.innerHTML = summary + results;
}

function getSessionName(sessionId) {
    const session = state.sessions.find(s => s.session_id === sessionId);
    return session ? (session.session_name || sessionId.substring(0, 8)) : sessionId.substring(0, 8);
}

// ========== Health Check ==========

async function checkHealth() {
    try {
        const health = await apiCall('/health');
        updateHealthIndicator('connected', `${health.total_sessions} sessions`);
    } catch (error) {
        updateHealthIndicator('disconnected', 'Disconnected');
    }
}

function updateHealthIndicator(status, text) {
    const indicator = document.getElementById('health-indicator');
    const dot = indicator.querySelector('.health-dot');
    const textEl = indicator.querySelector('.health-text');

    dot.className = 'health-dot ' + status;
    textEl.textContent = text;
}

// ========== Tab Navigation ==========

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.toggle('active', pane.id === `${tabName}-tab`);
    });

    // Refresh data if needed
    if (tabName === 'logs' && state.selectedSessionId) {
        loadSessionLogs();
    }

    // Initialize or sync company view
    if (tabName === 'company') {
        initCompanyView();
    }
}

// ========== Company View ==========

let _companyInitialized = false;

function initCompanyView() {
    if (_companyInitialized) {
        // Just sync sessions
        syncCompanySessions();
        return;
    }

    const container = document.getElementById('company-canvas');
    const loading = document.getElementById('company-loading');
    if (!container) return;

    // Check if PixiJS is loaded
    if (typeof PIXI === 'undefined') {
        if (loading) loading.querySelector('.company-loading-text').textContent = 'Loading PixiJS...';
        console.error('PixiJS not loaded');
        return;
    }

    // Wait a frame for the tab to become visible and sized
    requestAnimationFrame(() => {
        try {
            const scene = window.CompanyView.getInstance();
            scene.mount(container).then(() => {
                _companyInitialized = true;
                if (loading) loading.style.display = 'none';

                // Initial session sync
                syncCompanySessions();

                // Listen for avatar clicks
                document.addEventListener('company-avatar-click', (e) => {
                    const sessionId = e.detail.sessionId;
                    selectSession(sessionId);
                    switchTab('command');
                });
            });
        } catch (err) {
            console.error('Failed to init company view:', err);
            if (loading) {
                loading.querySelector('.company-loading-text').textContent = 'Failed to initialize';
            }
        }
    });
}

function syncCompanySessions() {
    if (!_companyInitialized) return;
    const scene = window.CompanyView.getInstance();
    if (scene && scene.isInitialized) {
        scene.syncSessions(state.sessions);

        // Update UI
        const countEl = document.getElementById('company-session-count');
        if (countEl) {
            countEl.textContent = `${state.sessions.length} worker${state.sessions.length !== 1 ? 's' : ''}`;
        }

        const emptyState = document.getElementById('company-empty-state');
        if (emptyState) {
            emptyState.style.display = state.sessions.length === 0 ? 'block' : 'none';
        }

        // Update status overlay
        updateCompanyStatusOverlay();
    }
}

function updateCompanyStatusOverlay() {
    const overlay = document.getElementById('company-status-overlay');
    if (!overlay) return;

    const running = state.sessions.filter(s => s.status === 'running').length;
    const idle = state.sessions.filter(s => s.status !== 'running' && s.status !== 'error').length;
    const errors = state.sessions.filter(s => s.status === 'error').length;

    let html = '';
    if (running > 0) {
        html += `<div class="company-status-item"><span class="company-status-dot running"></span>${running} working</div>`;
    }
    if (idle > 0) {
        html += `<div class="company-status-item"><span class="company-status-dot idle"></span>${idle} idle</div>`;
    }
    if (errors > 0) {
        html += `<div class="company-status-item"><span class="company-status-dot error"></span>${errors} error</div>`;
    }
    overlay.innerHTML = html;
}

function companyZoomIn() {
    const scene = window.CompanyView.getInstance();
    if (scene) scene.zoomIn();
}

function companyZoomOut() {
    const scene = window.CompanyView.getInstance();
    if (scene) scene.zoomOut();
}

function companyResetView() {
    const scene = window.CompanyView.getInstance();
    if (scene) scene.resetView();
}

// ========== Modals ==========

function showCreateSessionModal() {
    document.getElementById('create-session-modal').classList.remove('hidden');
    document.getElementById('new-session-name').value = '';
    document.getElementById('new-session-model').value = '';
    document.getElementById('new-session-max-turns').value = '50';
    document.getElementById('new-session-autonomous').checked = true;
}

function hideCreateSessionModal() {
    document.getElementById('create-session-modal').classList.add('hidden');
}

// ========== Utility Functions ==========

function formatTimestamp(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch {
        return isoString;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(message) {
    console.error(message);
    // Could implement toast notifications here
    alert('Error: ' + message);
}

function showSuccess(message) {
    console.log(message);
    // Could implement toast notifications here
}

async function refreshAll() {
    await loadSessions();
    await checkHealth();
}

// ========== Initialization ==========

document.addEventListener('DOMContentLoaded', () => {
    // Initialize sidebar state for mobile
    initSidebarState();

    // Initial load
    refreshAll();

    // Periodic refresh
    setInterval(checkHealth, 30000); // Health check every 30s
    setInterval(loadSessions, 60000); // Session list every 60s

    // Handle resize events
    window.addEventListener('resize', () => {
        const isMobile = window.innerWidth <= 768;
        const sidebar = document.getElementById('sidebar');

        if (!isMobile) {
            // Reset sidebar state on desktop
            sidebar.classList.remove('collapsed');
            state.sidebarCollapsed = false;
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + Enter to execute command
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
            if (activeTab === 'command') {
                executeCommand();
            } else if (activeTab === 'batch') {
                executeBatchCommand();
            }
        }

        // Escape to close modals
        if (e.key === 'Escape') {
            hideCreateSessionModal();
            hideDeleteSessionModal();
        }
    });
});
