// Locked - Session Target Page Controller

(function () {
    let activeSession = null;
    let spotlightInterval = null;

    async function api(url, method = 'GET', body = null) {
        try {
            const opts = { method, headers: {} };
            if (body) {
                opts.headers['Content-Type'] = 'application/json';
                opts.body = JSON.stringify(body);
            }
            const res = await fetch(url, opts);
            return await res.json();
        } catch (e) {
            console.error("API error:", e);
            return { status: "500", message: e.message };
        }
    }

    // Load & Render Stats
    async function loadStats() {
        const res = await api('/api/sessions/stats');
        const stats = res.data;
        if (!stats) return;

        document.getElementById('page-stat-total-time').textContent = stats.total_focus_formatted || '0m';
        document.getElementById('page-stat-completed').textContent = stats.completed_sessions || '0';
        document.getElementById('page-stat-today-time').textContent = stats.today_focus_formatted || '0m';
        document.getElementById('page-stat-today-sessions').textContent = `${stats.today_completed_sessions || 0} sessions today`;
        document.getElementById('page-stat-goal-rate').textContent = `${stats.todo_completion_rate}%`;
        document.getElementById('page-stat-todos-ratio').textContent = `${stats.done_todos}/${stats.total_todos} goals met`;
    }

    // Load & Render Spotlight (Active Session)
    async function loadActiveSpotlight() {
        const res = await api('/api/sessions/active');
        const container = document.getElementById('active-session-container');
        activeSession = res.data;

        if (!activeSession || (activeSession.status !== 'running' && activeSession.status !== 'paused')) {
            container.style.display = 'none';
            if (spotlightInterval) clearInterval(spotlightInterval);
            return;
        }

        container.style.display = 'block';
        document.getElementById('spotlight-title').textContent = activeSession.title;
        document.getElementById('spotlight-target-duration').textContent = activeSession.duration_minutes;

        // Merged badge and chips
        const mergedBadge = document.getElementById('spotlight-merged-badge');
        const subheading = document.getElementById('spotlight-subheading');
        const chipsContainer = document.getElementById('spotlight-active-sessions-chips');
        const todosHeading = document.getElementById('spotlight-todos-heading');

        if (activeSession.is_merged) {
            if (mergedBadge) {
                mergedBadge.style.display = 'inline-block';
                mergedBadge.textContent = `MERGED (${activeSession.active_count} SESSIONS)`;
            }
            if (subheading) {
                subheading.textContent = `🔥 MULTIPLE ACTIVE SESSIONS MERGED (${activeSession.active_count} SESSIONS RUNNING)`;
            }
            if (todosHeading) {
                todosHeading.textContent = `Merged Targets & Goals (${activeSession.todos_done}/${activeSession.todos_total})`;
            }
            if (chipsContainer) {
                chipsContainer.style.display = 'flex';
                chipsContainer.innerHTML = (activeSession.active_sessions || []).map((s, idx) => `
                    <span class="active-session-chip ${s.status === 'running' ? 'primary' : ''}">
                        <span>●</span>
                        <strong>${s.title}</strong>
                        <span class="active-session-chip-rem" data-idx="${idx}" style="font-family: var(--font-mono); opacity: 0.85;">(${s.formatted_remaining} left)</span>
                    </span>
                `).join('');
            }
        } else {
            if (mergedBadge) mergedBadge.style.display = 'none';
            if (subheading) subheading.textContent = 'Active Session In Progress';
            if (todosHeading) todosHeading.textContent = 'Session Targets & Checklist';
            if (chipsContainer) chipsContainer.style.display = 'none';
        }

        const statusPill = document.getElementById('spotlight-status-pill');
        const statusText = document.getElementById('spotlight-status-text');
        statusPill.className = `session-widget-status-pill ${activeSession.status}`;
        statusText.textContent = activeSession.status === 'running' ? 'Running' : 'Paused';

        const btnToggle = document.getElementById('btn-spotlight-toggle');
        btnToggle.textContent = activeSession.status === 'running' ? '⏸ Pause' : '▶ Resume';
        btnToggle.className = activeSession.status === 'running' ? 'btn outline btn-sm' : 'btn primary btn-sm';

        renderSpotlightTodos(activeSession.todos || []);
        startSpotlightTimer();
    }

    function renderSpotlightTodos(todos) {
        const listEl = document.getElementById('spotlight-todos-list');
        const countEl = document.getElementById('spotlight-todos-count');
        listEl.innerHTML = '';

        const total = todos.length;
        const done = todos.filter(t => t.done).length;
        countEl.textContent = `(${done}/${total})`;

        if (todos.length === 0) {
            listEl.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); font-style: italic;">No specific goals set yet for this session.</div>`;
            return;
        }

        todos.forEach((todo, idx) => {
            const label = document.createElement('label');
            label.className = `session-widget-todo-item ${todo.done ? 'done' : ''}`;
            label.style.fontSize = '13px';
            label.style.padding = '4px 0';

            const tagHtml = (activeSession && activeSession.is_merged && todo.session_title)
                ? `<span class="session-todo-tag" title="${todo.session_title}">[${todo.session_title}]</span>`
                : '';

            label.innerHTML = `
                <input type="checkbox" ${todo.done ? 'checked' : ''} data-index="${idx}">
                <span style="flex: 1; word-break: break-word;">${tagHtml}${todo.text}</span>
            `;

            label.querySelector('input').addEventListener('change', async (e) => {
                const sId = todo.session_id || activeSession.id;
                const tId = todo.id || String(idx);
                todo.done = e.target.checked;
                label.classList.toggle('done', e.target.checked);

                await api('/api/sessions/todo/toggle', 'POST', {
                    session_id: sId,
                    todo_id: tId,
                    done: e.target.checked
                });
                window.dispatchEvent(new CustomEvent('session-state-changed'));
            });

            listEl.appendChild(label);
        });
    }

    function startSpotlightTimer() {
        if (spotlightInterval) clearInterval(spotlightInterval);

        const updateTick = () => {
            if (!activeSession) return;
            const now = Math.floor(Date.now() / 1000);
            let elapsed = activeSession.elapsed_seconds || 0;
            const startedAt = activeSession.started_at || (activeSession.scheduled_start_at > 0 && activeSession.scheduled_start_at <= now ? activeSession.scheduled_start_at : 0);
            if (activeSession.status === 'running' && startedAt > 0) {
                elapsed += Math.max(0, now - startedAt);
            }

            const total = Math.max(1, activeSession.duration_minutes * 60);
            const remaining = Math.max(0, total - elapsed);

            const hrs = Math.floor(remaining / 3600);
            const mins = Math.floor((remaining % 3600) / 60);
            const secs = remaining % 60;
            let formatted = "";
            if (hrs > 0) {
                formatted = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            } else {
                formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            }

            const timerEl = document.getElementById('spotlight-timer');
            if (timerEl) timerEl.textContent = formatted;

            const percent = Math.min(100, (elapsed / total) * 100);
            const barEl = document.getElementById('spotlight-progress-bar');
            if (barEl) barEl.style.width = percent + '%';

            // Real-time tick for merged chips
            if (activeSession.is_merged && activeSession.active_sessions) {
                const chipRemEls = document.querySelectorAll('.active-session-chip-rem');
                activeSession.active_sessions.forEach((s, idx) => {
                    let sElapsed = s.elapsed_seconds || 0;
                    const sStartedAt = s.started_at || (s.scheduled_start_at > 0 && s.scheduled_start_at <= now ? s.scheduled_start_at : 0);
                    if (s.status === 'running' && sStartedAt > 0) {
                        sElapsed += Math.max(0, now - sStartedAt);
                    }
                    const sTotal = Math.max(1, s.duration_minutes * 60);
                    const sRem = Math.max(0, sTotal - sElapsed);
                    const sHrs = Math.floor(sRem / 3600);
                    const sMins = Math.floor((sRem % 3600) / 60);
                    const sSecs = sRem % 60;
                    const sFmt = sHrs > 0
                        ? `${String(sHrs).padStart(2, '0')}:${String(sMins).padStart(2, '0')}:${String(sSecs).padStart(2, '0')}`
                        : `${String(sMins).padStart(2, '0')}:${String(sSecs).padStart(2, '0')}`;
                    if (chipRemEls[idx]) {
                        chipRemEls[idx].textContent = `(${sFmt} left)`;
                    }
                });
            }
        };

        updateTick();
        spotlightInterval = setInterval(updateTick, 1000);
    }

    // Load Planned (Pending / Scheduled) Sessions
    async function loadPendingSessions() {
        const res = await api('/api/sessions?status=pending');
        const list = res.data || [];
        document.getElementById('count-tab-pending').textContent = list.length;
        const container = document.getElementById('session-pending-list');
        container.innerHTML = '';

        if (list.length === 0) {
            container.innerHTML = `
                <div style="grid-column: 1 / -1; padding: 48px 20px; text-align: center; background: var(--surface); border: 1px dashed var(--border); border-radius: var(--radius);">
                    <div style="font-size: 32px; margin-bottom: 8px;">🎯</div>
                    <h4 style="font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 4px;">No planned session targets</h4>
                    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">Set your next session target and goals in advance so you can jump straight into focus.</p>
                    <button class="btn primary btn-sm" onclick="window.openQuickSessionModal()">+ Create Target (Alt+S)</button>
                </div>
            `;
            return;
        }

        const now = Math.floor(Date.now() / 1000);

        list.forEach(item => {
            const card = document.createElement('div');
            card.className = 'session-card';

            const todosCount = (item.todos || []).length;
            const todosHtml = (item.todos || []).map(t => `
                <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary);">
                    <span style="color: var(--text-muted);">○</span>
                    <span>${t.text}</span>
                </div>
            `).join('');

            // Scheduled badge
            let scheduleBadgeHtml = '';
            if (item.scheduled_start_at > 0) {
                const diffSecs = item.scheduled_start_at - now;
                let relText = '';
                if (diffSecs > 0) {
                    const diffMins = Math.round(diffSecs / 60);
                    if (diffMins < 60) relText = `Starts in ${diffMins}m`;
                    else relText = `Starts in ${Math.round(diffMins / 60)}h`;
                } else {
                    relText = 'Scheduled Window Active';
                }

                scheduleBadgeHtml = `
                    <div style="display: flex; align-items: center; gap: 6px; margin-top: 4px;">
                        <span class="session-schedule-badge">
                            📅 ${item.scheduled_start_formatted}
                        </span>
                        <span style="font-size: 11px; color: var(--warning); font-weight: 600;">${relText}</span>
                    </div>
                `;
            } else {
                scheduleBadgeHtml = `
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                        ⚡ On-demand (Start anytime)
                    </div>
                `;
            }

            const btnText = item.scheduled_start_at > 0 ? '▶ Start Now' : '▶ Start Session';

            card.innerHTML = `
                <div class="session-card-header">
                    <div>
                        <h4 class="session-card-title">${item.title}</h4>
                        <div style="display: flex; align-items: center; gap: 8px; margin-top: 2px;">
                            <span style="font-size: 12px; color: var(--primary); font-weight: 600; font-family: var(--font-mono);">${item.duration_minutes} mins</span>
                            ${item.status === 'scheduled' ? '<span class="session-widget-status-pill paused" style="font-size: 9px; padding: 1px 6px;">Scheduled</span>' : ''}
                        </div>
                        ${scheduleBadgeHtml}
                    </div>
                    <button class="tree-mini-btn danger btn-del-pending" title="Delete target">✕</button>
                </div>
                ${todosCount > 0 ? `<div class="session-card-todos">${todosHtml}</div>` : ''}
                <div class="session-card-footer">
                    <span>${todosCount} goals attached</span>
                    <button class="btn primary btn-sm btn-start-pending">${btnText}</button>
                </div>
            `;

            card.querySelector('.btn-start-pending').onclick = async () => {
                await api('/api/sessions/start', 'POST', { id: item.id });
                if (window.showToast) window.showToast(`🎯 Session started (${item.duration_minutes} mins)`, "success");
                window.dispatchEvent(new CustomEvent('session-state-changed'));
                refreshAll();
            };

            card.querySelector('.btn-del-pending').onclick = async () => {
                if (confirm(`Delete session target "${item.title}"?`)) {
                    await api(`/api/sessions?id=${item.id}`, 'DELETE');
                    if (window.showToast) window.showToast("Target deleted", "info");
                    refreshAll();
                }
            };

            container.appendChild(card);
        });
    }

    // Load Completed Sessions
    async function loadCompletedSessions() {
        const res = await api('/api/sessions?status=completed');
        const list = res.data || [];
        document.getElementById('count-tab-completed').textContent = list.length;
        const container = document.getElementById('session-completed-list');
        container.innerHTML = '';

        if (list.length === 0) {
            container.innerHTML = `
                <div style="padding: 40px 20px; text-align: center; background: var(--surface); border: 1px dashed var(--border); border-radius: var(--radius); color: var(--text-muted); font-size: 13px;">
                    No completed sessions yet. Start a session target above to begin tracking your accomplishments!
                </div>
            `;
            return;
        }

        list.forEach(item => {
            const card = document.createElement('div');
            card.className = 'session-card';

            const endedDate = item.ended_at ? new Date(item.ended_at * 1000).toLocaleString() : '';
            const actualMins = Math.round((item.elapsed_seconds || 0) / 60);

            const totalTodos = (item.todos || []).length;
            const doneTodos = (item.todos || []).filter(t => t.done).length;

            const todosHtml = (item.todos || []).map(t => `
                <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: ${t.done ? 'var(--text-muted)' : 'var(--text)'};">
                    <span>${t.done ? '✓' : '✗'}</span>
                    <span style="${t.done ? 'text-decoration: line-through;' : ''}">${t.text}</span>
                </div>
            `).join('');

            card.innerHTML = `
                <div class="session-card-header">
                    <div>
                        <h4 class="session-card-title">${item.title}</h4>
                        <div style="display: flex; gap: 10px; font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                            <span>Target: <strong>${item.duration_minutes}m</strong></span>
                            <span>Focused: <strong style="color: var(--success);">${actualMins}m</strong></span>
                            <span>Completed: ${endedDate}</span>
                        </div>
                    </div>
                    <button class="tree-mini-btn danger btn-del-completed" title="Delete record">✕</button>
                </div>
                ${totalTodos > 0 ? `<div class="session-card-todos">${todosHtml}</div>` : ''}
                <div class="session-card-footer">
                    <span style="color: ${doneTodos === totalTodos && totalTodos > 0 ? 'var(--success)' : 'var(--text-muted)'}; font-weight: 600;">
                        ${doneTodos}/${totalTodos} goals accomplished
                    </span>
                    <span class="session-widget-status-pill completed">Completed</span>
                </div>
            `;

            card.querySelector('.btn-del-completed').onclick = async () => {
                if (confirm(`Delete history record for "${item.title}"?`)) {
                    await api(`/api/sessions?id=${item.id}`, 'DELETE');
                    refreshAll();
                }
            };

            container.appendChild(card);
        });
    }

    async function refreshAll() {
        await Promise.all([
            loadStats(),
            loadActiveSpotlight(),
            loadPendingSessions(),
            loadCompletedSessions()
        ]);
    }

    // Tab Switching
    document.addEventListener("DOMContentLoaded", () => {
        // Tab buttons
        document.querySelectorAll('.session-tab-btn').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('.session-tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const tab = btn.dataset.tab;
                document.getElementById('session-tab-content-pending').style.display = tab === 'pending' ? 'block' : 'none';
                document.getElementById('session-tab-content-completed').style.display = tab === 'completed' ? 'block' : 'none';
            };
        });

        // Spotlight Pause/Resume
        document.getElementById('btn-spotlight-toggle').onclick = async () => {
            if (!activeSession) return;
            if (activeSession.status === 'running') {
                await api('/api/sessions/pause', 'POST', { id: activeSession.id });
            } else if (activeSession.status === 'paused') {
                await api('/api/sessions/resume', 'POST', { id: activeSession.id });
            }
            window.dispatchEvent(new CustomEvent('session-state-changed'));
            refreshAll();
        };

        // Spotlight Complete
        document.getElementById('btn-spotlight-finish').onclick = async () => {
            if (!activeSession) return;
            const confirmMsg = activeSession.is_merged
                ? `Mark all ${activeSession.active_count} active sessions as completed?`
                : `Mark session "${activeSession.title}" as completed?`;
            if (confirm(confirmMsg)) {
                if (activeSession.is_merged) {
                    await api('/api/sessions/complete', 'POST', { complete_all: true });
                } else {
                    await api('/api/sessions/complete', 'POST', { id: activeSession.id });
                }
                if (window.showToast) window.showToast("Session completed! Excellent work!", "success");
                window.dispatchEvent(new CustomEvent('session-state-changed'));
                refreshAll();
            }
        };

        // Spotlight Abandon
        document.getElementById('btn-spotlight-abandon').onclick = async () => {
            if (!activeSession) return;
            const confirmMsg = activeSession.is_merged
                ? `Cancel all ${activeSession.active_count} active sessions?`
                : `Cancel active session "${activeSession.title}"?`;
            if (confirm(confirmMsg)) {
                await api('/api/sessions/abandon', 'POST', { id: activeSession.id });
                if (window.showToast) window.showToast("Session cancelled", "info");
                window.dispatchEvent(new CustomEvent('session-state-changed'));
                refreshAll();
            }
        };

        // Spotlight Add Todo
        const addInput = document.getElementById('spotlight-add-todo-input');
        const btnAdd = document.getElementById('btn-spotlight-add-todo');
        const submitTodo = async () => {
            if (!activeSession || !addInput) return;
            const text = addInput.value.trim();
            if (text) {
                const targetId = activeSession.primary_session ? activeSession.primary_session.id : activeSession.id;
                const newTodo = { id: String(Date.now()), text: text, done: false };
                activeSession.todos.push(newTodo);
                await api('/api/sessions/todos', 'PUT', {
                    id: targetId,
                    todos: activeSession.todos.filter(t => !t.session_id || t.session_id === targetId)
                });
                addInput.value = '';
                renderSpotlightTodos(activeSession.todos);
                window.dispatchEvent(new CustomEvent('session-state-changed'));
            }
        };

        if (btnAdd) btnAdd.onclick = submitTodo;
        if (addInput) {
            addInput.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submitTodo();
                }
            };
        }

        // Listen to state changes from floating widget
        window.addEventListener('session-state-changed', refreshAll);

        // Gentle background sync
        setInterval(refreshAll, 6000);

        // Immediate refresh when tab becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) refreshAll();
        });

        // Initial Load
        refreshAll();
    });
})();

