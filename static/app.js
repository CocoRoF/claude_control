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
    sessionData: {}, // { sessionId: { input: '', output: '', status: '', statusText: '' } }
    // Available prompt templates
    prompts: [], // [{ name, filename, description }]
    promptContents: {}, // { promptName: content }
    // Auto-continue state
    isAutoContinuing: false,
    autoContinueCount: 0,
    autoContinueRetries: 0,
    maxRetries: 3,
    // SSR initial state loaded flag
    ssrInitialized: false,
    // Logs auto-refresh state
    logsAutoRefreshInterval: null,
    logsAutoRefreshEnabled: true
};

// Initialize from SSR data if available
function initFromSSR() {
    if (window.__INITIAL_STATE__ && !state.ssrInitialized) {
        const ssr = window.__INITIAL_STATE__;
        console.log('[SSR] Initializing from server-rendered state');

        // Load sessions from SSR
        if (ssr.sessions && Array.isArray(ssr.sessions)) {
            state.sessions = ssr.sessions;
            console.log(`[SSR] Loaded ${state.sessions.length} sessions`);
        }

        // Load prompts from SSR
        if (ssr.prompts && Array.isArray(ssr.prompts)) {
            state.prompts = ssr.prompts;
            console.log(`[SSR] Loaded ${state.prompts.length} prompts`);
        }

        // Load health status from SSR
        if (ssr.health) {
            state.healthStatus = ssr.health.status === 'healthy' ? 'healthy' : 'error';
        }

        state.ssrInitialized = true;
        return true;
    }
    return false;
}

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
        state.sessions = await apiCall('/api/agents');
        renderSessionList();
        updateSessionStats();
        updateBatchSessionList();
        syncPlaygroundSessions();
    } catch (error) {
        showError('Failed to load sessions: ' + error.message);
    }
}

// ========== Prompts Management ==========

async function loadPrompts() {
    try {
        const response = await apiCall('/api/command/prompts');
        state.prompts = response.prompts || [];
        updatePromptDropdown();
    } catch (error) {
        console.error('Failed to load prompts:', error);
        // Non-critical, don't show error to user
    }
}

function updatePromptDropdown() {
    const select = document.getElementById('new-session-prompt');
    if (!select) return;

    // Clear existing options except first (None) and last (Custom)
    while (select.options.length > 2) {
        select.remove(1);
    }

    // Insert prompt options before "Custom..."
    const customOption = select.options[select.options.length - 1];
    state.prompts.forEach(prompt => {
        const option = document.createElement('option');
        option.value = prompt.name;
        option.textContent = prompt.description || prompt.name;
        select.insertBefore(option, customOption);
    });

    // Set self-manager as default if available
    const selfManagerOption = Array.from(select.options).find(opt => opt.value === 'self-manager');
    if (selfManagerOption) {
        select.value = 'self-manager';
    }
}

async function onPromptSelect() {
    const select = document.getElementById('new-session-prompt');
    const customGroup = document.getElementById('custom-prompt-group');
    const customTextarea = document.getElementById('new-session-custom-prompt');

    if (select.value === 'custom') {
        customGroup.classList.remove('hidden');
        customTextarea.focus();
    } else {
        customGroup.classList.add('hidden');

        // Load prompt content if selecting a template
        if (select.value && select.value !== '') {
            await loadPromptContent(select.value);
        }
    }
}

async function loadPromptContent(promptName) {
    if (state.promptContents[promptName]) {
        return state.promptContents[promptName];
    }

    try {
        const response = await apiCall(`/api/command/prompts/${promptName}`);
        state.promptContents[promptName] = response.content;
        return response.content;
    } catch (error) {
        console.error(`Failed to load prompt ${promptName}:`, error);
        return null;
    }
}

async function getSelectedPromptContent() {
    const select = document.getElementById('new-session-prompt');
    const customTextarea = document.getElementById('new-session-custom-prompt');

    if (!select.value || select.value === '') {
        return null;
    }

    if (select.value === 'custom') {
        const content = customTextarea.value.trim();
        return content || null;
    }

    // Load template content
    return await loadPromptContent(select.value);
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

// Role selection handler
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

// Load managers for the selection dropdown
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

    // Get current session to check if autonomous mode
    const session = state.sessions.find(s => s.session_id === state.selectedSessionId);
    if (!session) {
        showError('Session not found');
        return;
    }

    const skipPermissions = document.getElementById('skip-permissions').checked;

    // Check if session is in autonomous mode
    if (session.autonomous) {
        await executeAutonomousInternal(prompt, skipPermissions);
    } else {
        await executeSingleInternal(prompt, skipPermissions);
    }
}

async function executeSingleInternal(prompt, skipPermissions) {
    setExecutionStatus('running', 'Executing...');
    updateExecutionUI(true);
    notifyCharacterRequestStart(state.selectedSessionId);

    try {
        const result = await apiCall(`/api/agents/${state.selectedSessionId}/execute`, {
            method: 'POST',
            body: JSON.stringify({
                prompt: prompt,
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

            sessionData.output = output;
            sessionData.status = 'success';
            sessionData.statusText = statusText;

            notifyCharacterRequestEnd(state.selectedSessionId, true);
        } else {
            setExecutionStatus('error', 'Failed');
            const output = result.error || 'Unknown error';
            document.getElementById('command-output').textContent = output;

            sessionData.output = output;
            sessionData.status = 'error';
            sessionData.statusText = 'Failed';

            notifyCharacterRequestEnd(state.selectedSessionId, false);
        }
    } catch (error) {
        setExecutionStatus('error', 'Error');
        document.getElementById('command-output').textContent = error.message;

        const sessionData = getSessionData(state.selectedSessionId);
        sessionData.output = error.message;
        sessionData.status = 'error';
        sessionData.statusText = 'Error';

        notifyCharacterRequestEnd(state.selectedSessionId, false);
    } finally {
        updateExecutionUI(false);
    }
}

async function executeAutonomousInternal(prompt, skipPermissions) {
    state.isAutoContinuing = true;
    state.autoContinueCount = 0;
    updateExecutionUI(true);
    setExecutionStatus('running', 'Starting autonomous execution...');
    notifyCharacterRequestStart(state.selectedSessionId);

    try {
        const result = await apiCall(`/api/agents/${state.selectedSessionId}/execute/autonomous`, {
            method: 'POST',
            body: JSON.stringify({
                prompt: prompt,
                skip_permissions: skipPermissions
            })
        });

        const sessionData = getSessionData(state.selectedSessionId);
        sessionData.input = prompt;

        if (result.success) {
            const statusText = `✅ Completed in ${result.total_iterations} iterations (${result.stop_reason})`;
            setExecutionStatus('success', statusText);
            const output = result.final_output || 'No output';
            document.getElementById('command-output').textContent = output;

            sessionData.output = output;
            sessionData.status = 'success';
            sessionData.statusText = statusText;

            notifyCharacterRequestEnd(state.selectedSessionId, true);
        } else {
            setExecutionStatus('error', `❌ Failed: ${result.stop_reason}`);
            const output = result.error || result.final_output || 'Unknown error';
            document.getElementById('command-output').textContent = output;

            sessionData.output = output;
            sessionData.status = 'error';
            sessionData.statusText = `Failed: ${result.stop_reason}`;

            notifyCharacterRequestEnd(state.selectedSessionId, false);
        }
    } catch (error) {
        setExecutionStatus('error', 'Error');
        document.getElementById('command-output').textContent = error.message;

        const sessionData = getSessionData(state.selectedSessionId);
        sessionData.output = error.message;
        sessionData.status = 'error';
        sessionData.statusText = 'Error';

        notifyCharacterRequestEnd(state.selectedSessionId, false);
    } finally {
        state.isAutoContinuing = false;
        updateExecutionUI(false);
    }
}

async function stopExecution() {
    if (!state.selectedSessionId) return;

    // Check if session is autonomous
    const session = state.sessions.find(s => s.session_id === state.selectedSessionId);

    if (session && session.autonomous && state.isAutoContinuing) {
        try {
            await apiCall(`/api/agents/${state.selectedSessionId}/execute/autonomous/stop`, {
                method: 'POST'
            });
            setExecutionStatus('warning', '🛑 Stop requested, waiting for current iteration...');
        } catch (error) {
            console.error('Failed to stop autonomous execution:', error);
        }
    }

    state.isAutoContinuing = false;
    updateExecutionUI(false);
}

function updateExecutionUI(isRunning) {
    const executeBtn = document.getElementById('execute-btn');
    const stopBtn = document.getElementById('stop-btn');

    if (isRunning) {
        if (executeBtn) executeBtn.classList.add('hidden');
        if (stopBtn) stopBtn.classList.remove('hidden');
    } else {
        if (executeBtn) executeBtn.classList.remove('hidden');
        if (stopBtn) stopBtn.classList.add('hidden');
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

// Start auto-refresh for logs (5 second interval)
function startLogsAutoRefresh() {
    if (state.logsAutoRefreshInterval) {
        clearInterval(state.logsAutoRefreshInterval);
    }
    state.logsAutoRefreshInterval = setInterval(() => {
        if (state.selectedSessionId && state.logsAutoRefreshEnabled) {
            loadSessionLogs();
        }
    }, 5000);
}

// Stop auto-refresh for logs
function stopLogsAutoRefresh() {
    if (state.logsAutoRefreshInterval) {
        clearInterval(state.logsAutoRefreshInterval);
        state.logsAutoRefreshInterval = null;
    }
}

// Toggle auto-refresh for logs
function toggleLogsAutoRefresh() {
    const checkbox = document.getElementById('logs-auto-refresh');
    state.logsAutoRefreshEnabled = checkbox.checked;

    if (state.logsAutoRefreshEnabled) {
        startLogsAutoRefresh();
    } else {
        stopLogsAutoRefresh();
    }
}

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

        container.innerHTML = result.entries.map(entry => {
            // Check if this is a long message that should be collapsible
            const message = entry.message || '';
            const metadata = entry.metadata || {};
            const isLongMessage = metadata.is_truncated || message.length > 200;
            const preview = metadata.preview || message.substring(0, 200) + (message.length > 200 ? '...' : '');

            if (isLongMessage) {
                return `
                    <div class="log-entry expandable" onclick="toggleLogEntry(this)">
                        <div class="log-header">
                            <span class="log-timestamp">${formatTimestamp(entry.timestamp)}</span>
                            <span class="log-level ${entry.level}">${entry.level}</span>
                            <span class="log-expand-icon">▶</span>
                        </div>
                        <div class="log-message-container">
                            <span class="log-message log-preview">${escapeHtml(preview)}</span>
                            <span class="log-message log-full hidden">${escapeHtml(message)}</span>
                        </div>
                        ${metadata.prompt_length ? `<span class="log-meta">(${metadata.prompt_length} chars)</span>` : ''}
                        ${metadata.output_length ? `<span class="log-meta">(${metadata.output_length} chars)</span>` : ''}
                    </div>
                `;
            } else {
                return `
                    <div class="log-entry">
                        <span class="log-timestamp">${formatTimestamp(entry.timestamp)}</span>
                        <span class="log-level ${entry.level}">${entry.level}</span>
                        <span class="log-message">${escapeHtml(message)}</span>
                    </div>
                `;
            }
        }).join('');

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

/**
 * Toggle log entry expansion
 */
function toggleLogEntry(element) {
    const isExpanded = element.classList.contains('expanded');

    if (isExpanded) {
        // Collapse
        element.classList.remove('expanded');
        element.querySelector('.log-expand-icon').textContent = '▶';
        element.querySelector('.log-preview').classList.remove('hidden');
        element.querySelector('.log-full').classList.add('hidden');
    } else {
        // Expand
        element.classList.add('expanded');
        element.querySelector('.log-expand-icon').textContent = '▼';
        element.querySelector('.log-preview').classList.add('hidden');
        element.querySelector('.log-full').classList.remove('hidden');
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

function updateHealthUI(status) {
    // Update health indicator based on SSR status
    if (status === 'healthy') {
        updateHealthIndicator('connected', `${state.sessions.length} sessions`);
    } else {
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

    // Load storage when switching to storage tab
    if (tabName === 'storage') {
        refreshStorage();
    }

    // Initialize or sync playground view
    if (tabName === 'playground') {
        initPlaygroundView();
    }

    // Refresh dashboard when switching to dashboard tab
    if (tabName === 'dashboard') {
        refreshManagerDashboard();
    }
}

// ========== Playground View (Three.js) ==========

let _playgroundInitialized = false;

function initPlaygroundView() {
    if (_playgroundInitialized) {
        // Just sync sessions
        syncPlaygroundSessions();
        return;
    }

    const container = document.getElementById('playground-canvas');
    const loading = document.getElementById('playground-loading');
    if (!container) return;

    // Check if Three.js and Playground are loaded
    if (typeof THREE === 'undefined' || !window.Playground || !window.Playground.Scene) {
        if (loading) loading.querySelector('.playground-loading-text').textContent = 'Loading Three.js...';
        console.error('Three.js or Playground not loaded');
        return;
    }

    // Wait a frame for the tab to become visible and sized
    requestAnimationFrame(() => {
        try {
            const scene = window.Playground.Scene;
            scene.mount(container).then(() => {
                _playgroundInitialized = true;
                if (loading) loading.style.display = 'none';

                // Initial session sync
                syncPlaygroundSessions();

                // Listen for avatar clicks
                document.addEventListener('playground-avatar-click', (e) => {
                    const sessionId = e.detail.sessionId;
                    selectSession(sessionId);
                    switchTab('command');
                });
            });
        } catch (err) {
            console.error('Failed to init playground view:', err);
            if (loading) {
                loading.querySelector('.playground-loading-text').textContent = 'Failed to initialize';
            }
        }
    });
}

function syncPlaygroundSessions() {
    if (!_playgroundInitialized) return;
    const scene = window.Playground.Scene;
    if (scene && scene.isInitialized) {
        scene.syncSessions(state.sessions);

        // Update UI
        const countEl = document.getElementById('playground-session-count');
        if (countEl) {
            countEl.textContent = `${state.sessions.length} citizen${state.sessions.length !== 1 ? 's' : ''}`;
        }

        const emptyState = document.getElementById('playground-empty-state');;
        if (emptyState) {
            emptyState.style.display = state.sessions.length === 0 ? 'block' : 'none';
        }

        // Update status overlay
        updatePlaygroundStatusOverlay();
    }
}

function updatePlaygroundStatusOverlay() {
    const overlay = document.getElementById('playground-status-overlay');
    if (!overlay) return;

    const running = state.sessions.filter(s => s.status === 'running').length;
    const idle = state.sessions.filter(s => s.status !== 'running' && s.status !== 'error').length;
    const errors = state.sessions.filter(s => s.status === 'error').length;

    let html = '';
    if (running > 0) {
        html += `<div class="playground-status-item"><span class="playground-status-dot running"></span>${running} working</div>`;
    }
    if (idle > 0) {
        html += `<div class="playground-status-item"><span class="playground-status-dot idle"></span>${idle} idle</div>`;
    }
    if (errors > 0) {
        html += `<div class="playground-status-item"><span class="playground-status-dot error"></span>${errors} error</div>`;
    }
    overlay.innerHTML = html;
}

/**
 * 캐릭터에게 요청 시작 알림
 */
function notifyCharacterRequestStart(sessionId) {
    if (!_playgroundInitialized) return;
    const scene = window.Playground.Scene;
    if (scene && scene.isInitialized) {
        scene.notifyRequestStart(sessionId);
    }
}

/**
 * 캐릭터에게 요청 완료 알림
 */
function notifyCharacterRequestEnd(sessionId, success) {
    if (!_playgroundInitialized) return;
    const scene = window.Playground.Scene;
    if (scene && scene.isInitialized) {
        scene.notifyRequestEnd(sessionId, success);
    }
}

function playgroundZoomIn() {
    const scene = window.Playground.Scene;
    if (scene) scene.zoomIn();
}

function playgroundZoomOut() {
    const scene = window.Playground.Scene;
    if (scene) scene.zoomOut();
}

function playgroundResetView() {
    const scene = window.Playground.Scene;
    if (scene) scene.resetView();
}

// ========== Modals ==========

function showCreateSessionModal() {
    document.getElementById('create-session-modal').classList.remove('hidden');
    document.getElementById('new-session-name').value = '';
    document.getElementById('new-session-prompt').value = 'self-manager';
    document.getElementById('new-session-custom-prompt').value = '';
    document.getElementById('custom-prompt-group').classList.add('hidden');
    document.getElementById('new-session-model').value = '';
    document.getElementById('new-session-max-turns').value = '100';
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
    // Skip initial API calls if SSR data is available
    if (initFromSSR()) {
        console.log('[SSR] Using server-rendered data, skipping initial API calls');
        // Just update the UI with SSR data (HTML is already rendered)
        updateHealthUI(state.healthStatus);
        syncPlaygroundSessions();
    } else {
        // Fallback: fetch data from API
        await loadSessions();
        await loadPrompts();
        await checkHealth();
    }
}

// ========== Storage Functions ==========

async function refreshStorage() {
    if (!state.selectedSessionId) {
        showStoragePlaceholder('Select a session to view its storage');
        return;
    }

    const storageTree = document.getElementById('storage-tree');
    storageTree.innerHTML = '<p class="storage-placeholder">Loading...</p>';

    try {
        const response = await fetch(`/api/agents/${state.selectedSessionId}/storage`);
        if (!response.ok) {
            if (response.status === 404) {
                showStoragePlaceholder('No storage found for this session');
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        renderStorageTree(data.files || []);
    } catch (error) {
        console.error('Failed to load storage:', error);
        showStoragePlaceholder('Failed to load storage');
    }
}

function showStoragePlaceholder(message) {
    const storageTree = document.getElementById('storage-tree');
    storageTree.innerHTML = `<p class="storage-placeholder">${message}</p>`;

    const previewFilename = document.getElementById('preview-filename');
    const previewContent = document.getElementById('preview-content');
    previewFilename.textContent = 'No file selected';
    previewContent.textContent = '';
}

function renderStorageTree(files) {
    const storageTree = document.getElementById('storage-tree');

    if (!files || files.length === 0) {
        showStoragePlaceholder('Storage is empty');
        return;
    }

    // Build tree structure
    const tree = buildFileTree(files);
    storageTree.innerHTML = renderTreeNode(tree, '');
}

function buildFileTree(files) {
    const tree = { children: {}, files: [] };

    for (const file of files) {
        const parts = file.path.split('/').filter(p => p);
        let current = tree;

        for (let i = 0; i < parts.length - 1; i++) {
            const part = parts[i];
            if (!current.children[part]) {
                current.children[part] = { children: {}, files: [] };
            }
            current = current.children[part];
        }

        current.files.push({
            name: parts[parts.length - 1],
            path: file.path,
            size: file.size || 0
        });
    }

    return tree;
}

function renderTreeNode(node, path) {
    let html = '<ul class="file-tree">';

    // Render folders first
    for (const [name, child] of Object.entries(node.children)) {
        const folderPath = path ? `${path}/${name}` : name;
        html += `
            <li class="file-tree-folder" data-path="${escapeHtml(folderPath)}">
                <div class="file-tree-folder-header" onclick="toggleFolder(this.parentElement)">
                    <span class="folder-toggle">▼</span>
                    <span class="file-icon">📁</span>
                    <span class="file-name">${escapeHtml(name)}</span>
                </div>
                <div class="file-tree-folder-children">
                    ${renderTreeNode(child, folderPath)}
                </div>
            </li>
        `;
    }

    // Render files
    for (const file of node.files) {
        const icon = getFileIcon(file.name);
        const sizeStr = formatFileSize(file.size);
        html += `
            <li class="file-tree-item" data-path="${escapeHtml(file.path)}" onclick="loadStorageFile('${escapeHtml(file.path)}')">
                <span class="file-icon">${icon}</span>
                <span class="file-name">${escapeHtml(file.name)}</span>
                <span class="file-size">${sizeStr}</span>
            </li>
        `;
    }

    html += '</ul>';
    return html;
}

function toggleFolder(folderElement) {
    folderElement.classList.toggle('collapsed');
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'md': '📝',
        'txt': '📄',
        'json': '📋',
        'js': '📜',
        'py': '🐍',
        'html': '🌐',
        'css': '🎨',
        'log': '📊',
        'yml': '⚙️',
        'yaml': '⚙️'
    };
    return iconMap[ext] || '📄';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

async function loadStorageFile(filePath) {
    if (!state.selectedSessionId) return;

    // Update active state in tree
    document.querySelectorAll('.file-tree-item.active').forEach(el => el.classList.remove('active'));
    const activeItem = document.querySelector(`.file-tree-item[data-path="${CSS.escape(filePath)}"]`);
    if (activeItem) activeItem.classList.add('active');

    const previewFilename = document.getElementById('preview-filename');
    const previewContent = document.getElementById('preview-content');

    previewFilename.textContent = filePath;
    previewContent.textContent = 'Loading...';

    try {
        // Remove leading slash if present
        const cleanPath = filePath.startsWith('/') ? filePath.substring(1) : filePath;
        const response = await fetch(`/api/agents/${state.selectedSessionId}/storage/${encodeURIComponent(cleanPath)}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        previewContent.textContent = data.content || '(empty file)';
    } catch (error) {
        console.error('Failed to load file:', error);
        previewContent.textContent = `Error loading file: ${error.message}`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== Manager Dashboard Functions ==========

async function refreshManagerDashboard() {
    if (!state.selectedSessionId) return;

    const session = state.sessions.find(s => s.session_id === state.selectedSessionId);
    if (!session || session.role !== 'manager') return;

    // Update dashboard session name
    const sessionNameEl = document.getElementById('dashboard-session-name');
    if (sessionNameEl) {
        sessionNameEl.textContent = session.session_name || session.session_id.substring(0, 8);
    }

    try {
        const dashboard = await apiCall(`/api/agents/${state.selectedSessionId}/dashboard`);
        renderManagerDashboard(dashboard);
    } catch (error) {
        console.error('Failed to load manager dashboard:', error);
    }
}

function renderManagerDashboard(dashboard) {
    // Update worker count
    document.getElementById('worker-count').textContent = dashboard.workers.length;

    // Render workers list
    const workersList = document.getElementById('workers-list');
    if (dashboard.workers.length === 0) {
        workersList.innerHTML = '<div class="empty-state-small">No workers assigned to this manager</div>';
    } else {
        workersList.innerHTML = dashboard.workers.map(worker => `
            <div class="worker-item ${worker.is_busy ? 'busy' : 'idle'}">
                <div class="worker-status-indicator ${worker.status}"></div>
                <div class="worker-info">
                    <div class="worker-name">${worker.worker_name || worker.worker_id.substring(0, 8)}</div>
                    <div class="worker-status-text">${worker.status}</div>
                </div>
                <div class="worker-task-info">
                    ${worker.is_busy
                        ? `<span class="worker-busy-badge">Working</span><span class="worker-task-text">${worker.current_task || ''}</span>`
                        : '<span class="worker-idle-badge">Idle</span>'}
                </div>
            </div>
        `).join('');
    }

    // Render activity timeline
    const timeline = document.getElementById('activity-timeline');
    if (dashboard.recent_events.length === 0) {
        timeline.innerHTML = '<div class="empty-state-small">No activity yet</div>';
    } else {
        timeline.innerHTML = dashboard.recent_events.map(event => {
            const time = new Date(event.timestamp).toLocaleString();
            const typeClass = getEventTypeClass(event.event_type);
            const icon = getEventIcon(event.event_type);
            return `
                <div class="timeline-item ${typeClass}">
                    <div class="timeline-icon">${icon}</div>
                    <div class="timeline-content">
                        <div class="timeline-header">
                            <span class="timeline-type">${formatEventType(event.event_type)}</span>
                            <span class="timeline-time">${time}</span>
                        </div>
                        <div class="timeline-message">${event.message}</div>
                        ${event.worker_id ? `<div class="timeline-worker">Worker: ${event.worker_id.substring(0, 8)}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
}

function getEventTypeClass(eventType) {
    switch (eventType) {
        case 'task_delegated':
        case 'worker_started':
            return 'event-info';
        case 'worker_completed':
            return 'event-success';
        case 'worker_error':
            return 'event-error';
        case 'worker_progress':
            return 'event-progress';
        default:
            return '';
    }
}

function formatEventType(eventType) {
    const typeMap = {
        'task_delegated': 'Task Delegated',
        'worker_started': 'Worker Started',
        'worker_completed': 'Worker Completed',
        'worker_error': 'Worker Error',
        'worker_progress': 'Progress Update',
        'plan_created': 'Plan Created',
        'plan_updated': 'Plan Updated',
        'user_message': 'User Message',
        'manager_response': 'Manager Response'
    };
    return typeMap[eventType] || eventType;
}

function getEventIcon(eventType) {
    const iconMap = {
        'task_delegated': '📤',
        'worker_started': '▶️',
        'worker_completed': '✅',
        'worker_error': '❌',
        'worker_progress': '🔄',
        'plan_created': '📋',
        'plan_updated': '📝',
        'user_message': '💬',
        'manager_response': '🤖'
    };
    return iconMap[eventType] || '📌';
}

// ========== Initialization ==========

document.addEventListener('DOMContentLoaded', () => {
    // Initialize sidebar state
    initSidebarState();

    // Load initial data
    refreshAll();
    // Periodic refresh
    setInterval(checkHealth, 30000); // Health check every 30s
    setInterval(loadSessions, 60000); // Session list every 60s

    // Start logs auto-refresh (default enabled)
    startLogsAutoRefresh();

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
