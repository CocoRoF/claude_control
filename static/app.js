/**
 * Claude Control Dashboard - JavaScript Application
 */

// Global state
const state = {
    sessions: [],
    selectedSessionId: null,
    isLoading: false,
    healthStatus: 'connecting'
};

// API base URL
const API_BASE = '';

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
        updateLogSessionSelect();
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
    state.selectedSessionId = sessionId;
    renderSessionList();

    const session = state.sessions.find(s => s.session_id === sessionId);
    if (session) {
        showCommandPanel(session);
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

        if (state.selectedSessionId === sessionToDelete) {
            state.selectedSessionId = null;
            document.getElementById('no-session-message').classList.remove('hidden');
            document.getElementById('command-panel').classList.add('hidden');
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

        if (result.success) {
            setExecutionStatus('success', `Completed in ${result.duration_ms}ms`);
            document.getElementById('command-output').textContent = result.output || 'No output';
        } else {
            setExecutionStatus('error', 'Failed');
            document.getElementById('command-output').textContent = result.error || 'Unknown error';
        }
    } catch (error) {
        setExecutionStatus('error', 'Error');
        document.getElementById('command-output').textContent = error.message;
    }
}

function setExecutionStatus(status, text) {
    const statusEl = document.getElementById('execution-status');
    statusEl.textContent = text;
    statusEl.className = 'execution-status ' + status;
}

function clearOutput() {
    document.getElementById('command-output').textContent = 'No output yet';
    setExecutionStatus('', '');
}

// ========== Logs ==========

function updateLogSessionSelect() {
    const select = document.getElementById('log-session-select');
    const currentValue = select.value;

    select.innerHTML = '<option value="">Select Session</option>' +
        state.sessions.map(s => `
            <option value="${s.session_id}" ${s.session_id === currentValue ? 'selected' : ''}>
                ${s.session_name || s.session_id.substring(0, 8)}
            </option>
        `).join('');
}

async function loadSessionLogs() {
    const sessionId = document.getElementById('log-session-select').value;
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
    if (tabName === 'logs') {
        loadSessionLogs();
    }
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
    // Initial load
    refreshAll();

    // Periodic refresh
    setInterval(checkHealth, 30000); // Health check every 30s
    setInterval(loadSessions, 60000); // Session list every 60s

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
