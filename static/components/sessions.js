/**
 * Claude Control Dashboard - Session Management
 */

// Session to delete (for confirmation modal)
let sessionToDelete = null;

/**
 * Load all sessions from API
 */
async function loadSessions() {
    try {
        state.sessions = await apiCall('/api/agents');
        renderSessionList();
        updateSessionStats();
        updateBatchSessionList();
        syncPlaygroundSessions();
    } catch (error) {
        showError('Failed to load sessions: ' + error.message);
    }
}

/**
 * Render session list in sidebar
 */
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

    container.innerHTML = state.sessions.map(session => {
        const roleClass = session.role === 'manager' ? 'role-manager' : 'role-worker';
        const roleLabel = session.role === 'manager' ? 'M' : 'W';
        return `
        <div class="session-item ${session.session_id === state.selectedSessionId ? 'selected' : ''}"
             onclick="selectSession('${session.session_id}')">
            <span class="session-status-dot ${session.status}"></span>
            <div class="session-info">
                <div class="session-name">
                    <span class="role-badge ${roleClass}">${roleLabel}</span>
                    ${session.session_name || 'Unnamed'}
                </div>
                <div class="session-id">${session.session_id.substring(0, 8)}...</div>
            </div>
            <div class="session-actions">
                <button class="btn btn-icon btn-sm" onclick="event.stopPropagation(); showDeleteConfirmation('${session.session_id}', '${session.session_name || session.session_id}')" title="Delete">
                    ✕
                </button>
            </div>
        </div>
    `}).join('');
}

/**
 * Update session statistics display
 */
function updateSessionStats() {
    const total = state.sessions.length;
    const running = state.sessions.filter(s => s.status === 'running').length;
    const error = state.sessions.filter(s => s.status === 'error').length;

    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-running').textContent = running;
    document.getElementById('stat-error').textContent = error;
}

/**
 * Select a session
 * @param {string} sessionId - Session ID to select
 */
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

/**
 * Show command panel for selected session
 * @param {Object} session - Session object
 */
function showCommandPanel(session) {
    document.getElementById('no-session-message').classList.add('hidden');
    document.getElementById('command-panel').classList.remove('hidden');

    const roleLabel = session.role === 'manager' ? 'Manager' : 'Worker';
    const roleClass = session.role === 'manager' ? 'role-manager' : 'role-worker';

    const infoContainer = document.getElementById('selected-session-info');
    infoContainer.innerHTML = `
        <h4>
            <span class="role-badge-large ${roleClass}">${roleLabel}</span>
            ${session.session_name || 'Unnamed Session'}
        </h4>
        <div class="session-meta">
            <span>ID: ${session.session_id.substring(0, 8)}...</span>
            <span>Status: ${session.status}</span>
            <span>Model: ${session.model || 'Default'}</span>
            ${session.pod_name ? `<span>Pod: ${session.pod_name}</span>` : ''}
            ${session.manager_id ? `<span>Manager: ${session.manager_id.substring(0, 8)}...</span>` : ''}
        </div>
    `;

    // Apply session settings to command options (read-only display)
    document.getElementById('command-timeout').value = session.timeout || 1800;
    document.getElementById('command-max-turns').value = session.max_turns || 100;
    document.getElementById('autonomous-max-iterations').value = session.autonomous_max_iterations || 100;

    // Update session mode badge
    const modeBadge = document.getElementById('session-mode-badge');
    if (modeBadge) {
        if (session.autonomous) {
            modeBadge.textContent = 'Autonomous';
            modeBadge.classList.add('autonomous');
            modeBadge.classList.remove('single');
        } else {
            modeBadge.textContent = 'Single';
            modeBadge.classList.add('single');
            modeBadge.classList.remove('autonomous');
        }
    }

    // Restore session-specific input and output
    const sessionData = getSessionData(session.session_id);
    document.getElementById('command-input').value = sessionData.input;
    document.getElementById('command-output').textContent = sessionData.output;

    // Restore execution status
    const statusEl = document.getElementById('execution-status');
    statusEl.textContent = sessionData.statusText;
    statusEl.className = 'execution-status ' + sessionData.status;

    // Show/hide manager dashboard tab
    const dashboardTabBtn = document.getElementById('dashboard-tab-btn');
    if (session.role === 'manager') {
        dashboardTabBtn.classList.remove('hidden');
    } else {
        dashboardTabBtn.classList.add('hidden');
    }
}

/**
 * Show logs panel for selected session
 * @param {Object} session - Session object
 */
function showLogsPanel(session) {
    document.getElementById('no-session-logs-message').classList.add('hidden');
    document.getElementById('logs-panel').classList.remove('hidden');

    // Update title
    document.getElementById('logs-session-title').textContent =
        `Logs: ${session.session_name || session.session_id.substring(0, 8)}`;

    // Load logs for selected session
    loadSessionLogs();
}

/**
 * Create a new session
 */
async function createSession() {
    const name = document.getElementById('new-session-name').value;
    const model = document.getElementById('new-session-model').value;
    const maxTurns = parseInt(document.getElementById('new-session-max-turns').value) || 100;
    const timeout = parseFloat(document.getElementById('new-session-timeout').value) || 1800;
    const maxIterations = parseInt(document.getElementById('new-session-max-iterations').value) || 100;
    const autonomous = document.getElementById('new-session-autonomous').checked;
    const role = document.getElementById('new-session-role').value || 'worker';
    const managerId = document.getElementById('new-session-manager').value || null;

    try {
        // Get system prompt content
        const systemPrompt = await getSelectedPromptContent();

        const payload = {
            session_name: name || undefined,
            model: model || undefined,
            max_turns: maxTurns,
            timeout: timeout,
            autonomous: autonomous,
            autonomous_max_iterations: maxIterations,
            system_prompt: systemPrompt || undefined,
            role: role,
            manager_id: managerId || undefined
        };

        await apiCall('/api/agents', {
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

/**
 * Role selection handler
 */
function onRoleSelect() {
    const role = document.getElementById('new-session-role').value;
    const managerSelectGroup = document.getElementById('manager-select-group');

    if (role === 'manager') {
        // Hide manager selection for manager role
        managerSelectGroup.classList.add('hidden');
    } else {
        // Show manager selection for worker role
        managerSelectGroup.classList.remove('hidden');
        loadManagersForSelect();
    }
}

/**
 * Load managers for the selection dropdown
 */
async function loadManagersForSelect() {
    try {
        const managers = await apiCall('/api/agents/managers');
        const select = document.getElementById('new-session-manager');

        // Clear existing options except the first one
        select.innerHTML = '<option value="">None (Standalone)</option>';

        for (const manager of managers) {
            const option = document.createElement('option');
            option.value = manager.session_id;
            const name = manager.session_name || manager.session_id.substring(0, 8);
            const statusIcon = manager.status === 'running' ? '🟢' : '⚪';
            option.textContent = `${statusIcon} ${name}`;
            // Disable non-running managers
            if (manager.status !== 'running') {
                option.disabled = true;
            }
            select.appendChild(option);
        }
    } catch (error) {
        console.error('Failed to load managers:', error);
    }
}

/**
 * Show delete confirmation modal
 * @param {string} sessionId - Session ID
 * @param {string} sessionName - Session name
 */
function showDeleteConfirmation(sessionId, sessionName) {
    sessionToDelete = sessionId;
    document.getElementById('delete-session-name').textContent = sessionName;
    document.getElementById('delete-session-modal').classList.remove('hidden');
}

/**
 * Hide delete session modal
 */
function hideDeleteSessionModal() {
    sessionToDelete = null;
    document.getElementById('delete-session-modal').classList.add('hidden');
}

/**
 * Confirm and delete session
 */
async function confirmDeleteSession() {
    if (!sessionToDelete) return;

    try {
        await apiCall(`/api/agents/${sessionToDelete}`, {
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
