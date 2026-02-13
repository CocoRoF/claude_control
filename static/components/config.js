/**
 * Claude Control Dashboard - Configuration Management
 */

/**
 * Load all configurations
 */
async function loadConfigs() {
    try {
        const response = await apiCall('/api/config');
        configState.configs = response.configs || [];
        configState.categories = response.categories || [];
        renderConfigCategories();
        renderConfigList();
    } catch (error) {
        showError('Failed to load configurations: ' + error.message);
    }
}

/**
 * Render config categories sidebar
 */
function renderConfigCategories() {
    const container = document.getElementById('settings-categories');
    if (!container) return;

    const allCount = configState.configs.length;

    let html = `
        <div class="settings-category ${configState.selectedCategory === 'all' ? 'active' : ''}"
             onclick="filterConfigsByCategory('all')">
            <span class="category-icon">⚙️</span>
            <span class="category-name">All</span>
            <span class="category-count">${allCount}</span>
        </div>
    `;

    const categoryIcons = {
        'general': '🔧',
        'channels': '💬',
        'security': '🔒',
        'advanced': '⚡'
    };

    configState.categories.forEach(cat => {
        const count = configState.configs.filter(c =>
            c.schema?.category === cat.name
        ).length;

        const icon = categoryIcons[cat.name] || '📁';

        html += `
            <div class="settings-category ${configState.selectedCategory === cat.name ? 'active' : ''}"
                 onclick="filterConfigsByCategory('${cat.name}')">
                <span class="category-icon">${icon}</span>
                <span class="category-name">${cat.label}</span>
                <span class="category-count">${count}</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Filter configs by category
 * @param {string} category - Category name
 */
function filterConfigsByCategory(category) {
    configState.selectedCategory = category;
    renderConfigCategories();
    renderConfigList();
}

/**
 * Render config list
 */
function renderConfigList() {
    const container = document.getElementById('config-list');
    if (!container) return;

    let configs = configState.configs;

    // Filter by category if not 'all'
    if (configState.selectedCategory !== 'all') {
        configs = configs.filter(c => c.schema?.category === configState.selectedCategory);
    }

    if (configs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No configurations found</p>
            </div>
        `;
        return;
    }

    const configIcons = {
        'discord': '🎮',
        'slack': '💼',
        'teams': '👥',
        'settings': '⚙️'
    };

    container.innerHTML = configs.map(config => {
        const schema = config.schema || {};
        const values = config.values || {};
        const isEnabled = values.enabled === true;
        const icon = configIcons[schema.icon] || configIcons[schema.name] || '⚙️';

        // Count configured fields (non-empty, non-default)
        const configuredCount = schema.fields?.filter(f => {
            const value = values[f.name];
            return value !== undefined && value !== '' && value !== f.default;
        }).length || 0;

        const totalFields = schema.fields?.length || 0;

        return `
            <div class="config-card ${isEnabled ? 'enabled' : 'disabled'}" onclick="editConfig('${schema.name}')">
                <div class="config-card-header">
                    <div class="config-icon">${icon}</div>
                    <div class="config-info">
                        <h4 class="config-name">${schema.display_name || schema.name}</h4>
                        <p class="config-description">${schema.description || ''}</p>
                    </div>
                    <div class="config-status">
                        <span class="config-status-badge ${isEnabled ? 'status-enabled' : 'status-disabled'}">
                            ${isEnabled ? 'Enabled' : 'Disabled'}
                        </span>
                    </div>
                </div>
                <div class="config-card-footer">
                    <span class="config-progress">${configuredCount}/${totalFields} fields configured</span>
                    ${!config.valid ? `<span class="config-warning">⚠️ ${config.errors?.length || 0} issues</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Edit a specific config
 * @param {string} configName - Config name
 */
async function editConfig(configName) {
    try {
        const response = await apiCall(`/api/config/${configName}`);
        configState.currentConfig = {
            name: configName,
            schema: response.schema,
            values: response.values
        };
        showConfigEditModal();
    } catch (error) {
        showError('Failed to load configuration: ' + error.message);
    }
}

/**
 * Show config edit modal
 */
function showConfigEditModal() {
    const modal = document.getElementById('config-edit-modal');
    const title = document.getElementById('config-edit-title');
    const body = document.getElementById('config-edit-body');

    if (!configState.currentConfig) return;

    const { schema, values } = configState.currentConfig;

    title.textContent = `Edit ${schema.display_name || schema.name}`;

    // Group fields by group
    const fieldGroups = {};
    schema.fields.forEach(field => {
        const group = field.group || 'general';
        if (!fieldGroups[group]) {
            fieldGroups[group] = [];
        }
        fieldGroups[group].push(field);
    });

    const groupLabels = {
        'connection': 'Connection',
        'server': 'Server Settings',
        'workspace': 'Workspace',
        'teams': 'Teams',
        'permissions': 'Permissions',
        'behavior': 'Behavior',
        'session': 'Session Settings',
        'commands': 'Commands',
        'graph': 'Microsoft Graph',
        'general': 'General'
    };

    let html = `<form id="config-form" class="config-form">`;

    for (const [groupName, fields] of Object.entries(fieldGroups)) {
        html += `
            <div class="config-group">
                <h4 class="config-group-title">${groupLabels[groupName] || groupName}</h4>
                <div class="config-group-fields">
        `;

        fields.forEach(field => {
            const value = values[field.name] ?? field.default ?? '';
            html += renderConfigField(field, value);
        });

        html += `
                </div>
            </div>
        `;
    }

    html += `</form>`;

    body.innerHTML = html;
    modal.classList.remove('hidden');
}

/**
 * Render a single config field
 * @param {Object} field - Field schema
 * @param {any} value - Field value
 * @returns {string} HTML string
 */
function renderConfigField(field, value) {
    const id = `config-field-${field.name}`;
    const required = field.required ? '<span class="field-required">*</span>' : '';

    let inputHtml = '';

    switch (field.type) {
        case 'boolean':
            inputHtml = `
                <label class="toggle-switch-label">
                    <input type="checkbox" id="${id}" name="${field.name}" ${value ? 'checked' : ''}>
                    <span class="toggle-switch-slider"></span>
                </label>
            `;
            break;

        case 'password':
            inputHtml = `
                <div class="password-field">
                    <input type="password" id="${id}" name="${field.name}" value="${escapeHtml(value || '')}"
                           placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''}>
                    <button type="button" class="btn-icon toggle-password" onclick="togglePasswordVisibility('${id}')">
                        👁️
                    </button>
                </div>
            `;
            break;

        case 'number':
            inputHtml = `
                <input type="number" id="${id}" name="${field.name}" value="${value}"
                       placeholder="${field.placeholder || ''}"
                       ${field.min !== undefined ? `min="${field.min}"` : ''}
                       ${field.max !== undefined ? `max="${field.max}"` : ''}
                       ${field.required ? 'required' : ''}>
            `;
            break;

        case 'select':
            inputHtml = `
                <select id="${id}" name="${field.name}" ${field.required ? 'required' : ''}>
                    <option value="">-- Select --</option>
                    ${(field.options || []).map(opt => `
                        <option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>${opt.label}</option>
                    `).join('')}
                </select>
            `;
            break;

        case 'textarea':
            // Handle array values (convert to comma-separated string)
            let textValue = value;
            if (Array.isArray(value)) {
                textValue = value.join(', ');
            }
            inputHtml = `
                <textarea id="${id}" name="${field.name}" rows="3"
                          placeholder="${field.placeholder || ''}"
                          ${field.required ? 'required' : ''}>${escapeHtml(textValue || '')}</textarea>
            `;
            break;

        case 'url':
            inputHtml = `
                <input type="url" id="${id}" name="${field.name}" value="${escapeHtml(value || '')}"
                       placeholder="${field.placeholder || 'https://'}" ${field.required ? 'required' : ''}>
            `;
            break;

        case 'email':
            inputHtml = `
                <input type="email" id="${id}" name="${field.name}" value="${escapeHtml(value || '')}"
                       placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''}>
            `;
            break;

        default: // string
            inputHtml = `
                <input type="text" id="${id}" name="${field.name}" value="${escapeHtml(value || '')}"
                       placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''}>
            `;
    }

    return `
        <div class="config-field ${field.type === 'boolean' ? 'config-field-toggle' : ''}">
            <label for="${id}">${field.label}${required}</label>
            ${inputHtml}
            ${field.description ? `<small class="field-description">${field.description}</small>` : ''}
        </div>
    `;
}

/**
 * Toggle password visibility
 * @param {string} fieldId - Field ID
 */
function togglePasswordVisibility(fieldId) {
    const input = document.getElementById(fieldId);
    if (input) {
        input.type = input.type === 'password' ? 'text' : 'password';
    }
}

/**
 * Hide config edit modal
 */
function hideConfigEditModal() {
    const modal = document.getElementById('config-edit-modal');
    modal.classList.add('hidden');
    configState.currentConfig = null;
}

/**
 * Save config
 */
async function saveConfig() {
    if (!configState.currentConfig) return;

    const form = document.getElementById('config-form');
    const formData = new FormData(form);
    const values = {};

    // Collect form values
    configState.currentConfig.schema.fields.forEach(field => {
        const element = document.getElementById(`config-field-${field.name}`);
        if (!element) return;

        if (field.type === 'boolean') {
            values[field.name] = element.checked;
        } else if (field.type === 'number') {
            values[field.name] = element.value ? Number(element.value) : null;
        } else if (field.type === 'textarea' && field.name.includes('_ids')) {
            // Convert comma-separated to array for ID fields
            const text = element.value.trim();
            values[field.name] = text ? text.split(',').map(s => s.trim()).filter(s => s) : [];
        } else {
            values[field.name] = element.value;
        }
    });

    try {
        const response = await apiCall(`/api/config/${configState.currentConfig.name}`, {
            method: 'PUT',
            body: JSON.stringify({ values })
        });

        if (response.success) {
            showSuccess(`Configuration saved successfully`);
            hideConfigEditModal();
            loadConfigs();
        } else {
            showError('Failed to save configuration');
        }
    } catch (error) {
        showError('Failed to save configuration: ' + error.message);
    }
}

/**
 * Reset config to defaults
 */
async function resetConfigToDefaults() {
    if (!configState.currentConfig) return;

    if (!confirm(`Reset "${configState.currentConfig.schema.display_name}" to default values?`)) {
        return;
    }

    try {
        const response = await apiCall(`/api/config/${configState.currentConfig.name}`, {
            method: 'DELETE'
        });

        if (response.success) {
            showSuccess('Configuration reset to defaults');
            hideConfigEditModal();
            loadConfigs();
        } else {
            showError('Failed to reset configuration');
        }
    } catch (error) {
        showError('Failed to reset configuration: ' + error.message);
    }
}

/**
 * Export all configs
 */
async function exportConfigs() {
    try {
        const response = await apiCall('/api/config/export', { method: 'POST' });

        if (response.success) {
            const json = JSON.stringify(response.configs, null, 2);
            const blob = new Blob([json], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `claude-control-config-${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            URL.revokeObjectURL(url);
            showSuccess('Configurations exported successfully');
        }
    } catch (error) {
        showError('Failed to export configurations: ' + error.message);
    }
}

/**
 * Show import config modal
 */
function showImportConfigModal() {
    const modal = document.getElementById('config-import-modal');
    document.getElementById('config-import-data').value = '';
    modal.classList.remove('hidden');
}

/**
 * Hide import config modal
 */
function hideImportConfigModal() {
    const modal = document.getElementById('config-import-modal');
    modal.classList.add('hidden');
}

/**
 * Import configs
 */
async function importConfigs() {
    const textarea = document.getElementById('config-import-data');
    const jsonText = textarea.value.trim();

    if (!jsonText) {
        showError('Please paste configuration JSON');
        return;
    }

    let configs;
    try {
        configs = JSON.parse(jsonText);
    } catch (e) {
        showError('Invalid JSON format');
        return;
    }

    try {
        const response = await apiCall('/api/config/import', {
            method: 'POST',
            body: JSON.stringify({ configs })
        });

        if (response.success) {
            showSuccess(response.message);
            hideImportConfigModal();
            loadConfigs();
        } else {
            showError(response.message || 'Failed to import configurations');
        }
    } catch (error) {
        showError('Failed to import configurations: ' + error.message);
    }
}
