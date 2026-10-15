// Locked - Study Workspace Manager (Direction 3: Split Workspace Layout)

// ==========================================
// Global State
// ==========================================
const studyState = {
    projects: [],
    selectedProjectId: null,
    currentTree: null,
    expandedProblems: new Set(),
    selectedNode: null, // { type: 'project' | 'problem' | 'note', id: number }
    activeNote: null,
    activeProblem: null,
    activeProject: null,
    noteSaveTimeout: null,
    problemTitleSaveTimeout: null,
    noteViewMode: 'split', // 'split' | 'edit' | 'preview'
    searchQuery: '',
    mentionMode: false,
    mentionQuery: '',
    mentionStartIndex: 0,
    mentionSelectedIndex: 0,
    mentionItems: []
};

// ==========================================
// Modal Prompt Helper
// ==========================================
function promptStudyInput(modalTitle, inputLabel, showDesc, defaultTitle = '', defaultDesc = '') {
    return new Promise((resolve) => {
        const overlay = document.getElementById('study-overlay');
        const modal = document.getElementById('study-modal');
        const titleEl = document.getElementById('study-modal-title');
        const labelEl = document.getElementById('study-label-title');
        const inputTitle = document.getElementById('study-input-title');
        const groupDesc = document.getElementById('study-group-desc');
        const inputDesc = document.getElementById('study-input-desc');
        const form = document.getElementById('study-form');
        const btnCancel = document.getElementById('btn-cancel-study-modal');
        const btnClose = document.getElementById('btn-close-study-modal');

        titleEl.textContent = modalTitle;
        labelEl.textContent = inputLabel;
        inputTitle.value = defaultTitle;
        inputDesc.value = defaultDesc;

        groupDesc.style.display = showDesc ? 'flex' : 'none';

        overlay.classList.remove('hidden');
        modal.classList.remove('hidden');
        inputTitle.focus();

        const cleanup = () => {
            overlay.classList.add('hidden');
            modal.classList.add('hidden');
            form.onsubmit = null;
            btnCancel.onclick = null;
            if (btnClose) btnClose.onclick = null;
            overlay.onclick = null;
        };

        btnCancel.onclick = () => { cleanup(); resolve(null); };
        if (btnClose) btnClose.onclick = () => { cleanup(); resolve(null); };
        overlay.onclick = () => { cleanup(); resolve(null); };

        form.onsubmit = (e) => {
            e.preventDefault();
            const title = inputTitle.value.trim();
            const desc = inputDesc.value.trim();
            if (title) {
                cleanup();
                resolve({ title, desc });
            }
        };
    });
}

// ==========================================
// API Helper
// ==========================================
async function apiCall(url, method = 'GET', body = null) {
    try {
        const options = { method, headers: {} };
        if (body) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }
        const res = await fetch(url, options);
        return await res.json();
    } catch (e) {
        console.error("Study API error:", e);
        if (window.showToast) window.showToast("Network error: " + e.message, "error");
        return { status: "500", message: e.message };
    }
}

// ==========================================
// URL Navigation & Routing
// ==========================================
function getQueryParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        view: params.get('view') || 'project',
        id: params.get('id') ? parseInt(params.get('id'), 10) : null,
        projectId: params.get('projectId') ? parseInt(params.get('projectId'), 10) : null,
        problemId: params.get('problemId') ? parseInt(params.get('problemId'), 10) : null
    };
}

function updateUrl(params) {
    const url = new URL(window.location);
    Object.keys(params).forEach(key => {
        if (params[key] !== null && params[key] !== undefined) {
            url.searchParams.set(key, params[key]);
        } else {
            url.searchParams.delete(key);
        }
    });
    window.history.pushState({}, '', url);
}

function updateBreadcrumbs(crumbs) {
    const container = document.getElementById('study-breadcrumbs');
    if (!container) return;
    container.innerHTML = '';
    crumbs.forEach((c, idx) => {
        const isLast = idx === crumbs.length - 1;
        const span = document.createElement('span');
        if (isLast) {
            span.textContent = c.label;
            span.style.fontWeight = '700';
            span.style.color = 'var(--text)';
        } else {
            const a = document.createElement('a');
            a.textContent = c.label;
            a.href = '#';
            a.style.color = 'var(--primary)';
            a.style.textDecoration = 'none';
            a.style.fontWeight = '600';
            a.onclick = (e) => {
                e.preventDefault();
                if (c.onClick) c.onClick();
            };
            span.appendChild(a);

            const sep = document.createElement('span');
            sep.textContent = ' / ';
            sep.style.margin = '0 6px';
            sep.style.color = 'var(--text-subtle)';
            span.appendChild(sep);
        }
        container.appendChild(span);
    });
}

function showCanvasView(viewId) {
    document.querySelectorAll('.study-canvas-view').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(viewId);
    if (target) target.classList.add('active');
}

// ==========================================
// Markdown, Math & Mermaid Rendering
// ==========================================
function initMarkdownAndMermaid() {
    try {
        if (typeof marked !== 'undefined' && !window.markedConfigured) {
            marked.use({ gfm: true, breaks: true });
            const katexPlugin = typeof markedKatex === 'function'
                ? markedKatex
                : (typeof window !== 'undefined' && typeof window.markedKatex === 'function' ? window.markedKatex : null);
            if (katexPlugin) {
                marked.use(katexPlugin({ throwOnError: false }));
            }
            window.markedConfigured = true;
        }

        if (typeof mermaid !== 'undefined' && !window.mermaidConfigured) {
            const currentTheme = document.documentElement.getAttribute('data-theme') === 'light' ? 'default' : 'dark';
            mermaid.initialize({
                startOnLoad: false,
                theme: currentTheme,
                securityLevel: 'loose'
            });
            window.mermaidConfigured = true;
        }
    } catch (e) {
        console.warn("Markdown/Mermaid initialization warning:", e);
    }
}

function renderContent(rawText, containerEl) {
    if (!rawText || rawText.trim() === '') {
        containerEl.innerHTML = '<span style="color: var(--text-subtle); font-style: italic;">No content yet...</span>';
        return;
    }

    initMarkdownAndMermaid();

    if (typeof marked === 'undefined') {
        containerEl.innerText = rawText;
        return;
    }

    let parsedHtml = marked.parse(rawText);

    // Transform ```mermaid code blocks into <div class="mermaid">...</div>
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = parsedHtml;

    const mermaidCodeBlocks = tempDiv.querySelectorAll('pre code.language-mermaid');
    mermaidCodeBlocks.forEach(block => {
        const mermaidDiv = document.createElement('div');
        mermaidDiv.className = 'mermaid';
        mermaidDiv.textContent = block.textContent;
        const pre = block.parentElement;
        if (pre && pre.parentElement) {
            pre.parentElement.replaceChild(mermaidDiv, pre);
        }
    });

    containerEl.innerHTML = tempDiv.innerHTML;

    // Render Mermaid diagrams asynchronously if present
    if (typeof mermaid !== 'undefined') {
        const mermaidElements = containerEl.querySelectorAll('.mermaid');
        if (mermaidElements.length > 0) {
            try {
                mermaid.run({ nodes: mermaidElements }).catch(err => {
                    console.warn("Mermaid rendering warning:", err);
                });
            } catch (err) {
                console.warn("Mermaid run error:", err);
            }
        }
    }
}

// ==========================================
// Project Management & Switcher
// ==========================================
async function loadProjectsList() {
    const select = document.getElementById('study-project-select');
    try {
        const res = await apiCall('/api/study/projects');
        studyState.projects = (res && Array.isArray(res.data)) ? res.data : [];

        if (!select) return;

        select.innerHTML = '';
        if (studyState.projects.length === 0) {
            select.innerHTML = '<option value="">No projects found</option>';
            studyState.selectedProjectId = null;
            showCanvasView('view-empty');
            renderTree();
            return;
        }

        studyState.projects.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            select.appendChild(opt);
        });

        // Pick selected project from URL or first project
        const q = getQueryParams();
        if (q.projectId && studyState.projects.some(p => String(p.id) === String(q.projectId))) {
            studyState.selectedProjectId = Number(q.projectId);
        } else if (q.id && q.view === 'project' && studyState.projects.some(p => String(p.id) === String(q.id))) {
            studyState.selectedProjectId = Number(q.id);
        } else if (!studyState.selectedProjectId || !studyState.projects.some(p => String(p.id) === String(studyState.selectedProjectId))) {
            studyState.selectedProjectId = studyState.projects[0].id;
        }

        select.value = studyState.selectedProjectId;
        await loadProjectTree(studyState.selectedProjectId);
    } catch (err) {
        console.error("Failed to load projects list:", err);
        if (select) {
            select.innerHTML = '<option value="">⚠️ Failed to load (Click to retry)</option>';
            select.onclick = () => loadProjectsList();
        }
    }
}

// ==========================================
// Tree Hierarchy Loader & Renderer
// ==========================================
async function loadProjectTree(projectId) {
    if (!projectId) {
        studyState.currentTree = null;
        renderTree();
        return;
    }

    const res = await apiCall(`/api/study/tree?project_id=${projectId}`);
    studyState.currentTree = res.data || { project: null, subprojects: [], problems: [], general_notes: [] };
    renderTree();
}

function renderTree() {
    const container = document.getElementById('study-tree-list');
    if (!container) return;
    container.innerHTML = '';

    if (!studyState.selectedProjectId || !studyState.currentTree || !studyState.currentTree.project) {
        container.innerHTML = `
            <div style="text-align: center; padding: 32px 14px; color: var(--text-muted); font-size: 13px;">
                <div style="font-size: 28px; margin-bottom: 8px;">📂</div>
                <p style="margin: 0 0 12px 0;">No active project selected</p>
                <button class="btn primary btn-sm" onclick="handleNewProject()">+ New Project</button>
            </div>
        `;
        return;
    }

    const tree = studyState.currentTree;
    const query = studyState.searchQuery.toLowerCase().trim();

    // 1. Root Project Node
    const projNode = document.createElement('div');
    const isProjActive = studyState.selectedNode && studyState.selectedNode.type === 'project' && studyState.selectedNode.id === tree.project.id;
    projNode.className = `tree-node ${isProjActive ? 'active' : ''}`;
    projNode.innerHTML = `
        <span class="tree-node-icon">
            <svg width="15" height="15"><use href="#icon-folder"></use></svg>
        </span>
        <span class="tree-node-title" style="font-weight: 700;">${tree.project.name}</span>
        <div class="tree-node-actions">
            <button class="tree-mini-btn btn-tree-add-prob-icon" title="Add problem">+</button>
        </div>
    `;
    projNode.onclick = (e) => {
        if (e.target.closest('.btn-tree-add-prob-icon')) {
            e.stopPropagation();
            handleNewProblem();
            return;
        }
        openProjectView(tree.project);
    };
    container.appendChild(projNode);

    // 2. Sub-projects (if any)
    if (tree.subprojects && tree.subprojects.length > 0) {
        const subLabel = document.createElement('div');
        subLabel.className = 'study-tree-section-label';
        subLabel.textContent = 'Sub-projects';
        container.appendChild(subLabel);

        tree.subprojects.forEach(sub => {
            const subNode = document.createElement('div');
            subNode.className = 'tree-node tree-node-indent-1';
            subNode.innerHTML = `
                <span class="tree-node-icon"><svg width="14" height="14"><use href="#icon-folder"></use></svg></span>
                <span class="tree-node-title">${sub.name}</span>
            `;
            subNode.onclick = () => {
                switchProject(sub.id);
            };
            container.appendChild(subNode);
        });
    }

    // Filter problems and notes if search query exists
    let displayProblems = tree.problems || [];
    let displayGeneralNotes = tree.general_notes || [];

    if (query) {
        displayProblems = displayProblems.filter(p => {
            const matchProb = p.title.toLowerCase().includes(query) || (p.description && p.description.toLowerCase().includes(query));
            const matchNotes = p.notes && p.notes.some(n => n.title.toLowerCase().includes(query) || (n.body && n.body.toLowerCase().includes(query)));
            if (matchNotes) studyState.expandedProblems.add(p.id);
            return matchProb || matchNotes;
        });

        displayGeneralNotes = displayGeneralNotes.filter(n =>
            n.title.toLowerCase().includes(query) || (n.body && n.body.toLowerCase().includes(query))
        );
    }

    // 3. Problems Section
    const probLabel = document.createElement('div');
    probLabel.className = 'study-tree-section-label';
    probLabel.innerHTML = `
        <span>Problems (${displayProblems.length})</span>
        <button class="tree-mini-btn" id="tree-sec-add-problem" title="Add Problem">+</button>
    `;
    container.appendChild(probLabel);
    probLabel.querySelector('#tree-sec-add-problem').onclick = (e) => {
        e.stopPropagation();
        handleNewProblem();
    };

    if (displayProblems.length === 0) {
        const emptyProb = document.createElement('div');
        emptyProb.style.padding = '4px 12px 10px 12px';
        emptyProb.style.fontSize = '12px';
        emptyProb.style.color = 'var(--text-subtle)';
        emptyProb.style.fontStyle = 'italic';
        emptyProb.textContent = query ? 'No matching problems' : 'No problems yet';
        container.appendChild(emptyProb);
    } else {
        displayProblems.forEach(prob => {
            const isExpanded = studyState.expandedProblems.has(prob.id);
            const isProbActive = studyState.selectedNode && studyState.selectedNode.type === 'problem' && studyState.selectedNode.id === prob.id;

            const probRow = document.createElement('div');
            probRow.className = `tree-node tree-node-indent-1 ${isProbActive ? 'active' : ''}`;
            const noteCount = (prob.notes && prob.notes.length) || 0;

            probRow.innerHTML = `
                <span class="tree-node-chevron ${isExpanded ? 'expanded' : ''}">▶</span>
                <span class="tree-node-icon"><svg width="14" height="14"><use href="#icon-tasks"></use></svg></span>
                <span class="tree-node-title" title="${prob.title}">${prob.title}</span>
                <span class="tree-node-badge">${noteCount}</span>
                <div class="tree-node-actions">
                    <button class="tree-mini-btn btn-add-note-inline" title="Add note to problem">+</button>
                    <button class="tree-mini-btn danger btn-del-prob-inline" title="Delete problem">✕</button>
                </div>
            `;

            // Chevron toggle
            const chevron = probRow.querySelector('.tree-node-chevron');
            chevron.onclick = (e) => {
                e.stopPropagation();
                if (studyState.expandedProblems.has(prob.id)) {
                    studyState.expandedProblems.delete(prob.id);
                } else {
                    studyState.expandedProblems.add(prob.id);
                }
                renderTree();
            };

            // Inline buttons
            probRow.querySelector('.btn-add-note-inline').onclick = (e) => {
                e.stopPropagation();
                handleNewNote(prob.id);
            };

            probRow.querySelector('.btn-del-prob-inline').onclick = async (e) => {
                e.stopPropagation();
                if (confirm(`Delete problem "${prob.title}" and its notes?`)) {
                    await apiCall('/api/study/problems', 'DELETE', { id: prob.id });
                    if (window.showToast) window.showToast("Problem deleted", "info");
                    await loadProjectTree(studyState.selectedProjectId);
                    openProjectView(studyState.currentTree.project);
                }
            };

            probRow.onclick = () => {
                openProblemView(prob);
            };

            container.appendChild(probRow);

            // If expanded, render notes under this problem
            if (isExpanded) {
                if (prob.notes && prob.notes.length > 0) {
                    prob.notes.forEach(note => {
                        const isNoteActive = studyState.selectedNode && studyState.selectedNode.type === 'note' && studyState.selectedNode.id === note.id;
                        const noteRow = document.createElement('div');
                        noteRow.className = `tree-node tree-node-indent-2 ${isNoteActive ? 'active' : ''}`;
                        noteRow.innerHTML = `
                            <span class="tree-node-icon"><svg width="13" height="13"><use href="#icon-file"></use></svg></span>
                            <span class="tree-node-title" title="${note.title}">${note.title}</span>
                            <div class="tree-node-actions">
                                <button class="tree-mini-btn danger btn-del-note-inline" title="Delete note">✕</button>
                            </div>
                        `;

                        noteRow.querySelector('.btn-del-note-inline').onclick = async (e) => {
                            e.stopPropagation();
                            if (confirm(`Delete note "${note.title}"?`)) {
                                await apiCall('/api/study/records', 'DELETE', { id: note.id });
                                if (window.showToast) window.showToast("Note deleted", "info");
                                await loadProjectTree(studyState.selectedProjectId);
                                if (studyState.activeNote && studyState.activeNote.id === note.id) {
                                    openProblemView(prob);
                                }
                            }
                        };

                        noteRow.onclick = () => {
                            openNoteView(note, prob);
                        };

                        container.appendChild(noteRow);
                    });
                } else {
                    const emptyNote = document.createElement('div');
                    emptyNote.className = 'tree-node tree-node-indent-2';
                    emptyNote.style.color = 'var(--text-subtle)';
                    emptyNote.style.fontSize = '11px';
                    emptyNote.style.fontStyle = 'italic';
                    emptyNote.innerHTML = `<span>No notes yet. <a href="#" style="color: var(--primary);">+ Add</a></span>`;
                    emptyNote.onclick = (e) => {
                        e.preventDefault();
                        handleNewNote(prob.id);
                    };
                    container.appendChild(emptyNote);
                }
            }
        });
    }

    // 4. General Notes Section
    const genLabel = document.createElement('div');
    genLabel.className = 'study-tree-section-label';
    genLabel.innerHTML = `
        <span>General Notes (${displayGeneralNotes.length})</span>
        <button class="tree-mini-btn" id="tree-sec-add-gen-note" title="Add General Note">+</button>
    `;
    container.appendChild(genLabel);
    genLabel.querySelector('#tree-sec-add-gen-note').onclick = (e) => {
        e.stopPropagation();
        handleNewNote(null);
    };

    if (displayGeneralNotes.length === 0) {
        const emptyGen = document.createElement('div');
        emptyGen.style.padding = '4px 12px 10px 12px';
        emptyGen.style.fontSize = '12px';
        emptyGen.style.color = 'var(--text-subtle)';
        emptyGen.style.fontStyle = 'italic';
        emptyGen.textContent = query ? 'No matching notes' : 'No general notes';
        container.appendChild(emptyGen);
    } else {
        displayGeneralNotes.forEach(note => {
            const isNoteActive = studyState.selectedNode && studyState.selectedNode.type === 'note' && studyState.selectedNode.id === note.id;
            const noteRow = document.createElement('div');
            noteRow.className = `tree-node tree-node-indent-1 ${isNoteActive ? 'active' : ''}`;
            noteRow.innerHTML = `
                <span class="tree-node-icon"><svg width="13" height="13"><use href="#icon-file"></use></svg></span>
                <span class="tree-node-title" title="${note.title}">${note.title}</span>
                <div class="tree-node-actions">
                    <button class="tree-mini-btn danger btn-del-gen-note-inline" title="Delete note">✕</button>
                </div>
            `;

            noteRow.querySelector('.btn-del-gen-note-inline').onclick = async (e) => {
                e.stopPropagation();
                if (confirm(`Delete note "${note.title}"?`)) {
                    await apiCall('/api/study/records', 'DELETE', { id: note.id });
                    if (window.showToast) window.showToast("Note deleted", "info");
                    await loadProjectTree(studyState.selectedProjectId);
                    if (studyState.activeNote && studyState.activeNote.id === note.id) {
                        openProjectView(tree.project);
                    }
                }
            };

            noteRow.onclick = () => {
                openNoteView(note, null);
            };

            container.appendChild(noteRow);
        });
    }
}

// Switch Active Project
async function switchProject(projectId) {
    studyState.selectedProjectId = projectId;
    const select = document.getElementById('study-project-select');
    if (select) select.value = projectId;
    await loadProjectTree(projectId);
    if (studyState.currentTree && studyState.currentTree.project) {
        openProjectView(studyState.currentTree.project);
    }
}

// ==========================================
// Canvas Views Implementations
// ==========================================

// 1. Open Project Overview View
function openProjectView(project) {
    if (!project) return;
    studyState.activeProject = project;
    studyState.activeProblem = null;
    studyState.activeNote = null;
    studyState.selectedNode = { type: 'project', id: project.id };

    updateUrl({ view: 'project', id: project.id, projectId: project.id, problemId: null });
    updateBreadcrumbs([
        { label: 'Projects', onClick: () => openProjectView(project) },
        { label: project.name }
    ]);

    showCanvasView('view-project');
    renderTree();

    document.getElementById('canvas-project-title').textContent = project.name;
    document.getElementById('canvas-project-desc').textContent = project.description || 'No project description provided.';

    const tree = studyState.currentTree || { problems: [], general_notes: [], subprojects: [] };
    const totalNotes = (tree.problems ? tree.problems.reduce((acc, p) => acc + (p.notes ? p.notes.length : 0), 0) : 0) + (tree.general_notes ? tree.general_notes.length : 0);

    document.getElementById('stat-problems-count').textContent = (tree.problems ? tree.problems.length : 0);
    document.getElementById('stat-notes-count').textContent = totalNotes;
    document.getElementById('stat-subprojects-count').textContent = (tree.subprojects ? tree.subprojects.length : 0);

    // Render Problems Quick List
    const probContainer = document.getElementById('project-overview-problems');
    probContainer.innerHTML = '';
    if (tree.problems && tree.problems.length > 0) {
        tree.problems.forEach(p => {
            const item = document.createElement('div');
            item.className = 'list-item';
            item.style.cursor = 'pointer';
            item.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <svg width="15" height="15" style="color: var(--primary);"><use href="#icon-tasks"></use></svg>
                    <div>
                        <div style="font-weight: 600; font-size: 13px; color: var(--text);">${p.title}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">${(p.notes ? p.notes.length : 0)} notes attached</div>
                    </div>
                </div>
                <button class="btn outline btn-sm" style="font-size: 11px; padding: 2px 8px;">Open</button>
            `;
            item.onclick = () => openProblemView(p);
            probContainer.appendChild(item);
        });
    } else {
        probContainer.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); font-style: italic; padding: 10px 0;">No problems yet in this project.</div>';
    }

    // Render General Notes Quick List
    const notesContainer = document.getElementById('project-overview-notes');
    notesContainer.innerHTML = '';
    if (tree.general_notes && tree.general_notes.length > 0) {
        tree.general_notes.forEach(n => {
            const item = document.createElement('div');
            item.className = 'list-item';
            item.style.cursor = 'pointer';
            item.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <svg width="15" height="15" style="color: var(--primary);"><use href="#icon-file"></use></svg>
                    <div style="font-weight: 600; font-size: 13px; color: var(--text);">${n.title}</div>
                </div>
                <button class="btn outline btn-sm" style="font-size: 11px; padding: 2px 8px;">Open</button>
            `;
            item.onclick = () => openNoteView(n, null);
            notesContainer.appendChild(item);
        });
    } else {
        notesContainer.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); font-style: italic; padding: 10px 0;">No general notes in this project.</div>';
    }
}

// 2. Open Problem View (Statement + Attached Notes Grid)
async function openProblemView(prob) {
    if (!prob) return;
    studyState.activeProblem = prob;
    studyState.activeNote = null;
    studyState.selectedNode = { type: 'problem', id: prob.id };
    studyState.expandedProblems.add(prob.id);

    const proj = studyState.currentTree ? studyState.currentTree.project : null;
    updateUrl({ view: 'problem', id: prob.id, projectId: prob.project_id || (proj ? proj.id : null) });
    updateBreadcrumbs([
        { label: proj ? proj.name : 'Project', onClick: () => proj && openProjectView(proj) },
        { label: prob.title }
    ]);

    showCanvasView('view-problem');
    renderTree();

    const titleInput = document.getElementById('canvas-problem-title');
    titleInput.value = prob.title;

    // Handle problem title auto-save
    titleInput.oninput = () => {
        if (studyState.problemTitleSaveTimeout) clearTimeout(studyState.problemTitleSaveTimeout);
        studyState.problemTitleSaveTimeout = setTimeout(async () => {
            const newTitle = titleInput.value.trim() || 'Untitled Problem';
            await apiCall('/api/study/problems', 'PUT', { id: prob.id, title: newTitle });
            prob.title = newTitle;
            loadProjectTree(studyState.selectedProjectId);
        }, 600);
    };

    // Problem Statement Preview
    const descPreview = document.getElementById('canvas-problem-desc-preview');
    const descEditorContainer = document.getElementById('canvas-problem-desc-editor-container');
    const descEditor = document.getElementById('canvas-problem-desc-editor');
    const btnToggleDesc = document.getElementById('btn-toggle-problem-desc');

    renderContent(prob.description || '', descPreview);
    descEditor.value = prob.description || '';
    descEditorContainer.style.display = 'none';

    btnToggleDesc.onclick = () => {
        const isEditing = descEditorContainer.style.display === 'flex';
        descEditorContainer.style.display = isEditing ? 'none' : 'flex';
        btnToggleDesc.textContent = isEditing ? 'Edit Statement' : 'Hide Editor';
        if (!isEditing) descEditor.focus();
    };

    descPreview.ondblclick = () => {
        descEditorContainer.style.display = 'flex';
        btnToggleDesc.textContent = 'Hide Editor';
        descEditor.focus();
    };

    document.getElementById('btn-cancel-problem-desc').onclick = () => {
        descEditor.value = prob.description || '';
        descEditorContainer.style.display = 'none';
        btnToggleDesc.textContent = 'Edit Statement';
    };

    document.getElementById('btn-save-problem-desc').onclick = async () => {
        const newDesc = descEditor.value;
        await apiCall('/api/study/problems', 'PUT', { id: prob.id, description: newDesc });
        prob.description = newDesc;
        renderContent(newDesc, descPreview);
        descEditorContainer.style.display = 'none';
        btnToggleDesc.textContent = 'Edit Statement';
        if (window.showToast) window.showToast("Problem statement saved", "success");
        loadProjectTree(studyState.selectedProjectId);
    };

    // Load and render problem notes grid
    const notesRes = await apiCall(`/api/study/records?problem_id=${prob.id}`);
    const notes = notesRes.data || [];
    prob.notes = notes;

    document.getElementById('canvas-problem-notes-count').textContent = notes.length;
    const grid = document.getElementById('canvas-problem-notes-grid');
    grid.innerHTML = '';

    if (notes.length > 0) {
        notes.forEach(note => {
            const card = document.createElement('div');
            card.className = 'problem-note-card';
            const updatedDate = note.updated_at ? new Date(note.updated_at * 1000).toLocaleDateString() : '';
            const snippet = note.body ? note.body.replace(/[#*`$\n]/g, ' ').substring(0, 140) : 'No content yet';

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                    <h4 class="problem-note-card-title">${note.title}</h4>
                    <button class="tree-mini-btn danger btn-del-card-note" title="Delete note">✕</button>
                </div>
                <div class="problem-note-card-snippet">${snippet}</div>
                <div class="problem-note-card-footer">
                    <span>${updatedDate}</span>
                    <span style="color: var(--primary); font-weight: 600;">Edit Note →</span>
                </div>
            `;

            card.querySelector('.btn-del-card-note').onclick = async (e) => {
                e.stopPropagation();
                if (confirm(`Delete note "${note.title}"?`)) {
                    await apiCall('/api/study/records', 'DELETE', { id: note.id });
                    if (window.showToast) window.showToast("Note deleted", "info");
                    openProblemView(prob);
                    loadProjectTree(studyState.selectedProjectId);
                }
            };

            card.onclick = () => {
                openNoteView(note, prob);
            };

            grid.appendChild(card);
        });
    } else {
        grid.innerHTML = `
            <div style="grid-column: 1 / -1; padding: 36px 16px; text-align: center; background: var(--surface-subtle); border: 1px dashed var(--border); border-radius: var(--radius); color: var(--text-muted);">
                <div style="font-size: 26px; margin-bottom: 6px;">💡</div>
                <div style="font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 4px;">No notes or solutions yet</div>
                <div style="font-size: 12px; margin-bottom: 14px;">Add your ideas, edge cases, algorithms, or code walkthroughs for this problem.</div>
                <button class="btn primary btn-sm" id="btn-empty-prob-add-note">+ Add First Note</button>
            </div>
        `;
        grid.querySelector('#btn-empty-prob-add-note').onclick = () => handleNewNote(prob.id);
    }
}

// 3. Open Note Editor & Preview View
async function openNoteView(noteRef, parentProblem) {
    if (!noteRef) return;

    // Fetch full record if needed
    const res = await apiCall(`/api/study/records/single?id=${noteRef.id}`);
    const note = res.data || noteRef;

    studyState.activeNote = note;
    studyState.activeProblem = parentProblem;
    studyState.selectedNode = { type: 'note', id: note.id };

    const proj = studyState.currentTree ? studyState.currentTree.project : null;
    updateUrl({
        view: 'note',
        id: note.id,
        projectId: note.project_id || (proj ? proj.id : null),
        problemId: note.problem_id || null
    });

    const crumbs = [];
    if (proj) {
        crumbs.push({ label: proj.name, onClick: () => openProjectView(proj) });
    }
    if (parentProblem) {
        crumbs.push({ label: parentProblem.title, onClick: () => openProblemView(parentProblem) });
    }
    crumbs.push({ label: note.title });
    updateBreadcrumbs(crumbs);

    showCanvasView('view-note');
    renderTree();

    const titleInput = document.getElementById('canvas-note-title');
    const editor = document.getElementById('canvas-note-editor');
    const preview = document.getElementById('canvas-note-preview-content');
    const statusEl = document.getElementById('canvas-note-save-status');
    const tagEl = document.getElementById('canvas-note-breadcrumb-tag');

    titleInput.value = note.title;
    editor.value = note.body || '';
    statusEl.textContent = 'Saved';
    statusEl.style.color = 'var(--text-muted)';

    if (parentProblem) {
        tagEl.innerHTML = `Problem: <strong>${parentProblem.title}</strong>`;
    } else {
        tagEl.innerHTML = `General Note &bull; <strong>${proj ? proj.name : 'Project'}</strong>`;
    }

    renderContent(editor.value, preview);

    // Auto-save logic
    const triggerAutoSave = () => {
        if (studyState.noteSaveTimeout) clearTimeout(studyState.noteSaveTimeout);
        statusEl.textContent = 'Saving...';
        statusEl.style.color = 'var(--warning)';

        studyState.noteSaveTimeout = setTimeout(async () => {
            const newTitle = titleInput.value.trim() || 'Untitled Note';
            const newBody = editor.value;

            await apiCall('/api/study/records', 'PUT', {
                id: note.id,
                title: newTitle,
                body: newBody,
                problem_id: note.problem_id
            });

            note.title = newTitle;
            note.body = newBody;
            statusEl.textContent = 'Saved';
            statusEl.style.color = 'var(--text-muted)';
            loadProjectTree(studyState.selectedProjectId);
        }, 700);
    };

    titleInput.oninput = () => {
        triggerAutoSave();
    };

    editor.oninput = () => {
        renderContent(editor.value, preview);
        triggerAutoSave();
        handleMentionInput(editor);
    };

    editor.onkeydown = handleEditorKeydown;

    preview.ondblclick = () => {
        setNoteWorkspaceMode('edit');
        editor.focus();
    };
}

// Note Workspace View Modes: 'split' | 'edit' | 'preview'
function setNoteWorkspaceMode(mode) {
    studyState.noteViewMode = mode;
    const container = document.getElementById('canvas-note-workspace');
    if (!container) return;

    container.classList.remove('mode-edit', 'mode-preview');
    if (mode === 'edit') container.classList.add('mode-edit');
    if (mode === 'preview') container.classList.add('mode-preview');

    document.querySelectorAll('#btn-note-view-split, #btn-note-view-edit, #btn-note-view-preview').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(`btn-note-view-${mode}`);
    if (activeBtn) activeBtn.classList.add('active');
}

// ==========================================
// Mentions Logic (@note or @problem)
// ==========================================
function closeMentionDropdown() {
    studyState.mentionMode = false;
    const dropdown = document.getElementById('note-mention-dropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
    }
}

async function handleMentionInput(editor) {
    const text = editor.value;
    const cursor = editor.selectionStart;
    const beforeCursor = text.substring(0, cursor);
    const match = beforeCursor.match(/(?:^|\s)@([^@\n]*)$/);

    if (match) {
        studyState.mentionMode = true;
        studyState.mentionStartIndex = cursor - match[1].length - 1;
        studyState.mentionQuery = match[1];
        renderMentionDropdown(editor);
    } else {
        closeMentionDropdown();
    }
}

async function renderMentionDropdown(editor) {
    const dropdown = document.getElementById('note-mention-dropdown');
    if (!dropdown || !studyState.mentionMode) return;

    const res = await apiCall(`/api/study/search?q=${encodeURIComponent(studyState.mentionQuery)}`);
    studyState.mentionItems = res.data || [];

    if (studyState.mentionItems.length === 0) {
        dropdown.style.display = 'none';
        return;
    }

    if (studyState.mentionSelectedIndex >= studyState.mentionItems.length) studyState.mentionSelectedIndex = studyState.mentionItems.length - 1;
    if (studyState.mentionSelectedIndex < 0) studyState.mentionSelectedIndex = 0;

    dropdown.innerHTML = '';
    studyState.mentionItems.forEach((item, index) => {
        const div = document.createElement('div');
        div.style.padding = '8px 12px';
        div.style.cursor = 'pointer';
        div.style.borderBottom = '1px solid var(--border-subtle)';
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.gap = '8px';
        div.style.fontSize = '13px';

        if (index === studyState.mentionSelectedIndex) {
            div.style.background = 'var(--primary-light)';
        }

        const iconSvg = item.type === 'record' ? '<svg width="13" height="13"><use href="#icon-file"></use></svg>' : (item.type === 'problem' ? '<svg width="13" height="13"><use href="#icon-tasks"></use></svg>' : '<svg width="13" height="13"><use href="#icon-folder"></use></svg>');
        div.innerHTML = `${iconSvg}<span style="font-weight: 500; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${item.name}</span><span style="font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); text-transform: uppercase;">${item.type}</span>`;

        div.addEventListener('mouseenter', () => {
            studyState.mentionSelectedIndex = index;
            renderMentionDropdown(editor);
        });

        div.addEventListener('mousedown', (e) => {
            e.preventDefault();
            insertMention(item, editor);
        });

        dropdown.appendChild(div);
    });

    dropdown.style.display = 'flex';
    dropdown.style.top = '16px';
    dropdown.style.left = '16px';
}

function insertMention(item, editor) {
    const text = editor.value;
    const before = text.substring(0, studyState.mentionStartIndex);
    const after = text.substring(editor.selectionStart);
    const link = `[${item.name}](/study?view=${item.type}&id=${item.id}&projectId=${item.project_id})`;

    editor.value = before + link + ' ' + after;
    editor.selectionStart = editor.selectionEnd = studyState.mentionStartIndex + link.length + 1;

    closeMentionDropdown();
    editor.dispatchEvent(new Event('input'));
    editor.focus();
}

function handleEditorKeydown(e) {
    if (studyState.mentionMode) {
        if (e.key === 'Escape') {
            closeMentionDropdown();
            e.preventDefault();
        } else if (e.key === 'ArrowDown') {
            studyState.mentionSelectedIndex++;
            renderMentionDropdown(e.target);
            e.preventDefault();
        } else if (e.key === 'ArrowUp') {
            studyState.mentionSelectedIndex--;
            renderMentionDropdown(e.target);
            e.preventDefault();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (studyState.mentionItems.length > 0) {
                insertMention(studyState.mentionItems[studyState.mentionSelectedIndex], e.target);
            } else {
                closeMentionDropdown();
            }
        }
    }
}

// ==========================================
// User Action Handlers (Creation & Deletion)
// ==========================================
async function handleNewProject(parentProjectId = null) {
    const input = await promptStudyInput(parentProjectId ? "Create Sub-project" : "Create New Project", "Project Name:", true);
    if (input) {
        const res = await apiCall('/api/study/projects', 'POST', {
            name: input.title,
            description: input.desc,
            parent_project_id: parentProjectId
        });
        if (window.showToast) window.showToast("Project created!", "success");
        await loadProjectsList();
        if (res.data && res.data.id) {
            switchProject(res.data.id);
        }
    }
}

async function handleNewProblem() {
    if (!studyState.selectedProjectId) {
        if (window.showToast) window.showToast("Please create or select a project first", "warning");
        return;
    }
    const input = await promptStudyInput("New Problem", "Problem Title:", true);
    if (input) {
        const res = await apiCall('/api/study/problems', 'POST', {
            project_id: studyState.selectedProjectId,
            title: input.title,
            description: input.desc
        });
        if (window.showToast) window.showToast("Problem created!", "success");
        await loadProjectTree(studyState.selectedProjectId);
        if (res.data) {
            openProblemView(res.data);
        }
    }
}

async function handleNewNote(problemId = null) {
    if (!studyState.selectedProjectId) {
        if (window.showToast) window.showToast("Please create or select a project first", "warning");
        return;
    }
    const modalTitle = problemId ? "New Note for Problem" : "New General Note";
    const input = await promptStudyInput(modalTitle, "Note Title:", true);
    if (input) {
        const res = await apiCall('/api/study/records', 'POST', {
            title: input.title,
            body: input.desc,
            project_id: studyState.selectedProjectId,
            problem_id: problemId
        });
        if (window.showToast) window.showToast("Note created!", "success");
        await loadProjectTree(studyState.selectedProjectId);

        let parentProb = null;
        if (problemId && studyState.currentTree && studyState.currentTree.problems) {
            parentProb = studyState.currentTree.problems.find(p => p.id === problemId);
        }
        if (res.data) {
            openNoteView(res.data, parentProb);
        }
    }
}

// ==========================================
// Initialization & Event Listeners
// ==========================================
async function initStudyWorkspace() {
    try {
        initMarkdownAndMermaid();
    } catch (e) {
        console.warn("Markdown/Mermaid init error:", e);
    }

    // Project Dropdown Change
    const projectSelect = document.getElementById('study-project-select');
    if (projectSelect) {
        projectSelect.onchange = (e) => {
            const val = parseInt(e.target.value, 10);
            if (val) switchProject(val);
        };
    }

    // Tree Header Buttons
    const btnTreeNewProject = document.getElementById('btn-tree-new-project');
    if (btnTreeNewProject) btnTreeNewProject.onclick = () => handleNewProject(null);

    const btnTreeAddProblem = document.getElementById('btn-tree-add-problem');
    if (btnTreeAddProblem) btnTreeAddProblem.onclick = () => handleNewProblem();

    const btnTreeAddNote = document.getElementById('btn-tree-add-note');
    if (btnTreeAddNote) btnTreeAddNote.onclick = () => {
        // If a problem is currently selected, add note to that problem! Otherwise general note.
        const activeProbId = (studyState.selectedNode && studyState.selectedNode.type === 'problem') ? studyState.selectedNode.id : null;
        handleNewNote(activeProbId);
    };

    const btnTreeAddSubproject = document.getElementById('btn-tree-add-subproject');
    if (btnTreeAddSubproject) btnTreeAddSubproject.onclick = () => handleNewProject(studyState.selectedProjectId);

    // Tree Search Filter
    const treeSearch = document.getElementById('study-tree-search');
    if (treeSearch) {
        treeSearch.oninput = (e) => {
            studyState.searchQuery = e.target.value;
            renderTree();
        };
    }

    // Welcome State Buttons
    const btnWelcomeAddProblem = document.getElementById('btn-welcome-add-problem');
    if (btnWelcomeAddProblem) btnWelcomeAddProblem.onclick = () => handleNewProblem();

    const btnWelcomeAddNote = document.getElementById('btn-welcome-add-note');
    if (btnWelcomeAddNote) btnWelcomeAddNote.onclick = () => handleNewNote(null);

    // Project View Buttons
    const btnProjNewProblem = document.getElementById('btn-proj-new-problem');
    if (btnProjNewProblem) btnProjNewProblem.onclick = () => handleNewProblem();

    const btnProjNewNote = document.getElementById('btn-proj-new-note');
    if (btnProjNewNote) btnProjNewNote.onclick = () => handleNewNote(null);

    const btnQuickAddProblem = document.getElementById('btn-quick-add-problem');
    if (btnQuickAddProblem) btnQuickAddProblem.onclick = () => handleNewProblem();

    const btnQuickAddNote = document.getElementById('btn-quick-add-note');
    if (btnQuickAddNote) btnQuickAddNote.onclick = () => handleNewNote(null);

    const btnProjDelete = document.getElementById('btn-proj-delete');
    if (btnProjDelete) {
        btnProjDelete.onclick = async () => {
            if (!studyState.selectedProjectId) return;
            const projName = studyState.currentTree && studyState.currentTree.project ? studyState.currentTree.project.name : 'this project';
            if (confirm(`Delete project "${projName}" and all associated problems and notes?`)) {
                await apiCall('/api/study/projects', 'DELETE', { id: studyState.selectedProjectId });
                if (window.showToast) window.showToast("Project deleted", "info");
                studyState.selectedProjectId = null;
                await loadProjectsList();
            }
        };
    }

    // Problem View Buttons
    const btnProblemAddNote = document.getElementById('btn-problem-add-note');
    if (btnProblemAddNote) btnProblemAddNote.onclick = () => {
        if (studyState.activeProblem) handleNewNote(studyState.activeProblem.id);
    };

    const btnProblemAddNoteInline = document.getElementById('btn-problem-add-note-inline');
    if (btnProblemAddNoteInline) btnProblemAddNoteInline.onclick = () => {
        if (studyState.activeProblem) handleNewNote(studyState.activeProblem.id);
    };

    const btnProblemDelete = document.getElementById('btn-problem-delete');
    if (btnProblemDelete) {
        btnProblemDelete.onclick = async () => {
            if (!studyState.activeProblem) return;
            if (confirm(`Delete problem "${studyState.activeProblem.title}" and its notes?`)) {
                await apiCall('/api/study/problems', 'DELETE', { id: studyState.activeProblem.id });
                if (window.showToast) window.showToast("Problem deleted", "info");
                await loadProjectTree(studyState.selectedProjectId);
                if (studyState.currentTree && studyState.currentTree.project) {
                    openProjectView(studyState.currentTree.project);
                }
            }
        };
    }

    // Note View Mode Buttons
    const btnModeSplit = document.getElementById('btn-note-view-split');
    if (btnModeSplit) btnModeSplit.onclick = () => setNoteWorkspaceMode('split');

    const btnModeEdit = document.getElementById('btn-note-view-edit');
    if (btnModeEdit) btnModeEdit.onclick = () => setNoteWorkspaceMode('edit');

    const btnModePreview = document.getElementById('btn-note-view-preview');
    if (btnModePreview) btnModePreview.onclick = () => setNoteWorkspaceMode('preview');

    const btnNoteDelete = document.getElementById('btn-canvas-note-delete');
    if (btnNoteDelete) {
        btnNoteDelete.onclick = async () => {
            if (!studyState.activeNote) return;
            if (confirm(`Delete note "${studyState.activeNote.title}"?`)) {
                await apiCall('/api/study/records', 'DELETE', { id: studyState.activeNote.id });
                if (window.showToast) window.showToast("Note deleted", "info");
                await loadProjectTree(studyState.selectedProjectId);
                if (studyState.activeProblem) {
                    openProblemView(studyState.activeProblem);
                } else if (studyState.currentTree && studyState.currentTree.project) {
                    openProjectView(studyState.currentTree.project);
                }
            }
        };
    }

    // Load projects and route
    try {
        await loadProjectsList();
    } catch (e) {
        console.error("loadProjectsList error:", e);
    }

    try {
        const q = getQueryParams();
        if (q.view === 'note' && q.id) {
            let parentProb = null;
            if (q.problemId && studyState.currentTree && studyState.currentTree.problems) {
                parentProb = studyState.currentTree.problems.find(p => p.id === q.problemId);
            }
            await openNoteView({ id: q.id }, parentProb);
        } else if (q.view === 'problem' && q.id) {
            const prob = studyState.currentTree && studyState.currentTree.problems ? studyState.currentTree.problems.find(p => p.id === q.id) : { id: q.id, title: 'Problem' };
            await openProblemView(prob);
        } else if (studyState.currentTree && studyState.currentTree.project) {
            openProjectView(studyState.currentTree.project);
        }
    } catch (e) {
        console.error("Initial routing error:", e);
    }

    window.addEventListener('popstate', async () => {
        const currentQ = getQueryParams();
        if (currentQ.projectId && currentQ.projectId !== studyState.selectedProjectId) {
            await switchProject(currentQ.projectId);
        }
        if (currentQ.view === 'note' && currentQ.id) {
            let parentProb = null;
            if (currentQ.problemId && studyState.currentTree && studyState.currentTree.problems) {
                parentProb = studyState.currentTree.problems.find(p => p.id === currentQ.problemId);
            }
            openNoteView({ id: currentQ.id }, parentProb);
        } else if (currentQ.view === 'problem' && currentQ.id) {
            const prob = studyState.currentTree && studyState.currentTree.problems ? studyState.currentTree.problems.find(p => p.id === currentQ.id) : { id: currentQ.id, title: 'Problem' };
            openProblemView(prob);
        } else if (studyState.currentTree && studyState.currentTree.project) {
            openProjectView(studyState.currentTree.project);
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener("DOMContentLoaded", initStudyWorkspace);
} else {
    initStudyWorkspace();
}
