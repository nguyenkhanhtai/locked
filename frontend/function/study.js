// Study Workspace Manager

// ==========================================
// Modal Prompt Helper
// ==========================================
function promptStudyInput(modalTitle, inputLabel, showDesc, defaultTitle = '') {
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
        inputDesc.value = '';

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

// URL Route Management
function getQueryParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        view: params.get('view') || 'projects',
        id: params.get('id'),
        projectId: params.get('projectId')
    };
}

function updateUrl(params) {
    const url = new URL(window.location);
    Object.keys(params).forEach(key => {
        if (params[key]) {
            url.searchParams.set(key, params[key]);
        } else {
            url.searchParams.delete(key);
        }
    });
    window.history.pushState({}, '', url);
    handleRoute();
}

function updateBreadcrumbs(path) {
    const container = document.getElementById('study-breadcrumbs');
    if (!container) return;
    container.innerHTML = '';
    path.forEach((p, idx) => {
        const isLast = idx === path.length - 1;
        const span = document.createElement('span');
        if (isLast) {
            span.textContent = p.label;
            span.style.fontWeight = '700';
            span.style.color = 'var(--text)';
        } else {
            const a = document.createElement('a');
            a.textContent = p.label;
            a.href = '#';
            a.style.color = 'var(--primary)';
            a.style.textDecoration = 'none';
            a.style.fontWeight = '600';
            a.onclick = (e) => {
                e.preventDefault();
                updateUrl(p.params);
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

function hideAllViews() {
    document.querySelectorAll('.study-view').forEach(el => el.style.display = 'none');
}

// API Helper
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
        console.error("API call error:", e);
        if (window.showToast) window.showToast("Network error: " + e.message, "error");
        return { status: "500", message: e.message };
    }
}

// ==========================================
// 1. Projects View
// ==========================================
async function renderProjectsView() {
    hideAllViews();
    const view = document.getElementById('view-projects');
    if (!view) return;
    view.style.display = 'flex';
    updateBreadcrumbs([{ label: 'Projects', params: { view: 'projects', id: null } }]);

    const list = document.getElementById('project-list');
    list.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">Loading projects...</div>';

    const res = await apiCall('/api/study/projects');
    list.innerHTML = '';
    if (res.data && res.data.length > 0) {
        res.data.forEach(p => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';
            div.innerHTML = `
                <div style="display: flex; align-items: center; gap: 14px;">
                    <div style="width: 40px; height: 40px; border-radius: var(--radius); background: var(--primary-light); color: var(--primary); display: flex; align-items: center; justify-content: center; font-size: 20px;">
                        📁
                    </div>
                    <div>
                        <h4 style="margin: 0; font-size: 15px; font-weight: 700; color: var(--text);">${p.name}</h4>
                        <p style="margin: 3px 0 0 0; font-size: 12px; color: var(--text-muted);">${p.description || 'No description'}</p>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <button class="btn ghost btn-sm btn-del-proj hover-only" style="color: var(--danger);" title="Delete Project">✕</button>
                </div>
            `;
            div.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-del-proj')) return;
                updateUrl({ view: 'project_details', id: p.id });
            });
            div.querySelector('.btn-del-proj').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Delete project "${p.name}" and all associated items?`)) {
                    await apiCall('/api/study/projects', 'DELETE', { id: p.id });
                    if (window.showToast) window.showToast("Project deleted", "info");
                    renderProjectsView();
                }
            });
            list.appendChild(div);
        });
    } else {
        list.innerHTML = `
            <div style="text-align: center; padding: 48px 20px; background: var(--surface); border-radius: var(--radius); border: 1px dashed var(--border);">
                <div style="font-size: 32px; margin-bottom: 8px;">📂</div>
                <h4 style="font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 4px;">No study projects yet</h4>
                <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">Create your first project to organize your subjects and notes.</p>
                <button class="btn primary btn-sm" onclick="document.getElementById('btn-create-project').click()">+ Create Project</button>
            </div>
        `;
    }
}

// ==========================================
// 2. Project Details View
// ==========================================
async function renderProjectDetailsView(projectId) {
    hideAllViews();
    const view = document.getElementById('view-project-details');
    if (!view) return;
    view.style.display = 'flex';

    const subprojectList = document.getElementById('subproject-list');
    const problemList = document.getElementById('problem-list');
    const recordList = document.getElementById('project-record-list');

    subprojectList.innerHTML = '<div style="font-size: 12px; color: var(--text-muted);">Loading...</div>';
    problemList.innerHTML = '<div style="font-size: 12px; color: var(--text-muted);">Loading...</div>';
    recordList.innerHTML = '<div style="font-size: 12px; color: var(--text-muted);">Loading...</div>';

    // Breadcrumbs & Path
    const pathRes = await apiCall(`/api/study/projects/path?id=${projectId}`);
    const breadcrumbs = pathRes.data ? pathRes.data.map(p => ({ label: p.name, params: { view: 'project_details', id: p.id } })) : [];
    breadcrumbs.unshift({ label: 'Projects', params: { view: 'projects', id: null } });
    updateBreadcrumbs(breadcrumbs);

    const currentProject = pathRes.data ? pathRes.data[pathRes.data.length - 1] : null;
    if (currentProject) {
        document.getElementById('project-details-title').innerText = currentProject.name;
        document.getElementById('project-details-desc').innerText = currentProject.description || 'No description';
    }

    // 1. Sub-projects
    const subprojectsRes = await apiCall(`/api/study/projects?parent_project_id=${projectId}`);
    subprojectList.innerHTML = '';
    if (subprojectsRes.data && subprojectsRes.data.length > 0) {
        subprojectsRes.data.forEach(p => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';
            div.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 18px;">📁</span>
                    <div>
                        <div style="font-weight: 700; font-size: 14px; color: var(--text);">${p.name}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">${p.description || ''}</div>
                    </div>
                </div>
                <button class="btn ghost btn-sm btn-del-proj hover-only" style="color: var(--danger);" title="Delete">✕</button>
            `;
            div.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-del-proj')) return;
                updateUrl({ view: 'project_details', id: p.id });
            });
            div.querySelector('.btn-del-proj').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Delete sub-project "${p.name}"?`)) {
                    await apiCall('/api/study/projects', 'DELETE', { id: p.id });
                    renderProjectDetailsView(projectId);
                }
            });
            subprojectList.appendChild(div);
        });
    } else {
        subprojectList.innerHTML = '<p style="color: var(--text-subtle); font-size: 13px; margin: 4px 0;">No sub-projects. Click "+ Sub-project" above to create one.</p>';
    }

    // 2. Problems
    const problemsRes = await apiCall(`/api/study/problems?project_id=${projectId}`);
    problemList.innerHTML = '';
    if (problemsRes.data && problemsRes.data.length > 0) {
        problemsRes.data.forEach(p => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';
            div.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 18px;">📋</span>
                    <div>
                        <div style="font-weight: 700; font-size: 14px; color: var(--text);">${p.title}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">${p.description || 'Open problem board'}</div>
                    </div>
                </div>
                <button class="btn ghost btn-sm btn-del-prob hover-only" style="color: var(--danger);" title="Delete">✕</button>
            `;
            div.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-del-prob')) return;
                updateUrl({ view: 'problem', id: p.id, projectId: projectId });
            });
            div.querySelector('.btn-del-prob').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Delete problem board "${p.title}"?`)) {
                    await apiCall('/api/study/problems', 'DELETE', { id: p.id });
                    renderProjectDetailsView(projectId);
                }
            });
            problemList.appendChild(div);
        });
    } else {
        problemList.innerHTML = '<p style="color: var(--text-subtle); font-size: 13px; margin: 4px 0;">No problems yet. Click "+ Problem" to add a Kanban board.</p>';
    }

    // 3. Records
    const recordsRes = await apiCall(`/api/study/records?project_id=${projectId}`);
    recordList.innerHTML = '';
    if (recordsRes.data && recordsRes.data.length > 0) {
        recordsRes.data.forEach(r => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';
            div.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 18px;">📝</span>
                    <div>
                        <div style="font-weight: 700; font-size: 14px; color: var(--text);">${r.title}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">${r.body ? (r.body.length > 50 ? r.body.substring(0, 50) + "..." : r.body) : 'No content'}</div>
                    </div>
                </div>
                <button class="btn ghost btn-sm btn-del-rec hover-only" style="color: var(--danger);" title="Delete">✕</button>
            `;
            div.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-del-rec')) return;
                updateUrl({ view: 'record', id: r.id, projectId: projectId });
            });
            div.querySelector('.btn-del-rec').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Delete note "${r.title}"?`)) {
                    await apiCall('/api/study/records', 'DELETE', { id: r.id });
                    renderProjectDetailsView(projectId);
                }
            });
            recordList.appendChild(div);
        });
    } else {
        recordList.innerHTML = '<p style="color: var(--text-subtle); font-size: 13px; margin: 4px 0;">No notes in this project. Click "+ Note / Record" to create one.</p>';
    }
}

// ==========================================
// 3. Problem View (Kanban)
// ==========================================
async function renderProblemView(problemId, projectId) {
    hideAllViews();
    const view = document.getElementById('view-problem');
    if (!view) return;
    view.style.display = 'flex';

    const kanban = document.getElementById('problem-kanban');
    kanban.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">Loading columns...</div>';

    const probRes = await apiCall(`/api/study/problems?project_id=${projectId}`);
    let problemTitle = "Problem Kanban";
    const titleInput = document.getElementById('problem-title');
    const editor = document.getElementById('problem-description-editor');
    const preview = document.getElementById('problem-description-preview');
    const descContainer = document.getElementById('problem-desc-container');

    // Default: view mode
    window.isProblemDescVisible = true;
    editor.style.display = 'none';
    preview.style.display = 'block';

    if (probRes.data) {
        const p = probRes.data.find(x => String(x.id) === String(problemId));
        if (p) {
            problemTitle = p.title;
            titleInput.value = p.title;
            editor.value = p.description || '';
            updatePreview(editor.value, preview);
        }
    }

    // Breadcrumbs
    const pathRes = await apiCall(`/api/study/projects/path?id=${projectId}`);
    const breadcrumbs = pathRes.data ? pathRes.data.map(p => ({ label: p.name, params: { view: 'project_details', id: p.id } })) : [];
    breadcrumbs.unshift({ label: 'Projects', params: { view: 'projects', id: null } });
    breadcrumbs.push({ label: problemTitle, params: { view: 'problem', id: problemId, projectId: projectId } });
    updateBreadcrumbs(breadcrumbs);

    let problemSaveTimeout = null;
    const saveProblem = async () => {
        await apiCall('/api/study/problems', 'PUT', {
            id: problemId,
            title: titleInput.value.trim(),
            description: editor.value.trim()
        });
    };

    titleInput.oninput = () => {
        if (problemSaveTimeout) clearTimeout(problemSaveTimeout);
        problemSaveTimeout = setTimeout(saveProblem, 800);
    };

    editor.oninput = () => {
        if (problemSaveTimeout) clearTimeout(problemSaveTimeout);
        updatePreview(editor.value, preview);
        problemSaveTimeout = setTimeout(saveProblem, 800);
    };

    preview.ondblclick = () => {
        editor.style.display = 'block';
        preview.style.display = 'none';
        editor.focus();
    };

    editor.onblur = () => {
        editor.style.display = 'none';
        preview.style.display = 'block';
        saveProblem();
    };

    document.getElementById('btn-toggle-problem-desc').onclick = () => {
        window.isProblemDescVisible = !window.isProblemDescVisible;
        descContainer.style.display = window.isProblemDescVisible ? 'flex' : 'none';
    };

    // Columns
    const res = await apiCall(`/api/study/columns?problem_id=${problemId}`);
    kanban.innerHTML = '';

    if (res.data && res.data.length > 0) {
        for (const col of res.data) {
            const colDiv = document.createElement('div');
            colDiv.className = 'kanban-col';
            colDiv.innerHTML = `
                <div class="kanban-header">
                    <input type="text" class="col-name-input" value="${col.name}"
                        style="font-size: 14px; font-weight: 700; border: none; background: transparent; color: var(--text); outline: none; padding: 2px; flex: 1;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <button class="btn outline btn-sm btn-add-card" style="padding: 2px 8px; font-size: 11px;">+ Card</button>
                        <button class="btn ghost btn-sm btn-del-col hover-only" style="padding: 2px 6px; color: var(--danger);" title="Delete Column">✕</button>
                    </div>
                </div>
                <div class="kanban-cards"></div>
            `;

            kanban.appendChild(colDiv);

            // Fetch cards
            const cardsRes = await apiCall(`/api/study/problem_cards?column_id=${col.id}`);
            const cardsContainer = colDiv.querySelector('.kanban-cards');
            if (cardsRes.data && cardsRes.data.length > 0) {
                cardsRes.data.forEach(card => {
                    const cardDiv = document.createElement('div');
                    cardDiv.className = 'kanban-card';
                    cardDiv.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                            <span style="font-size: 13px; font-weight: 600; color: var(--text);">${card.record_title}</span>
                            <button class="btn ghost btn-sm btn-del-card hover-only" style="padding: 0 4px; color: var(--danger); font-size: 11px;" title="Remove">✕</button>
                        </div>
                    `;
                    cardDiv.addEventListener('click', (e) => {
                        if (e.target.classList.contains('btn-del-card')) return;
                        updateUrl({ view: 'record', id: card.record_id, projectId: projectId });
                    });
                    cardDiv.querySelector('.btn-del-card').addEventListener('click', async (e) => {
                        e.stopPropagation();
                        await apiCall('/api/study/problem_cards', 'DELETE', { id: card.id });
                        renderProblemView(problemId, projectId);
                    });
                    cardsContainer.appendChild(cardDiv);
                });
            } else {
                cardsContainer.innerHTML = '<div style="color: var(--text-subtle); font-size: 12px; padding: 10px 0; text-align: center; font-style: italic;">No cards</div>';
            }

            // Column name edit
            colDiv.querySelector('.col-name-input').addEventListener('blur', async (e) => {
                const newName = e.target.value.trim();
                if (newName && newName !== col.name) {
                    await apiCall('/api/study/columns', 'PUT', { id: col.id, name: newName });
                    col.name = newName;
                }
            });

            // Column delete
            colDiv.querySelector('.btn-del-col').addEventListener('click', async () => {
                if (confirm(`Delete column "${col.name}"?`)) {
                    await apiCall('/api/study/columns', 'DELETE', { id: col.id });
                    renderProblemView(problemId, projectId);
                }
            });

            // Add card
            colDiv.querySelector('.btn-add-card').addEventListener('click', async () => {
                const input = await promptStudyInput("New Problem Card", "Card / Note Title:", true);
                if (input) {
                    const recRes = await apiCall('/api/study/records', 'POST', {
                        title: input.title,
                        body: input.desc,
                        project_id: projectId
                    });
                    await apiCall('/api/study/problem_cards', 'POST', {
                        column_id: col.id,
                        record_id: recRes.data.id,
                        order_index: cardsRes.data ? cardsRes.data.length : 0
                    });
                    renderProblemView(problemId, projectId);
                }
            });
        }
    } else {
        kanban.innerHTML = '<div style="color: var(--text-subtle); font-size: 13px;">No columns in this problem. Click "+ Add Column" to start.</div>';
    }
}

// ==========================================
// 4. Record View (Markdown & LaTeX)
// ==========================================
let recordSaveTimeout = null;
let mentionMode = false;
let mentionQuery = '';
let mentionStartIndex = -1;
let mentionItems = [];
let mentionSelectedIndex = 0;

async function renderRecordView(recordId, projectId) {
    hideAllViews();
    const view = document.getElementById('view-record');
    if (!view) return;
    view.style.display = 'flex';

    const titleInput = document.getElementById('record-title');
    const editor = document.getElementById('record-editor');
    const preview = document.getElementById('record-preview');
    const saveIndicator = document.getElementById('record-save-indicator');

    titleInput.value = 'Loading...';
    editor.value = '';

    window.isRecordEditMode = false;
    editor.style.display = 'none';
    preview.style.display = 'block';

    const res = await apiCall(`/api/study/records/single?id=${recordId}`);
    let recordTitle = "Note";
    if (res.data) {
        recordTitle = res.data.title;
        titleInput.value = res.data.title;
        editor.value = res.data.body || '';
        updatePreview(editor.value, preview);
    }

    const pathRes = await apiCall(`/api/study/projects/path?id=${projectId}`);
    const breadcrumbs = pathRes.data ? pathRes.data.map(p => ({ label: p.name, params: { view: 'project_details', id: p.id } })) : [];
    breadcrumbs.unshift({ label: 'Projects', params: { view: 'projects', id: null } });
    breadcrumbs.push({ label: recordTitle, params: { view: 'record', id: recordId, projectId: projectId } });
    updateBreadcrumbs(breadcrumbs);

    const saveRecord = async () => {
        saveIndicator.innerText = "Saving...";
        await apiCall('/api/study/records', 'PUT', {
            id: recordId,
            title: titleInput.value.trim(),
            body: editor.value.trim()
        });
        saveIndicator.innerText = "Saved";
    };

    const handleInput = () => {
        if (recordSaveTimeout) clearTimeout(recordSaveTimeout);
        updatePreview(editor.value, preview);
        saveIndicator.innerText = "Unsaved";
        recordSaveTimeout = setTimeout(saveRecord, 800);

        // Mention check
        const text = editor.value;
        const cursor = editor.selectionStart;
        const beforeCursor = text.substring(0, cursor);
        const match = beforeCursor.match(/(?:^|\s)@([^@\n]*)$/);
        if (match) {
            mentionMode = true;
            mentionStartIndex = cursor - match[1].length - 1;
            mentionQuery = match[1];
            renderMentionDropdown(editor);
        } else {
            closeMentionDropdown();
        }
    };

    titleInput.oninput = handleInput;
    editor.oninput = handleInput;
    editor.onkeydown = handleEditorKeydown;

    document.getElementById('btn-toggle-preview').onclick = () => {
        window.isRecordEditMode = !window.isRecordEditMode;
        if (window.isRecordEditMode) {
            editor.style.display = 'block';
            preview.style.display = 'block';
            editor.focus();
        } else {
            editor.style.display = 'none';
            preview.style.display = 'block';
            saveRecord();
        }
    };

    preview.ondblclick = () => {
        if (!window.isRecordEditMode) {
            window.isRecordEditMode = true;
            editor.style.display = 'block';
            preview.style.display = 'block';
            editor.focus();
        }
    };
}

// Mention Logic
function closeMentionDropdown() {
    mentionMode = false;
    const dropdown = document.getElementById('mention-dropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
    }
}

async function renderMentionDropdown(editor) {
    const dropdown = document.getElementById('mention-dropdown');
    if (!dropdown || !mentionMode) return;

    const res = await apiCall(`/api/study/search?q=${encodeURIComponent(mentionQuery)}`);
    mentionItems = res.data || [];

    if (mentionItems.length === 0) {
        dropdown.style.display = 'none';
        return;
    }

    if (mentionSelectedIndex >= mentionItems.length) mentionSelectedIndex = mentionItems.length - 1;
    if (mentionSelectedIndex < 0) mentionSelectedIndex = 0;

    dropdown.innerHTML = '';
    mentionItems.forEach((item, index) => {
        const div = document.createElement('div');
        div.style.padding = '8px 12px';
        div.style.cursor = 'pointer';
        div.style.borderBottom = '1px solid var(--border-subtle)';
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.gap = '8px';
        div.style.fontSize = '13px';

        if (index === mentionSelectedIndex) {
            div.style.background = 'var(--primary-light)';
        }

        let icon = item.type === 'record' ? '📝' : (item.type === 'problem' ? '📋' : '📁');
        div.innerHTML = `<span>${icon}</span><span style="font-weight: 700; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${item.name}</span><span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">${item.type}</span>`;

        div.addEventListener('mouseenter', () => {
            mentionSelectedIndex = index;
            renderMentionDropdown(editor);
        });

        div.addEventListener('mousedown', (e) => {
            e.preventDefault();
            insertMention(item, editor);
        });

        dropdown.appendChild(div);
    });

    dropdown.style.display = 'flex';
    dropdown.style.top = '12px';
    dropdown.style.left = '12px';
}

function insertMention(item, editor) {
    const text = editor.value;
    const before = text.substring(0, mentionStartIndex);
    const after = text.substring(editor.selectionStart);
    const link = `[${item.name}](/study?view=${item.type}&id=${item.id}&projectId=${item.project_id})`;

    editor.value = before + link + ' ' + after;
    editor.selectionStart = editor.selectionEnd = mentionStartIndex + link.length + 1;

    closeMentionDropdown();
    editor.dispatchEvent(new Event('input'));
    editor.focus();
}

function handleEditorKeydown(e) {
    if (mentionMode) {
        if (e.key === 'Escape') {
            closeMentionDropdown();
            e.preventDefault();
        } else if (e.key === 'ArrowDown') {
            mentionSelectedIndex++;
            renderMentionDropdown(e.target);
            e.preventDefault();
        } else if (e.key === 'ArrowUp') {
            mentionSelectedIndex--;
            renderMentionDropdown(e.target);
            e.preventDefault();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (mentionItems.length > 0) {
                insertMention(mentionItems[mentionSelectedIndex], e.target);
            } else {
                closeMentionDropdown();
            }
        }
    }
}

// Markdown & Math Preview
function updatePreview(markdownText, previewEl) {
    if (!markdownText || markdownText.trim() === '') {
        previewEl.innerHTML = '<span style="color: var(--text-subtle); font-style: italic;">Double-click to write notes in Markdown and LaTeX...</span>';
        return;
    }

    if (typeof marked === 'undefined') {
        previewEl.innerText = markdownText;
        return;
    }

    if (!window.markedConfigured) {
        marked.use({ gfm: true, breaks: true });
        if (typeof markedKatex !== 'undefined') {
            marked.use(markedKatex({ throwOnError: false }));
        }
        window.markedConfigured = true;
    }

    previewEl.innerHTML = marked.parse(markdownText);
}

// ==========================================
// Route Dispatcher & Event Handlers
// ==========================================
function handleRoute() {
    const params = getQueryParams();
    if (params.view === 'projects' || !params.view) {
        renderProjectsView();
    } else if (params.view === 'project_details') {
        renderProjectDetailsView(params.id);
    } else if (params.view === 'problem') {
        renderProblemView(params.id, params.projectId);
    } else if (params.view === 'record') {
        renderRecordView(params.id, params.projectId);
    } else {
        renderProjectsView();
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // Project actions
    const btnCreateProject = document.getElementById('btn-create-project');
    if (btnCreateProject) {
        btnCreateProject.addEventListener('click', async () => {
            const input = await promptStudyInput("Create New Project", "Project Name:", true);
            if (input) {
                await apiCall('/api/study/projects', 'POST', { name: input.title, description: input.desc });
                if (window.showToast) window.showToast("Project created!", "success");
                renderProjectsView();
            }
        });
    }

    const btnCreateSubproject = document.getElementById('btn-create-subproject');
    if (btnCreateSubproject) {
        btnCreateSubproject.addEventListener('click', async () => {
            const params = getQueryParams();
            if (params.id) {
                const input = await promptStudyInput("New Sub-project", "Sub-project Name:", true);
                if (input) {
                    await apiCall('/api/study/projects', 'POST', { name: input.title, description: input.desc, parent_project_id: params.id });
                    if (window.showToast) window.showToast("Sub-project created!", "success");
                    renderProjectDetailsView(params.id);
                }
            }
        });
    }

    const btnCreateProblem = document.getElementById('btn-create-problem');
    if (btnCreateProblem) {
        btnCreateProblem.addEventListener('click', async () => {
            const params = getQueryParams();
            if (params.id) {
                const input = await promptStudyInput("New Problem", "Problem Title:", true);
                if (input) {
                    await apiCall('/api/study/problems', 'POST', { project_id: params.id, title: input.title, description: input.desc });
                    if (window.showToast) window.showToast("Problem board created!", "success");
                    renderProjectDetailsView(params.id);
                }
            }
        });
    }

    const btnCreateRecord = document.getElementById('btn-create-project-record');
    if (btnCreateRecord) {
        btnCreateRecord.addEventListener('click', async () => {
            const params = getQueryParams();
            if (params.id) {
                const input = await promptStudyInput("New Note", "Note Title:", true);
                if (input) {
                    const res = await apiCall('/api/study/records', 'POST', { title: input.title, body: input.desc, project_id: params.id });
                    if (window.showToast) window.showToast("Note created!", "success");
                    updateUrl({ view: 'record', id: res.data.id, projectId: params.id });
                }
            }
        });
    }

    const btnCreateColumn = document.getElementById('btn-create-column');
    if (btnCreateColumn) {
        btnCreateColumn.addEventListener('click', async () => {
            const params = getQueryParams();
            if (params.id) {
                const input = await promptStudyInput("New Column", "Column Name:", false);
                if (input) {
                    await apiCall('/api/study/columns', 'POST', { problem_id: params.id, name: input.title });
                    if (window.showToast) window.showToast("Column added!", "success");
                    renderProblemView(params.id, params.projectId);
                }
            }
        });
    }

    window.addEventListener('popstate', handleRoute);
    handleRoute();
});
