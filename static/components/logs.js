/**
 * Claude Control Dashboard - Logs Management
 */

/**
 * Start auto-refresh for logs (5 second interval)
 */
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

/**
 * Stop auto-refresh for logs
 */
function stopLogsAutoRefresh() {
    if (state.logsAutoRefreshInterval) {
        clearInterval(state.logsAutoRefreshInterval);
        state.logsAutoRefreshInterval = null;
    }
}

/**
 * Toggle auto-refresh for logs
 */
function toggleLogsAutoRefresh() {
    const checkbox = document.getElementById('logs-auto-refresh');
    state.logsAutoRefreshEnabled = checkbox.checked;

    if (state.logsAutoRefreshEnabled) {
        startLogsAutoRefresh();
    } else {
        stopLogsAutoRefresh();
    }
}

/**
 * Load session logs from API
 */
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
 * @param {HTMLElement} element - Log entry element
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
