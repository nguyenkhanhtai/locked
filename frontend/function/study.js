// Utility to parse query params
// ==========================================
// Custom Prompts
// ==========================================
function promptStudyInput(modalTitle, inputLabel, showDesc, defaultTitle = '') {
    return new Promise((resolve) => {
        const overlay = document.getElementById('study-overlay');
        const drawer = document.getElementById('study-drawer');
        const titleEl = document.getElementById('study-drawer-title');
        const labelEl = document.getElementById('study-label-title');
        const inputTitle = document.getElementById('study-input-title');
        const groupDesc = document.getElementById('study-group-desc');
        const inputDesc = document.getElementById('study-input-desc');
        const form = document.getElementById('study-form');
        const btnCancel = document.getElementById('btn-close-study-drawer');
        
        titleEl.textContent = modalTitle;
        labelEl.textContent = inputLabel;
        inputTitle.value = defaultTitle;
        inputDesc.value = '';
        
        if (showDesc) {
            groupDesc.style.display = 'block';
        } else {
            groupDesc.style.display = 'none';
        }
        
        overlay.classList.remove('hidden');
        drawer.classList.remove('hidden');
        inputTitle.focus();
        
        const cleanup = () => {
            overlay.classList.add('hidden');
            drawer.classList.add('hidden');
            form.onsubmit = null;
            btnCancel.onclick = null;
        };
        
        btnCancel.onclick = () => {
            cleanup();
            resolve(null);
        };
        
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

function promptRecordModal(defaultTitle = '') {
    return new Promise((resolve) => {
        const modal = document.getElementById('record-modal');
        const inputTitle = document.getElementById('record-input-title');
        const inputDesc = document.getElementById('record-input-desc');
        const form = document.getElementById('record-form');
        const btnCancel = document.getElementById('btn-close-record-modal');
        
        inputTitle.value = defaultTitle;
        inputDesc.value = '';
        modal.style.display = 'flex';
        inputTitle.focus();
        
        const cleanup = () => {
            modal.style.display = 'none';
            form.onsubmit = null;
            btnCancel.onclick = null;
        };
        
        btnCancel.onclick = () => {
            cleanup();
            resolve(null);
        };
        
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

function getQueryParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        view: params.get('view') || 'projects',
        id: params.get('id'),
        projectId: params.get('projectId') // for breadcrumbs
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
    container.innerHTML = '';
    path.forEach((p, idx) => {
        const isLast = idx === path.length - 1;
        const span = document.createElement('span');
        if (isLast) {
            span.textContent = p.label;
            span.style.fontWeight = 'bold';
        } else {
            const a = document.createElement('a');
            a.textContent = p.label;
            a.href = '#';
            a.style.color = 'var(--primary)';
            a.style.textDecoration = 'none';
            a.onclick = (e) => {
                e.preventDefault();
                updateUrl(p.params);
            };
            span.appendChild(a);
            
            const sep = document.createElement('span');
            sep.textContent = ' > ';
            sep.style.margin = '0 5px';
            sep.style.color = 'var(--text-muted)';
            span.appendChild(sep);
        }
        container.appendChild(span);
    });
}

function hideAllViews() {
    document.querySelectorAll('.study-view').forEach(el => el.style.display = 'none');
}

// ==========================================
// API Helpers
// ==========================================
async function apiCall(url, method = 'GET', body = null) {
    const options = { method, headers: {} };
    if (body) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }
    const res = await fetch(url, options);
    return await res.json();
}

// ==========================================
// Views
// ==========================================

async function renderProjectsView() {
    hideAllViews();
    document.getElementById('view-projects').style.display = 'flex';
    updateBreadcrumbs([{ label: 'Projects', params: { view: 'projects', id: null } }]);
    
    const list = document.getElementById('project-list');
    list.innerHTML = 'Loading...';
    
    const res = await apiCall('/api/study/projects');
    list.innerHTML = '';
    if (res.data && res.data.length > 0) {
        res.data.forEach(p => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';
            div.innerHTML = `
                <div>
                    <h4 style="margin: 0; color: var(--primary);">${p.name}</h4>
                    <small style="color: #666;">${p.description || 'No description'}</small>
                </div>
                <button class="btn-del-proj btn-del-badge hover-only" title="Delete">✖</button>
            `;
            div.addEventListener('click', (e) => {
                if(e.target.classList.contains('btn-del-proj')) return;
                updateUrl({ view: 'project_details', id: p.id });
            });
            div.querySelector('.btn-del-proj').addEventListener('click', async () => {
                if (confirm('Delete project?')) {
                    await apiCall('/api/study/projects', 'DELETE', { id: p.id });
                    renderProjectsView();
                }
            });
            list.appendChild(div);
        });
    } else {
        list.innerHTML = '<p>No projects found. Create one!</p>';
    }
}

async function renderProjectDetailsView(projectId) {
    hideAllViews();
    document.getElementById('view-project-details').style.display = 'flex';
    
    const subprojectList = document.getElementById('subproject-list');
    const problemList = document.getElementById('problem-list');
    const recordList = document.getElementById('project-record-list');
    
    subprojectList.innerHTML = 'Loading...';
    problemList.innerHTML = 'Loading...';
    recordList.innerHTML = 'Loading...';
    
    updateBreadcrumbs([
        { label: 'Projects', params: { view: 'projects', id: null, projectId: null } },
        { label: 'Project Details', params: { view: 'project_details', id: projectId } }
    ]);
    
    // Fetch Sub-projects
    const subprojectsRes = await apiCall(`/api/study/projects?parent_project_id=${projectId}`);
    subprojectList.innerHTML = '';
    if (subprojectsRes.data && subprojectsRes.data.length > 0) {
        subprojectsRes.data.forEach(p => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';
            div.innerHTML = `
                <div style="flex: 1;">
                    <h4 style="margin: 0; color: var(--primary);">${p.name}</h4>
                    <p style="margin: 5px 0 0 0; font-size: 13px; color: var(--text-light);">${p.description || ''}</p>
                </div>
                <button class="btn-del-proj btn-del-badge hover-only" title="Delete">✖</button>
            `;
            div.addEventListener('click', (e) => {
                if(e.target.classList.contains('btn-del-proj')) return;
                updateUrl({ view: 'project_details', id: p.id });
            });
            div.querySelector('.btn-del-proj').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm('Delete sub-project?')) {
                    await apiCall('/api/study/projects', 'DELETE', { id: p.id });
                    renderProjectDetailsView(projectId);
                }
            });
            subprojectList.appendChild(div);
        });
    } else {
        subprojectList.innerHTML = '<p style="color: var(--text-light); font-size: 13px;">No sub-projects.</p>';
    }
    
    // Fetch Problems
    const problemsRes = await apiCall(`/api/study/problems?project_id=${projectId}`);
    problemList.innerHTML = '';
    if (problemsRes.data && problemsRes.data.length > 0) {
        problemsRes.data.forEach(p => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';
            div.innerHTML = `
                <div style="width: 100%; display: flex; justify-content: space-between; align-items: center;">
                    <h4 style="margin: 0; color: var(--primary);">${p.title}</h4>
                    <button class="btn-del-prob btn-del-badge hover-only" title="Delete">✖</button>
                </div>
            `;
            div.addEventListener('click', (e) => {
                if(e.target.classList.contains('btn-del-prob')) return;
                updateUrl({ view: 'problem', id: p.id, projectId: projectId });
            });
            div.querySelector('.btn-del-prob').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm('Delete problem?')) {
                    await apiCall('/api/study/problems', 'DELETE', { id: p.id });
                    renderProjectDetailsView(projectId);
                }
            });
            problemList.appendChild(div);
        });
    } else {
        problemList.innerHTML = '<p style="color: var(--text-light); font-size: 13px;">No problems found. Create one!</p>';
    }

    // Fetch Records
    const recordsRes = await apiCall(`/api/study/records?project_id=${projectId}`);
    recordList.innerHTML = '';
    if (recordsRes.data && recordsRes.data.length > 0) {
        recordsRes.data.forEach(r => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';
            div.innerHTML = `
                <div style="flex: 1;">
                    <h4 style="margin: 0; color: var(--primary);">${r.title}</h4>
                </div>
            `;
            div.addEventListener('click', () => {
                updateUrl({ view: 'record', id: r.id, projectId: projectId });
            });
            recordList.appendChild(div);
        });
    } else {
        recordList.innerHTML = '<p style="color: var(--text-light); font-size: 13px;">No standalone records.</p>';
    }
}

async function renderProblemView(problemId, projectId) {
    hideAllViews();
    document.getElementById('view-problem').style.display = 'flex';
    
    const kanban = document.getElementById('problem-kanban');
    kanban.innerHTML = 'Loading columns...';
    
    // Fetch Problem details to show description
    const probRes = await apiCall(`/api/study/problems?project_id=${projectId}`);
    let problemTitle = "Problem Kanban";
    if (probRes.data) {
        const p = probRes.data.find(x => String(x.id) === String(problemId));
        if (p) {
            problemTitle = p.title;
            const descEl = document.getElementById('problem-description');
            if (p.description) {
                descEl.textContent = p.description;
                document.getElementById('problem-desc-container').style.display = 'block';
            } else {
                document.getElementById('problem-desc-container').style.display = 'none';
            }
            document.getElementById('problem-title').textContent = p.title;
        }
    }

    updateBreadcrumbs([
        { label: 'Projects', params: { view: 'projects', id: null, projectId: null } },
        { label: 'Project', params: { view: 'project_details', id: projectId } },
        { label: problemTitle, params: { view: 'problem', id: problemId, projectId: projectId } }
    ]);

    
    const res = await apiCall(`/api/study/columns?problem_id=${problemId}`);
    kanban.innerHTML = '';
    
    if (res.data) {
        for (const col of res.data) {
            const colDiv = document.createElement('div');
            colDiv.style.background = 'var(--surface)';
            colDiv.style.border = '1px solid var(--border)';
            colDiv.style.borderRadius = '8px';
            colDiv.style.padding = '10px';
            colDiv.style.display = 'flex';
            colDiv.style.flexDirection = 'column';
            
            colDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <input type="text" class="col-name-input" value="${col.name}" style="font-size: 16px; font-weight: bold; border: none; background: transparent; outline: none; border-bottom: 1px solid transparent; flex: 1; padding: 2px;">
                    <div>
                        <button class="btn outline btn-add-card" style="font-size: 11px; padding: 2px 6px; margin-left: 10px;">+ Card</button>
                    </div>
                </div>
                <div class="cards-container" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px;"></div>
            `;
            
            kanban.appendChild(colDiv);
            
            // Fetch cards
            const cardsRes = await apiCall(`/api/study/problem_cards?column_id=${col.id}`);
            const cardsContainer = colDiv.querySelector('.cards-container');
            if (cardsRes.data) {
                cardsRes.data.forEach(card => {
                    const cardDiv = document.createElement('div');
                    cardDiv.style.background = '#fff';
                    cardDiv.style.border = '1px solid var(--border)';
                    cardDiv.style.borderRadius = '4px';
                    cardDiv.style.padding = '10px';
                    cardDiv.style.cursor = 'pointer';
                    cardDiv.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                    cardDiv.innerHTML = `
                        <div style="font-size: 13px; font-weight: bold;">${card.record_title}</div>
                    `;
                    cardDiv.addEventListener('click', () => {
                        updateUrl({ view: 'record', id: card.record_id, projectId: projectId });
                    });
                    cardsContainer.appendChild(cardDiv);
                });
            }
            
            colDiv.querySelector('.col-name-input').addEventListener('blur', async (e) => {
                const newName = e.target.value.trim();
                if (newName && newName !== col.name) {
                    await apiCall('/api/study/columns', 'PUT', { id: col.id, name: newName });
                    col.name = newName;
                }
            });
            colDiv.querySelector('.col-name-input').addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.target.blur();
                }
            });

            colDiv.querySelector('.btn-add-card').addEventListener('click', async () => {
                const input = await promptRecordModal("New Card");
                if (input) {
                    const recRes = await apiCall('/api/study/records', 'POST', { title: input.title, body: input.desc, project_id: projectId });
                    await apiCall('/api/study/problem_cards', 'POST', {
                        column_id: col.id,
                        record_id: recRes.data.id,
                        order_index: cardsRes.data ? cardsRes.data.length : 0
                    });
                    renderProblemView(problemId, projectId);
                }
            });
        }
    }
}

// Mention Logic State
let mentionMode = false;
let mentionQuery = '';
let mentionStartIndex = -1;
let mentionItems = [];
let mentionSelectedIndex = 0;

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
    if (!dropdown) return;

    if (!mentionMode) {
        dropdown.style.display = 'none';
        return;
    }

    // Fetch items
    const res = await apiCall(`/api/study/search?q=${encodeURIComponent(mentionQuery)}`);
    mentionItems = res.data || [];

    if (mentionItems.length === 0) {
        dropdown.style.display = 'none';
        return;
    }

    // Clamp selected index
    if (mentionSelectedIndex >= mentionItems.length) mentionSelectedIndex = mentionItems.length - 1;
    if (mentionSelectedIndex < 0) mentionSelectedIndex = 0;

    dropdown.innerHTML = '';
    mentionItems.forEach((item, index) => {
        const div = document.createElement('div');
        div.style.padding = '8px 12px';
        div.style.cursor = 'pointer';
        div.style.borderBottom = '1px solid var(--border)';
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.gap = '8px';
        
        if (index === mentionSelectedIndex) {
            div.style.background = 'var(--primary-light, #e0f7fa)';
        }

        let icon = '';
        if (item.type === 'record') icon = '📚';
        else if (item.type === 'problem') icon = '📋';
        else icon = '📁';

        div.innerHTML = `<span>${icon}</span><span style="font-weight: bold; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${item.name}</span><span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">${item.type}</span>`;
        
        div.addEventListener('mouseenter', () => {
            mentionSelectedIndex = index;
            renderMentionDropdown(editor); // Re-render to update highlight
        });
        
        div.addEventListener('mousedown', (e) => {
            e.preventDefault(); // Prevent blur
            insertMention(item, editor);
        });

        dropdown.appendChild(div);
    });

    dropdown.style.display = 'flex';
    // Position it at the top-left of the editor area for simplicity, 
    // or ideally a fixed spot since it's a relative container now.
    dropdown.style.top = '10px';
    dropdown.style.left = '10px';
}

function insertMention(item, editor) {
    const text = editor.value;
    const before = text.substring(0, mentionStartIndex);
    const after = text.substring(editor.selectionStart);
    
    // Markdown link format
    const link = `[${item.name}](/study?view=${item.type}&id=${item.id}&projectId=${item.project_id})`;
    
    editor.value = before + link + ' ' + after;
    editor.selectionStart = editor.selectionEnd = mentionStartIndex + link.length + 1;
    
    closeMentionDropdown();
    // Trigger input event to update preview and save
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

// Global typing timeout
let recordSaveTimeout = null;

async function renderRecordView(recordId, projectId) {
    hideAllViews();
    document.getElementById('view-record').style.display = 'flex';
    
    updateBreadcrumbs([
        { label: 'Projects', params: { view: 'projects', id: null, projectId: null } },
        { label: 'Record Editor', params: { view: 'record', id: recordId, projectId: projectId } }
    ]);
    
    const titleInput = document.getElementById('record-title');
    const editor = document.getElementById('record-editor');
    const preview = document.getElementById('record-preview');
    
    titleInput.value = 'Loading...';
    editor.value = '';
    
    // Set default mode to View
    isEditMode = false;
    editor.style.display = 'none';
    preview.style.display = 'block';
    
    const res = await apiCall(`/api/study/records/single?id=${recordId}`);
    if (res.data) {
        titleInput.value = res.data.title;
        editor.value = res.data.body || '';
        updatePreview(editor.value, preview);
    }
    
    // Auto save on type
    const handleInput = () => {
        if (recordSaveTimeout) clearTimeout(recordSaveTimeout);
        updatePreview(editor.value, preview);
        recordSaveTimeout = setTimeout(async () => {
            await apiCall('/api/study/records', 'PUT', {
                id: recordId,
                title: titleInput.value,
                body: editor.value
            });
        }, 1000); // 1 second debounce
        
        // Mention logic check
        const text = editor.value;
        const cursor = editor.selectionStart;
        const beforeCursor = text.substring(0, cursor);
        
        // Match "@..." where ... is everything after the last @ on the current line
        const match = beforeCursor.match(/(?:^|\s)@([^@\n]*)$/);
        if (match) {
            mentionMode = true;
            mentionStartIndex = cursor - match[1].length - 1; // position of @
            mentionQuery = match[1];
            renderMentionDropdown(editor);
        } else {
            closeMentionDropdown();
        }
    };
    
    titleInput.oninput = handleInput;
    editor.oninput = handleInput;
    editor.onkeydown = handleEditorKeydown;
    
    // Close dropdown when clicking outside
    document.addEventListener('mousedown', (e) => {
        if (mentionMode && e.target !== editor && !e.target.closest('#mention-dropdown')) {
            closeMentionDropdown();
        }
    }, { once: true });
}

// Global setup for marked in study module
function configureStudyMarked() {
    if (!window.marked || window.studyMarkedConfigured) return;
    
    // Ensure core marked config is applied first
    if (typeof window.initMarked === 'function') window.initMarked();

    // Custom renderer for study links
    const renderer = {
        link(href, title, text) {
            if (href && href.includes('/study?view=record&id=')) {
                return `<a href="${href}" class="study-record-link" style="background: var(--primary-light, #e0f7fa); color: var(--primary); padding: 2px 6px; border-radius: 12px; text-decoration: none; font-size: 0.9em; font-weight: bold; border: 1px solid var(--primary);"><span style="margin-right:4px;">📚</span>${text}</a>`;
            }
            if (href && href.includes('/study?view=problem&id=')) {
                return `<a href="${href}" class="study-problem-link" style="background: #fff3e0; color: #e65100; padding: 2px 6px; border-radius: 12px; text-decoration: none; font-size: 0.9em; font-weight: bold; border: 1px solid #ffb74d;"><span style="margin-right:4px;">📋</span>${text}</a>`;
            }
            return false; // Fallback to default
        }
    };
    
    marked.use({ renderer });
    window.studyMarkedConfigured = true;
}

function updatePreview(markdownText, previewEl) {
    if (!window.marked) {
        previewEl.innerHTML = markdownText;
        return;
    }
    
    configureStudyMarked();
    previewEl.innerHTML = marked.parse(markdownText);
}

// ==========================================
// Initialization & Events
// ==========================================

function handleRoute() {
    const params = getQueryParams();
    if (params.view === 'projects') {
        renderProjectsView();
    } else if (params.view === 'project_details') {
        renderProjectDetailsView(params.id);
    } else if (params.view === 'problem') {
        renderProblemView(params.id, params.projectId);
    } else if (params.view === 'record') {
        renderRecordView(params.id, params.projectId);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // Project events
    document.getElementById('btn-create-project').addEventListener('click', async () => {
        const input = await promptStudyInput("New Project", "Project Name:", true);
        if (input) {
            await apiCall('/api/study/projects', 'POST', { name: input.title, description: input.desc });
            renderProjectsView();
        }
    });
    document.getElementById('btn-create-subproject').addEventListener('click', async () => {
        const params = getQueryParams();
        if (params.id) {
            const input = await promptStudyInput("New Sub-project", "Sub-project Name:", true);
            if (input) {
                await apiCall('/api/study/projects', 'POST', { name: input.title, description: input.desc, parent_project_id: params.id });
                renderProjectDetailsView(params.id);
            }
        }
    });

    document.getElementById('btn-create-project-record').addEventListener('click', async () => {
        const params = getQueryParams();
        if (params.id) {
            const input = await promptRecordModal("New Record");
            if (input) {
                await apiCall('/api/study/records', 'POST', { title: input.title, body: input.desc, project_id: params.id });
                renderProjectDetailsView(params.id);
            }
        }
    });
    
    document.getElementById('btn-create-problem').addEventListener('click', async () => {
        const params = getQueryParams();
        if (params.id) {
            const input = await promptStudyInput("New Problem", "Problem Name:", true);
            if (input) {
                await apiCall('/api/study/problems', 'POST', { project_id: params.id, title: input.title, description: input.desc });
                renderProjectDetailsView(params.id);
            }
        }
    });

    document.getElementById('btn-create-column').addEventListener('click', async () => {
        const params = getQueryParams();
        if (params.id) {
            const input = await promptStudyInput("New Column", "Column Name:", false);
            if (input) {
                await apiCall('/api/study/columns', 'POST', { problem_id: params.id, name: input.title });
                renderProblemView(params.id, params.projectId);
            }
        }
    });

    // Record events
    window.isEditMode = false;
    document.getElementById('btn-toggle-preview').addEventListener('click', () => {
        window.isEditMode = !window.isEditMode;
        const editor = document.getElementById('record-editor');
        const preview = document.getElementById('record-preview');
        if (window.isEditMode) {
            editor.style.display = 'block';
            preview.style.display = 'block';
            updatePreview(editor.value, preview);
        } else {
            editor.style.display = 'none';
            preview.style.display = 'block';
        }
    });
    
    document.getElementById('record-preview').addEventListener('dblclick', () => {
        if (!window.isEditMode) {
            window.isEditMode = true;
            document.getElementById('record-editor').style.display = 'block';
            document.getElementById('record-preview').style.display = 'block';
        }
    });
    
    document.getElementById('btn-save-record').addEventListener('click', async () => {
        const params = getQueryParams();
        const title = document.getElementById('record-title').value;
        const body = document.getElementById('record-editor').value;
        if (params.id) {
            await apiCall('/api/study/records', 'PUT', { id: params.id, title, body });
            alert("Saved!");
        }
    });

    window.addEventListener('popstate', handleRoute);
    
    // Initial route
    handleRoute();
});
