/**
 * Claude Control Dashboard - Graph Visualization Component
 *
 * Renders LangGraph graph structures as interactive SVG diagrams.
 * Shows nodes, edges (straight + conditional), and prompt details
 * in a side panel when a node is clicked.
 */

// ========== Graph State ==========

const graphState = {
    graphData: null,        // GraphStructure from API
    selectedNode: null,     // currently-clicked node id
    svgPan: { x: 0, y: 0 },
    svgScale: 1,
    isDragging: false,
    dragStart: { x: 0, y: 0 },
    nodePositions: {},      // { nodeId: { x, y } }
};

// ========== Layout Constants ==========

const GRAPH_LAYOUT = {
    nodeWidth: 180,
    nodeHeight: 56,
    startEndRadius: 28,
    horizontalGap: 80,
    verticalGap: 100,
    padding: 60,
    arrowSize: 8,
};

// ========== Layout Engine ==========

/**
 * Compute node positions using a layered layout algorithm.
 * Groups nodes into rows (layers) based on topological distance from START.
 */
function computeGraphLayout(graphData) {
    const { nodes, edges } = graphData;
    const positions = {};

    if (graphData.graph_type === 'simple') {
        return computeSimpleLayout(nodes, edges);
    }
    return computeAutonomousLayout(nodes, edges);
}

/**
 * Simple graph: vertical linear chain with conditional loop.
 */
function computeSimpleLayout(nodes, edges) {
    const positions = {};
    const L = GRAPH_LAYOUT;
    const order = ['__start__', 'context_guard', 'agent', 'process_output', '__end__'];
    const centerX = 400;
    const startY = L.padding;

    order.forEach((id, idx) => {
        positions[id] = { x: centerX, y: startY + idx * (L.nodeHeight + L.verticalGap) };
    });
    return positions;
}

/**
 * Autonomous graph: multi-path branching layout.
 *
 *  Layer 0: START
 *  Layer 1: classify_difficulty
 *  Layer 2: direct_answer | answer | create_todos
 *  Layer 3: __end__       | review | execute_todo
 *  Layer 4:               | __end__| check_progress
 *  ...etc
 */
function computeAutonomousLayout(nodes, edges) {
    const positions = {};
    const L = GRAPH_LAYOUT;
    const colW = L.nodeWidth + L.horizontalGap;
    const rowH = L.nodeHeight + L.verticalGap;

    // Three columns: easy(left), medium(center), hard(right)
    const colX = {
        easy: 180,
        medium: 180 + colW,
        hard: 180 + colW * 2,
    };
    const topCenter = (colX.easy + colX.hard) / 2;

    // Row 0 — START
    positions['__start__'] = { x: topCenter, y: L.padding };
    // Row 1 — classify_difficulty
    positions['classify_difficulty'] = { x: topCenter, y: L.padding + rowH };

    // Easy column
    positions['direct_answer'] = { x: colX.easy, y: L.padding + rowH * 2 };

    // Medium column
    positions['answer'] = { x: colX.medium, y: L.padding + rowH * 2 };
    positions['review'] = { x: colX.medium, y: L.padding + rowH * 3 };

    // Hard column
    positions['create_todos'] = { x: colX.hard, y: L.padding + rowH * 2 };
    positions['execute_todo'] = { x: colX.hard, y: L.padding + rowH * 3 };
    positions['check_progress'] = { x: colX.hard, y: L.padding + rowH * 4 };
    positions['final_review'] = { x: colX.hard, y: L.padding + rowH * 5 };
    positions['final_answer'] = { x: colX.hard, y: L.padding + rowH * 6 };

    // END — bottom center
    const maxY = Math.max(...Object.values(positions).map(p => p.y));
    positions['__end__'] = { x: topCenter, y: maxY + rowH };

    return positions;
}

// ========== SVG Rendering ==========

/**
 * Render the full graph as an SVG inside the given container element.
 */
function renderGraph(containerEl, graphData) {
    if (!graphData || !graphData.nodes) return;

    graphState.graphData = graphData;
    graphState.nodePositions = computeGraphLayout(graphData);

    const positions = graphState.nodePositions;
    const L = GRAPH_LAYOUT;

    // Calculate SVG size
    const allX = Object.values(positions).map(p => p.x);
    const allY = Object.values(positions).map(p => p.y);
    const svgW = Math.max(...allX) + L.nodeWidth + L.padding * 2;
    const svgH = Math.max(...allY) + L.nodeHeight + L.padding * 2;

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'graph-svg');
    svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');
    svg.style.minHeight = `${svgH}px`;

    // Defs — arrowheads, filters
    svg.innerHTML = `
        <defs>
            <marker id="arrow-normal" markerWidth="${L.arrowSize}" markerHeight="${L.arrowSize}"
                    refX="${L.arrowSize}" refY="${L.arrowSize / 2}" orient="auto">
                <path d="M0,0 L${L.arrowSize},${L.arrowSize / 2} L0,${L.arrowSize} Z"
                      fill="var(--graph-edge-color, #6b7280)" />
            </marker>
            <marker id="arrow-conditional" markerWidth="${L.arrowSize}" markerHeight="${L.arrowSize}"
                    refX="${L.arrowSize}" refY="${L.arrowSize / 2}" orient="auto">
                <path d="M0,0 L${L.arrowSize},${L.arrowSize / 2} L0,${L.arrowSize} Z"
                      fill="var(--graph-cond-color, #f59e0b)" />
            </marker>
            <filter id="node-shadow" x="-10%" y="-10%" width="130%" height="140%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.15" />
            </filter>
            <filter id="node-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="6" flood-color="var(--graph-accent, #3b82f6)" flood-opacity="0.5" />
            </filter>
        </defs>
    `;

    // Render edges first (under nodes)
    const edgeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    edgeGroup.setAttribute('class', 'graph-edges');
    graphData.edges.forEach(edge => {
        renderEdge(edgeGroup, edge, positions, L);
    });
    svg.appendChild(edgeGroup);

    // Render nodes
    const nodeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    nodeGroup.setAttribute('class', 'graph-nodes');
    graphData.nodes.forEach(node => {
        renderNode(nodeGroup, node, positions, L);
    });
    svg.appendChild(nodeGroup);

    // Clear container and add SVG
    containerEl.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.className = 'graph-svg-wrapper';
    wrapper.appendChild(svg);
    containerEl.appendChild(wrapper);

    // Add pan/zoom
    initGraphPanZoom(wrapper, svg);
}

/**
 * Render a single node (rectangle or circle for start/end).
 */
function renderNode(group, node, positions, L) {
    const pos = positions[node.id];
    if (!pos) return;

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', `graph-node graph-node--${node.type} ${getPathClass(node)}`);
    g.setAttribute('data-node-id', node.id);
    g.setAttribute('tabindex', '0');
    g.style.cursor = 'pointer';

    if (node.type === 'start' || node.type === 'end') {
        // Circle for start/end
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', pos.x);
        circle.setAttribute('cy', pos.y);
        circle.setAttribute('r', L.startEndRadius);
        circle.setAttribute('class', 'graph-node-shape');
        circle.setAttribute('filter', 'url(#node-shadow)');
        g.appendChild(circle);

        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', pos.x);
        text.setAttribute('y', pos.y + 5);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('class', 'graph-node-label graph-node-label--terminal');
        text.textContent = node.label;
        g.appendChild(text);
    } else {
        // Rounded rectangle
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', pos.x - L.nodeWidth / 2);
        rect.setAttribute('y', pos.y - L.nodeHeight / 2);
        rect.setAttribute('width', L.nodeWidth);
        rect.setAttribute('height', L.nodeHeight);
        rect.setAttribute('rx', 12);
        rect.setAttribute('ry', 12);
        rect.setAttribute('class', 'graph-node-shape');
        rect.setAttribute('filter', 'url(#node-shadow)');
        g.appendChild(rect);

        // Icon based on path
        const iconX = pos.x - L.nodeWidth / 2 + 16;
        const iconY = pos.y + 5;
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        icon.setAttribute('x', iconX);
        icon.setAttribute('y', iconY);
        icon.setAttribute('class', 'graph-node-icon');
        icon.textContent = getNodeIcon(node);
        g.appendChild(icon);

        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', pos.x + 6);
        text.setAttribute('y', pos.y + 5);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('class', 'graph-node-label');
        text.textContent = node.label;
        g.appendChild(text);

        // Prompt indicator
        if (node.prompt_template) {
            const badge = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            badge.setAttribute('cx', pos.x + L.nodeWidth / 2 - 8);
            badge.setAttribute('cy', pos.y - L.nodeHeight / 2 + 8);
            badge.setAttribute('r', 6);
            badge.setAttribute('class', 'graph-prompt-badge');
            g.appendChild(badge);

            const badgeText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            badgeText.setAttribute('x', pos.x + L.nodeWidth / 2 - 8);
            badgeText.setAttribute('y', pos.y - L.nodeHeight / 2 + 11);
            badgeText.setAttribute('text-anchor', 'middle');
            badgeText.setAttribute('class', 'graph-prompt-badge-text');
            badgeText.textContent = 'P';
            g.appendChild(badgeText);
        }
    }

    // Click handler
    g.addEventListener('click', (e) => {
        e.stopPropagation();
        selectGraphNode(node.id);
    });

    group.appendChild(g);
}

/**
 * Render a single edge (line with arrow), optionally with a label.
 */
function renderEdge(group, edge, positions, L) {
    const src = positions[edge.source];
    const tgt = positions[edge.target];
    if (!src || !tgt) return;

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', `graph-edge graph-edge--${edge.type}`);

    // Calculate start/end points considering node shapes
    const { x1, y1, x2, y2 } = getEdgeEndpoints(src, tgt, edge, positions, L);

    const isConditional = edge.type === 'conditional';
    const isSelfLoop = edge.source === edge.target;
    const isBackEdge = isBackwardEdge(edge, positions);

    let path;
    if (isSelfLoop) {
        // Self loop (rare, but handle it)
        path = createSelfLoopPath(x1, y1, L);
    } else if (isBackEdge) {
        // Backward edge — curved
        path = createBackEdgePath(x1, y1, x2, y2, edge, positions, L);
    } else {
        // Forward edge — straight or gentle curve
        path = createForwardEdgePath(x1, y1, x2, y2, isConditional);
    }

    path.setAttribute('class', `graph-edge-path ${isConditional ? 'graph-edge-path--conditional' : ''}`);
    path.setAttribute('marker-end', isConditional ? 'url(#arrow-conditional)' : 'url(#arrow-normal)');
    g.appendChild(path);

    // Label
    if (edge.label) {
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        let labelX = midX;
        let labelY = midY;

        if (isBackEdge) {
            // Offset label for back edges
            labelX = Math.min(x1, x2) - 40;
            labelY = (y1 + y2) / 2;
        }

        const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        const textEl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        textEl.setAttribute('x', labelX);
        textEl.setAttribute('y', labelY + 4);
        textEl.setAttribute('text-anchor', 'middle');
        textEl.setAttribute('class', `graph-edge-label ${isConditional ? 'graph-edge-label--conditional' : ''}`);
        textEl.textContent = edge.label;
        g.appendChild(textEl);

        // Measure text for background (approximate)
        const textW = edge.label.length * 7 + 12;
        bg.setAttribute('x', labelX - textW / 2);
        bg.setAttribute('y', labelY - 8);
        bg.setAttribute('width', textW);
        bg.setAttribute('height', 18);
        bg.setAttribute('rx', 4);
        bg.setAttribute('class', 'graph-edge-label-bg');
        g.insertBefore(bg, textEl);
    }

    group.appendChild(g);
}

// ========== Edge Geometry Helpers ==========

function getEdgeEndpoints(src, tgt, edge, positions, L) {
    const srcNode = graphState.graphData.nodes.find(n => n.id === edge.source);
    const tgtNode = graphState.graphData.nodes.find(n => n.id === edge.target);

    let x1 = src.x, y1 = src.y, x2 = tgt.x, y2 = tgt.y;

    // Offset from node boundary
    if (srcNode && (srcNode.type === 'start' || srcNode.type === 'end')) {
        y1 += L.startEndRadius;
    } else {
        y1 += L.nodeHeight / 2;
    }

    if (tgtNode && (tgtNode.type === 'start' || tgtNode.type === 'end')) {
        y2 -= L.startEndRadius;
    } else {
        y2 -= L.nodeHeight / 2;
    }

    // Horizontal edges (same row)
    if (Math.abs(src.y - tgt.y) < 10) {
        y1 = src.y;
        y2 = tgt.y;
        if (src.x < tgt.x) {
            x1 = src.x + L.nodeWidth / 2;
            x2 = tgt.x - L.nodeWidth / 2;
        } else {
            x1 = src.x - L.nodeWidth / 2;
            x2 = tgt.x + L.nodeWidth / 2;
        }
    }

    // Back edges (going up) — attach from sides
    if (tgt.y < src.y) {
        const srcRight = srcNode?.type === 'start' || srcNode?.type === 'end'
            ? src.x + L.startEndRadius
            : src.x + L.nodeWidth / 2;
        const tgtRight = tgtNode?.type === 'start' || tgtNode?.type === 'end'
            ? tgt.x + L.startEndRadius
            : tgt.x + L.nodeWidth / 2;
        x1 = src.x - L.nodeWidth / 2;
        y1 = src.y;
        x2 = tgt.x - L.nodeWidth / 2;
        y2 = tgt.y;
    }

    return { x1, y1, x2, y2 };
}

function isBackwardEdge(edge, positions) {
    const src = positions[edge.source];
    const tgt = positions[edge.target];
    return tgt && src && tgt.y < src.y;
}

function createForwardEdgePath(x1, y1, x2, y2, isConditional) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const dx = Math.abs(x2 - x1);
    const dy = Math.abs(y2 - y1);

    if (dx < 5) {
        // Straight vertical
        path.setAttribute('d', `M${x1},${y1} L${x2},${y2}`);
    } else {
        // Smooth cubic curve
        const cpY = Math.min(y1, y2) + dy * 0.4;
        path.setAttribute('d', `M${x1},${y1} C${x1},${cpY} ${x2},${cpY} ${x2},${y2}`);
    }
    return path;
}

function createBackEdgePath(x1, y1, x2, y2, edge, positions, L) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const offset = -50;
    path.setAttribute('d',
        `M${x1},${y1} C${x1 + offset},${y1} ${x2 + offset},${y2} ${x2},${y2}`
    );
    return path;
}

function createSelfLoopPath(x, y, L) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const r = 30;
    path.setAttribute('d',
        `M${x + L.nodeWidth / 2},${y - 10} C${x + L.nodeWidth / 2 + r},${y - r - 10} ${x + L.nodeWidth / 2 + r},${y + r - 10} ${x + L.nodeWidth / 2},${y + 10}`
    );
    return path;
}

// ========== Node Utilities ==========

function getNodeIcon(node) {
    const icons = {
        context_guard: '🛡️',
        agent: '🤖',
        process_output: '⚙️',
        classify_difficulty: '🔀',
        direct_answer: '⚡',
        answer: '💬',
        review: '📋',
        create_todos: '📝',
        execute_todo: '🔨',
        check_progress: '📊',
        final_review: '✅',
        final_answer: '🎯',
    };
    return icons[node.id] || '●';
}

function getPathClass(node) {
    const pathMap = node.metadata?.path;
    if (pathMap === 'easy') return 'graph-path--easy';
    if (pathMap === 'medium') return 'graph-path--medium';
    if (pathMap === 'hard') return 'graph-path--hard';
    return '';
}

// ========== Selection & Detail Panel ==========

function selectGraphNode(nodeId) {
    const prev = graphState.selectedNode;
    graphState.selectedNode = nodeId;

    // Update visual selection
    document.querySelectorAll('.graph-node').forEach(el => {
        el.classList.toggle('graph-node--selected', el.dataset.nodeId === nodeId);
    });

    // Update detail panel
    const node = graphState.graphData?.nodes?.find(n => n.id === nodeId);
    if (!node) return;

    const panel = document.getElementById('graph-detail-panel');
    if (!panel) return;

    panel.classList.add('graph-detail-panel--open');
    renderNodeDetail(panel, node);
}

function closeGraphDetail() {
    graphState.selectedNode = null;
    document.querySelectorAll('.graph-node').forEach(el => {
        el.classList.remove('graph-node--selected');
    });
    const panel = document.getElementById('graph-detail-panel');
    if (panel) panel.classList.remove('graph-detail-panel--open');
}

function renderNodeDetail(panel, node) {
    const pathColors = { easy: '#10b981', medium: '#f59e0b', hard: '#ef4444' };
    const pathLabels = { easy: 'Easy Path', medium: 'Medium Path', hard: 'Hard Path' };
    const path = node.metadata?.path;

    let html = `
        <div class="graph-detail-header">
            <div class="graph-detail-title-row">
                <span class="graph-detail-icon">${getNodeIcon(node)}</span>
                <h3 class="graph-detail-title">${escapeHtml(node.label)}</h3>
            </div>
            <button class="graph-detail-close" onclick="closeGraphDetail()" title="Close">×</button>
        </div>
        <div class="graph-detail-body">
    `;

    // Node type badge
    html += `<div class="graph-detail-badges">`;
    html += `<span class="graph-badge graph-badge--type">${node.type.toUpperCase()}</span>`;
    if (path) {
        html += `<span class="graph-badge graph-badge--path" style="background:${pathColors[path]}20;color:${pathColors[path]};border:1px solid ${pathColors[path]}40">${pathLabels[path]}</span>`;
    }
    if (node.prompt_template) {
        html += `<span class="graph-badge graph-badge--prompt">Has Prompt</span>`;
    }
    html += `</div>`;

    // Description
    html += `<div class="graph-detail-section">
        <h4>Description</h4>
        <p>${escapeHtml(node.description)}</p>
    </div>`;

    // Node ID
    html += `<div class="graph-detail-section">
        <h4>Node ID</h4>
        <code class="graph-detail-code-inline">${escapeHtml(node.id)}</code>
    </div>`;

    // Edges from/to this node
    if (graphState.graphData) {
        const inEdges = graphState.graphData.edges.filter(e => e.target === node.id);
        const outEdges = graphState.graphData.edges.filter(e => e.source === node.id);

        if (inEdges.length > 0) {
            html += `<div class="graph-detail-section">
                <h4>Incoming Edges</h4>
                <div class="graph-edge-list">`;
            inEdges.forEach(e => {
                const srcNode = graphState.graphData.nodes.find(n => n.id === e.source);
                html += `<div class="graph-edge-item" onclick="selectGraphNode('${e.source}')">
                    <span class="graph-edge-from">${escapeHtml(srcNode?.label || e.source)}</span>
                    <span class="graph-edge-arrow">→</span>
                    <span class="graph-edge-to">${escapeHtml(node.label)}</span>
                    ${e.label ? `<span class="graph-edge-cond-label">[${escapeHtml(e.label)}]</span>` : ''}
                </div>`;
            });
            html += `</div></div>`;
        }

        if (outEdges.length > 0) {
            html += `<div class="graph-detail-section">
                <h4>Outgoing Edges</h4>
                <div class="graph-edge-list">`;
            // Group by condition_map (to avoid duplicating the same conditional set)
            const seen = new Set();
            outEdges.forEach(e => {
                const tgtNode = graphState.graphData.nodes.find(n => n.id === e.target);
                const key = `${e.source}-${e.target}-${e.label}`;
                if (seen.has(key)) return;
                seen.add(key);
                html += `<div class="graph-edge-item" onclick="selectGraphNode('${e.target}')">
                    <span class="graph-edge-from">${escapeHtml(node.label)}</span>
                    <span class="graph-edge-arrow">→</span>
                    <span class="graph-edge-to">${escapeHtml(tgtNode?.label || e.target)}</span>
                    ${e.label ? `<span class="graph-edge-cond-label">[${escapeHtml(e.label)}]</span>` : ''}
                </div>`;
            });
            html += `</div></div>`;
        }

        // Condition map (for conditional source nodes)
        const condEdge = outEdges.find(e => e.condition_map);
        if (condEdge?.condition_map) {
            html += `<div class="graph-detail-section">
                <h4>Conditional Routing</h4>
                <div class="graph-condition-map">`;
            Object.entries(condEdge.condition_map).forEach(([cond, target]) => {
                const tNode = graphState.graphData.nodes.find(n => n.id === target);
                html += `<div class="graph-condition-row">
                    <span class="graph-condition-key">${escapeHtml(cond)}</span>
                    <span class="graph-condition-arrow">→</span>
                    <span class="graph-condition-target" onclick="selectGraphNode('${target}')">${escapeHtml(tNode?.label || target)}</span>
                </div>`;
            });
            html += `</div></div>`;
        }
    }

    // Prompt template
    if (node.prompt_template) {
        html += `<div class="graph-detail-section">
            <h4>Prompt Template</h4>
            <pre class="graph-detail-prompt">${escapeHtml(node.prompt_template)}</pre>
        </div>`;
    }

    // Metadata
    if (node.metadata && Object.keys(node.metadata).length > 0) {
        // Filter out internal keys already shown
        const displayMeta = { ...node.metadata };
        delete displayMeta.path;
        delete displayMeta.inner_graph;

        if (Object.keys(displayMeta).length > 0) {
            html += `<div class="graph-detail-section">
                <h4>Metadata</h4>
                <pre class="graph-detail-code">${escapeHtml(JSON.stringify(displayMeta, null, 2))}</pre>
            </div>`;
        }

        // Inner graph info
        if (node.metadata.inner_graph) {
            html += `<div class="graph-detail-section">
                <h4>Inner Graph (Simple Agent Loop)</h4>
                <p class="graph-detail-inner-desc">${escapeHtml(node.metadata.inner_graph.description)}</p>
                <div class="graph-inner-mini">`;
            node.metadata.inner_graph.nodes.forEach(n => {
                html += `<span class="graph-inner-node graph-inner-node--${n.type}">${escapeHtml(n.label)}</span>`;
            });
            html += `</div></div>`;
        }
    }

    html += `</div>`; // close .graph-detail-body
    panel.innerHTML = html;
}

// ========== Pan/Zoom ==========

function initGraphPanZoom(wrapper, svg) {
    // Mouse wheel zoom
    wrapper.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.08 : 0.08;
        graphState.svgScale = Math.max(0.3, Math.min(2.5, graphState.svgScale + delta));
        applyGraphTransform(svg);
    }, { passive: false });

    // Pan
    wrapper.addEventListener('mousedown', (e) => {
        if (e.target.closest('.graph-node')) return;
        graphState.isDragging = true;
        graphState.dragStart = { x: e.clientX - graphState.svgPan.x, y: e.clientY - graphState.svgPan.y };
        wrapper.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        if (!graphState.isDragging) return;
        graphState.svgPan.x = e.clientX - graphState.dragStart.x;
        graphState.svgPan.y = e.clientY - graphState.dragStart.y;
        applyGraphTransform(svg);
    });

    window.addEventListener('mouseup', () => {
        graphState.isDragging = false;
        wrapper.style.cursor = 'grab';
    });

    wrapper.style.cursor = 'grab';
}

function applyGraphTransform(svg) {
    svg.style.transform = `translate(${graphState.svgPan.x}px, ${graphState.svgPan.y}px) scale(${graphState.svgScale})`;
    svg.style.transformOrigin = '0 0';
}

function resetGraphView() {
    graphState.svgPan = { x: 0, y: 0 };
    graphState.svgScale = 1;
    const svg = document.querySelector('.graph-svg');
    if (svg) applyGraphTransform(svg);
}

function zoomGraphIn() {
    graphState.svgScale = Math.min(2.5, graphState.svgScale + 0.15);
    const svg = document.querySelector('.graph-svg');
    if (svg) applyGraphTransform(svg);
}

function zoomGraphOut() {
    graphState.svgScale = Math.max(0.3, graphState.svgScale - 0.15);
    const svg = document.querySelector('.graph-svg');
    if (svg) applyGraphTransform(svg);
}

// ========== Main API ==========

/**
 * Load and render graph for the selected session.
 */
async function loadSessionGraph(sessionId) {
    if (!sessionId) {
        showGraphEmptyState('Select a session to view its graph');
        return;
    }

    const container = document.getElementById('graph-canvas');
    const panel = document.getElementById('graph-detail-panel');
    if (!container) return;

    // Loading state
    container.innerHTML = '<div class="graph-loading"><div class="graph-loading-spinner"></div><div>Loading graph...</div></div>';
    if (panel) panel.classList.remove('graph-detail-panel--open');

    // Reset state
    graphState.svgPan = { x: 0, y: 0 };
    graphState.svgScale = 1;
    graphState.selectedNode = null;

    try {
        const data = await apiCall(`/api/agents/${sessionId}/graph`);
        graphState.graphData = data;

        // Update header
        const typeEl = document.getElementById('graph-type-badge');
        if (typeEl) {
            typeEl.textContent = data.graph_type === 'autonomous' ? 'Autonomous' : 'Simple';
            typeEl.className = `graph-type-badge graph-type-badge--${data.graph_type}`;
        }

        const nameEl = document.getElementById('graph-session-name');
        if (nameEl) nameEl.textContent = data.session_name;

        renderGraph(container, data);
    } catch (err) {
        console.error('Failed to load graph:', err);
        container.innerHTML = `<div class="graph-error"><p>Failed to load graph</p><small>${escapeHtml(err.message)}</small></div>`;
    }
}

function showGraphEmptyState(msg) {
    const container = document.getElementById('graph-canvas');
    if (container) {
        container.innerHTML = `<div class="graph-empty-state"><p>${escapeHtml(msg)}</p></div>`;
    }
}

/**
 * Called when graph tab is shown — load graph for currently selected session.
 */
function refreshGraphTab() {
    const sessionId = state.selectedSessionId;
    loadSessionGraph(sessionId);
}
