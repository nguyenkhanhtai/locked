// Locked - Floating Draggable Session Target Widget & Hotkey Manager (Alt + S)

(function () {
    let activeSession = null;
    let timerInterval = null;
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let initialWidgetX = 0;
    let initialWidgetY = 0;

    // Chime on session completion
    function playChime() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const now = ctx.currentTime;
            const osc1 = ctx.createOscillator();
            const gain1 = ctx.createGain();
            osc1.type = 'sine';
            osc1.frequency.setValueAtTime(587.33, now); // D5
            gain1.gain.setValueAtTime(0.2, now);
            gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
            osc1.connect(gain1);
            gain1.connect(ctx.destination);
            osc1.start(now);
            osc1.stop(now + 0.35);

            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.type = 'sine';
            osc2.frequency.setValueAtTime(880, now + 0.18); // A5
            gain2.gain.setValueAtTime(0.25, now + 0.18);
            gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.8);
            osc2.connect(gain2);
            gain2.connect(ctx.destination);
            osc2.start(now + 0.18);
            osc2.stop(now + 0.8);
        } catch (e) {
            console.warn("Audio chime unsupported or blocked:", e);
        }
    }

    // =========================================================================
    // API HELPERS
    // =========================================================================
    async function sessionApi(url, method = 'GET', body = null) {
        try {
            const opts = { method, headers: {} };
            if (body) {
                opts.headers['Content-Type'] = 'application/json';
                opts.body = JSON.stringify(body);
            }
            const res = await fetch(url, opts);
            return await res.json();
        } catch (e) {
            console.error("Session API Error:", e);
            return { status: "500", message: e.message };
        }
    }

    // =========================================================================
    // DMOJ CONTEST DRAWER & FLOATING DRAGGABLE PILL
    // =========================================================================
    function getWidgetEl() {
        return document.getElementById('floating-session-widget');
    }

    function openSessionDrawer() {
        const drawer = document.getElementById('session-drawer');
        const overlay = document.getElementById('session-drawer-overlay');
        if (drawer) drawer.classList.add('open');
        if (overlay) overlay.classList.add('open');
    }

    function closeSessionDrawer() {
        const drawer = document.getElementById('session-drawer');
        const overlay = document.getElementById('session-drawer-overlay');
        if (drawer) drawer.classList.remove('open');
        if (overlay) overlay.classList.remove('open');
    }

    function toggleSessionDrawer() {
        const drawer = document.getElementById('session-drawer');
        if (drawer && drawer.classList.contains('open')) {
            closeSessionDrawer();
        } else {
            openSessionDrawer();
        }
    }

    let hasMoved = false;

    function initDraggable(widget) {
        // Restore saved position
        try {
            const savedPos = JSON.parse(localStorage.getItem('locked-widget-pos'));
            if (savedPos && typeof savedPos.left === 'number' && typeof savedPos.top === 'number') {
                const maxLeft = Math.max(10, window.innerWidth - 60);
                const maxTop = Math.max(10, window.innerHeight - 60);
                const clampLeft = Math.min(Math.max(10, savedPos.left), maxLeft);
                const clampTop = Math.min(Math.max(10, savedPos.top), maxTop);
                widget.style.left = clampLeft + 'px';
                widget.style.top = clampTop + 'px';
                widget.style.bottom = 'auto';
                widget.style.right = 'auto';
            }
        } catch (e) { }

        // Mouse Dragging on entire widget pill
        widget.addEventListener('mousedown', (e) => {
            if (e.target.closest('button') || e.target.closest('.btn-widget-pip') || e.target.closest('.dmoj-pill-btn-pip') || e.target.closest('.dmoj-pill-toggle-icon')) {
                return;
            }
            e.preventDefault(); // Stop browser native text drag
            isDragging = true;
            hasMoved = false;
            dragStartX = e.clientX;
            dragStartY = e.clientY;
            const rect = widget.getBoundingClientRect();
            initialWidgetX = rect.left;
            initialWidgetY = rect.top;
            widget.style.cursor = 'grabbing';
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - dragStartX;
            const dy = e.clientY - dragStartY;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                hasMoved = true;
            }

            let newX = initialWidgetX + dx;
            let newY = initialWidgetY + dy;

            const rect = widget.getBoundingClientRect();
            const minX = 8;
            const maxX = window.innerWidth - rect.width - 8;
            const minY = 8;
            const maxY = window.innerHeight - rect.height - 8;

            newX = Math.min(Math.max(minX, newX), Math.max(minX, maxX));
            newY = Math.min(Math.max(minY, newY), Math.max(minY, maxY));

            widget.style.left = newX + 'px';
            widget.style.top = newY + 'px';
            widget.style.bottom = 'auto';
            widget.style.right = 'auto';
        });

        window.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                widget.style.cursor = 'grab';
                if (hasMoved) {
                    const rect = widget.getBoundingClientRect();
                    localStorage.setItem('locked-widget-pos', JSON.stringify({ left: rect.left, top: rect.top }));
                }
            }
        });

        // Touch Dragging
        widget.addEventListener('touchstart', (e) => {
            if (e.target.closest('button') || e.target.closest('.btn-widget-pip') || e.target.closest('.dmoj-pill-btn-pip') || e.target.closest('.dmoj-pill-toggle-icon')) {
                return;
            }
            const touch = e.touches[0];
            isDragging = true;
            hasMoved = false;
            dragStartX = touch.clientX;
            dragStartY = touch.clientY;
            const rect = widget.getBoundingClientRect();
            initialWidgetX = rect.left;
            initialWidgetY = rect.top;
        }, { passive: true });

        window.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            const touch = e.touches[0];
            const dx = touch.clientX - dragStartX;
            const dy = touch.clientY - dragStartY;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                hasMoved = true;
            }

            let newX = initialWidgetX + dx;
            let newY = initialWidgetY + dy;

            const rect = widget.getBoundingClientRect();
            const minX = 8;
            const maxX = window.innerWidth - rect.width - 8;
            const minY = 8;
            const maxY = window.innerHeight - rect.height - 8;

            newX = Math.min(Math.max(minX, newX), Math.max(minX, maxX));
            newY = Math.min(Math.max(minY, newY), Math.max(minY, maxY));

            widget.style.left = newX + 'px';
            widget.style.top = newY + 'px';
            widget.style.bottom = 'auto';
            widget.style.right = 'auto';
        }, { passive: true });

        window.addEventListener('touchend', () => {
            if (isDragging) {
                isDragging = false;
                if (hasMoved) {
                    const rect = widget.getBoundingClientRect();
                    localStorage.setItem('locked-widget-pos', JSON.stringify({ left: rect.left, top: rect.top }));
                }
            }
        });

        // Click on widget pill toggles the DMOJ Contest Drawer (if not dragged)
        widget.addEventListener('click', (e) => {
            if (hasMoved) {
                hasMoved = false;
                return;
            }
            if (e.target.closest('button') || e.target.closest('.btn-widget-pip') || e.target.closest('.dmoj-pill-btn-pip')) {
                return;
            }
            toggleSessionDrawer();
        });
    }

    function renderWidget(session) {
        const widget = getWidgetEl();
        const drawer = document.getElementById('session-drawer');
        if (!widget) return;

        if (!session || (session.status !== 'running' && session.status !== 'paused')) {
            widget.style.display = 'none';
            if (drawer) closeSessionDrawer();
            if (timerInterval) clearInterval(timerInterval);
            activeSession = null;
            return;
        }

        activeSession = session;
        widget.style.display = 'inline-flex';

        // Set status classes
        widget.classList.remove('active-running', 'active-paused', 'active-completed');
        if (session.status === 'running') widget.classList.add('active-running');
        else if (session.status === 'paused') widget.classList.add('active-paused');

        // Merged badges
        const mergedBadge = document.getElementById('widget-merged-badge');
        if (mergedBadge) {
            if (session.is_merged) {
                mergedBadge.style.display = 'inline-block';
                mergedBadge.textContent = `MERGED (${session.active_count})`;
            } else {
                mergedBadge.style.display = 'none';
            }
        }
        const drawerMergedBadge = document.getElementById('drawer-merged-badge');
        if (drawerMergedBadge) {
            if (session.is_merged) {
                drawerMergedBadge.style.display = 'inline-block';
                drawerMergedBadge.textContent = `MERGED (${session.active_count})`;
            } else {
                drawerMergedBadge.style.display = 'none';
            }
        }

        // Header label
        const headerLabel = document.getElementById('widget-todos-header-label');
        if (headerLabel) {
            headerLabel.textContent = session.is_merged ? 'Merged Targets' : 'Contest Problems & Targets';
        }

        // Titles
        const pillTitle = document.getElementById('dmoj-pill-title') || widget.querySelector('.session-widget-drag-title-text');
        if (pillTitle) pillTitle.textContent = session.title;
        const drawerTitle = document.getElementById('drawer-session-title');
        if (drawerTitle) drawerTitle.textContent = session.title;
        const drawerDuration = document.getElementById('drawer-duration-text');
        if (drawerDuration) drawerDuration.textContent = session.duration_minutes;

        // Drawer Status pill
        const drawerStatusPill = document.getElementById('drawer-status-pill');
        const drawerStatusText = document.getElementById('drawer-status-text');
        if (drawerStatusPill) {
            drawerStatusPill.className = `session-widget-status-pill ${session.status}`;
        }
        if (drawerStatusText) {
            drawerStatusText.textContent = session.status === 'running' ? 'Running' : 'Paused';
        }

        // Toggle buttons in drawer and widget
        document.querySelectorAll('.btn-widget-toggle-pause').forEach(btn => {
            btn.innerHTML = session.status === 'running'
                ? `<span>⏸ Pause</span>`
                : `<span>▶ Resume</span>`;
            btn.className = session.status === 'running' ? 'btn outline btn-sm btn-widget-toggle-pause' : 'btn primary btn-sm btn-widget-toggle-pause';
        });

        // Merged active sessions breakdown chips
        const mergedChipsContainer = document.getElementById('drawer-merged-chips-container');
        const mergedChipsList = document.getElementById('drawer-merged-chips-list');
        if (mergedChipsContainer && mergedChipsList) {
            if (session.is_merged && session.active_sessions && session.active_sessions.length > 1) {
                mergedChipsContainer.style.display = 'block';
                mergedChipsList.innerHTML = '';
                session.active_sessions.forEach(s => {
                    const chip = document.createElement('div');
                    chip.className = `active-session-chip ${s.id === session.id ? 'primary-chip' : ''}`;
                    chip.setAttribute('data-session-id', s.id);
                    chip.innerHTML = `
                        <span class="active-chip-title">${s.title}</span>
                        <span class="active-chip-time drawer-chip-rem" data-mins="${s.duration_minutes}" data-started="${s.started_at || 0}" data-status="${s.status}" data-elapsed="${s.elapsed_seconds || 0}">--:--</span>
                    `;
                    mergedChipsList.appendChild(chip);
                });
            } else {
                mergedChipsContainer.style.display = 'none';
            }
        }

        // To-dos List
        renderWidgetTodos(session.todos || [], session.is_merged);

        // Start local timer loop
        startTimerLoop();
    }

    function renderWidgetTodos(todos, isMerged = false) {
        const containers = document.querySelectorAll('.session-widget-todos-list');
        const countEls = document.querySelectorAll('.session-widget-todos-count');
        const total = todos.length;
        const doneCount = todos.filter(t => t.done).length;

        countEls.forEach(el => {
            el.textContent = `(${doneCount}/${total})`;
        });

        containers.forEach(container => {
            container.innerHTML = '';
            if (todos.length === 0) {
                container.innerHTML = `<div style="color: var(--text-muted); font-size: 11px; font-style: italic; padding: 6px 0;">Chưa có mục tiêu cụ thể. Thêm mục tiêu bên dưới:</div>`;
                return;
            }

            todos.forEach((todo, idx) => {
                const item = document.createElement('label');
                item.className = `session-widget-todo-item ${todo.done ? 'done' : ''}`;
                
                const tagHtml = (isMerged && todo.session_title) 
                    ? `<span class="session-todo-tag" title="${todo.session_title}">[${todo.session_title}]</span>` 
                    : '';

                item.innerHTML = `
                    <input type="checkbox" ${todo.done ? 'checked' : ''} data-index="${idx}" data-session-id="${todo.session_id || ''}" data-todo-id="${todo.id || ''}">
                    <span style="flex: 1; word-break: break-word;">${tagHtml}${todo.text}</span>
                `;

                item.querySelector('input').addEventListener('change', async (e) => {
                    const sId = todo.session_id || activeSession.id;
                    const tId = todo.id || String(idx);
                    todo.done = e.target.checked;
                    item.classList.toggle('done', e.target.checked);

                    await sessionApi('/api/sessions/todo/toggle', 'POST', {
                        session_id: sId,
                        todo_id: tId,
                        done: e.target.checked
                    });
                    window.dispatchEvent(new CustomEvent('session-state-changed'));
                });

                container.appendChild(item);
            });
        });
    }

    function startTimerLoop() {
        if (timerInterval) clearInterval(timerInterval);

        const updateTick = () => {
            if (!activeSession) return;
            const widget = getWidgetEl();
            if (!widget) return;

            const now = Math.floor(Date.now() / 1000);
            let elapsed = activeSession.elapsed_seconds || 0;
            const startedAt = activeSession.started_at || (activeSession.scheduled_start_at > 0 && activeSession.scheduled_start_at <= now ? activeSession.scheduled_start_at : 0);
            if (activeSession.status === 'running' && startedAt > 0) {
                elapsed += Math.max(0, now - startedAt);
            }

            const total = Math.max(1, activeSession.duration_minutes * 60);
            const remaining = Math.max(0, total - elapsed);

            // Format mm:ss or hh:mm:ss
            const hrs = Math.floor(remaining / 3600);
            const mins = Math.floor((remaining % 3600) / 60);
            const secs = remaining % 60;
            let formatted = "";
            if (hrs > 0) {
                formatted = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            } else {
                formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            }

            // Update all countdown elements (pill, drawer, widget)
            const timerEls = document.querySelectorAll('.session-widget-countdown, #dmoj-pill-timer, #drawer-countdown');
            timerEls.forEach(el => {
                el.textContent = formatted;
            });

            // Progress Bar
            const percent = Math.min(100, (elapsed / total) * 100);
            const bars = document.querySelectorAll('.session-widget-progress-bar, #drawer-progress-bar');
            bars.forEach(b => {
                b.style.width = percent + '%';
            });

            // Update merged chips remaining times
            const nowSec = now;
            document.querySelectorAll('.drawer-chip-rem').forEach(chip => {
                const chipStatus = chip.getAttribute('data-status');
                const chipStarted = parseInt(chip.getAttribute('data-started'), 10) || 0;
                let chipElapsed = parseInt(chip.getAttribute('data-elapsed'), 10) || 0;
                const chipDuration = parseInt(chip.getAttribute('data-mins'), 10) || 25;
                if (chipStatus === 'running' && chipStarted > 0) {
                    chipElapsed += Math.max(0, nowSec - chipStarted);
                }
                const chipRem = Math.max(0, chipDuration * 60 - chipElapsed);
                const m = Math.floor(chipRem / 60);
                const s = chipRem % 60;
                chip.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
            });

            // Sync with Desktop PiP window if open
            if (pipWindowInstance && !pipWindowInstance.closed) {
                const pipTimer = pipWindowInstance.document.querySelector('.pip-timer');
                if (pipTimer) pipTimer.textContent = formatted;
                pipWindowInstance.document.title = `${formatted} - ${activeSession.title}`;
                const pipBar = pipWindowInstance.document.querySelector('.pip-progress-bar');
                if (pipBar) pipBar.style.width = percent + '%';
            }

            // Check if finished
            if (remaining === 0 && !activeSession._alerted) {
                activeSession._alerted = true;
                playChime();
                if (window.showToast) window.showToast("🎉 Session Target time is up! Great focus!", "success");
            }
        };

        updateTick();
    }

    // =========================================================================
    // DESKTOP PICTURE-IN-PICTURE (ALWAYS-ON-TOP OVER VSCODE / ALL APPS)
    // =========================================================================
    let pipWindowInstance = null;

    async function toggleDesktopPiP() {
        if (!activeSession) {
            if (window.showToast) window.showToast("No active session to pop out", "warning");
            return;
        }

        if (pipWindowInstance && !pipWindowInstance.closed) {
            pipWindowInstance.close();
            pipWindowInstance = null;
            return;
        }

        if ('documentPictureInPicture' in window) {
            try {
                const pipWindow = await window.documentPictureInPicture.requestWindow({
                    width: 340,
                    height: 320,
                });
                pipWindowInstance = pipWindow;

                // Copy theme and stylesheets
                pipWindow.document.documentElement.setAttribute('data-theme', document.documentElement.getAttribute('data-theme') || 'dark');

                document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
                    const l = pipWindow.document.createElement('link');
                    l.rel = 'stylesheet';
                    l.href = link.href;
                    pipWindow.document.head.appendChild(l);
                });

                document.querySelectorAll('style').forEach(st => {
                    const s = pipWindow.document.createElement('style');
                    s.textContent = st.textContent;
                    pipWindow.document.head.appendChild(s);
                });

                pipWindow.document.body.style.margin = '0';
                pipWindow.document.body.style.padding = '10px';
                pipWindow.document.body.style.background = 'var(--bg-color, #111318)';
                pipWindow.document.body.style.color = 'var(--text, #f8fafc)';
                pipWindow.document.body.style.fontFamily = 'var(--font-sans, sans-serif)';
                pipWindow.document.body.style.overflow = 'hidden';
                pipWindow.document.body.style.boxSizing = 'border-box';
                pipWindow.document.body.style.height = '100vh';
                pipWindow.document.body.style.display = 'flex';
                pipWindow.document.body.style.flexDirection = 'column';

                const container = pipWindow.document.createElement('div');
                container.className = 'popout-container';
                container.style.cssText = 'flex: 1; display: flex; flex-direction: column; gap: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 12px; box-shadow: var(--shadow-md); overflow: hidden;';

                const isMerged = Boolean(activeSession.is_merged);
                const mergedBadgeHtml = isMerged 
                    ? `<span class="session-widget-merged-badge" style="font-size: 8px; padding: 1px 5px;">MERGED (${activeSession.active_count})</span>` 
                    : '';

                container.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 6px; min-width: 0; flex: 1;">
                            <span style="color: var(--primary); font-size: 14px;">🎯</span>
                            <span class="pip-title" style="font-size: 13px; font-weight: 700; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${activeSession.title}</span>
                            ${mergedBadgeHtml}
                        </div>
                        <div style="display: flex; align-items: center; gap: 4px;">
                            <span class="pip-status-pill session-widget-status-pill ${activeSession.status}" style="font-size: 9px; padding: 2px 6px;">
                                <span class="session-widget-status-dot"></span>
                                <span class="pip-status-text">${activeSession.status === 'running' ? 'Running' : 'Paused'}</span>
                            </span>
                            <button type="button" class="session-widget-btn-mini btn-pip-close" title="Close PiP">✕</button>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div class="pip-timer" style="font-size: 32px; font-weight: 800; font-family: 'JetBrains Mono', monospace; line-height: 1; color: var(--text);">25:00</div>
                        <div style="display: flex; gap: 6px;">
                            <button type="button" class="btn outline btn-sm btn-pip-toggle" style="padding: 4px 8px; font-size: 11px;">⏸ Pause</button>
                            <button type="button" class="btn primary btn-sm btn-pip-finish" style="padding: 4px 8px; font-size: 11px;">✓ Done</button>
                        </div>
                    </div>
                    <div class="session-widget-progress-bg">
                        <div class="session-widget-progress-bar pip-progress-bar" style="width: 0%;"></div>
                    </div>
                    <div style="flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--border-subtle); padding-top: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">
                            <span>${isMerged ? 'Merged Targets' : 'Targets'}</span>
                            <span class="pip-todos-count">(0/0)</span>
                        </div>
                        <div class="pip-todos-list" style="display: flex; flex-direction: column; gap: 6px;"></div>
                    </div>
                    <div style="display: flex; gap: 6px; padding-top: 4px; border-top: 1px solid var(--border-subtle);">
                        <input type="text" class="pip-todo-input" placeholder="+ Add target..." style="flex: 1; padding: 4px 8px; font-size: 11px; background: var(--surface-subtle); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); outline: none;">
                        <button type="button" class="btn ghost btn-sm btn-pip-add-todo" style="padding: 2px 6px;">+</button>
                    </div>
                `;
                pipWindow.document.body.appendChild(container);

                function updatePipTodos() {
                    const listEl = container.querySelector('.pip-todos-list');
                    const countEl = container.querySelector('.pip-todos-count');
                    listEl.innerHTML = '';
                    const total = (activeSession.todos || []).length;
                    const done = (activeSession.todos || []).filter(t => t.done).length;
                    countEl.textContent = `(${done}/${total})`;

                    (activeSession.todos || []).forEach((t, idx) => {
                        const label = pipWindow.document.createElement('label');
                        label.className = `session-widget-todo-item ${t.done ? 'done' : ''}`;
                        label.style.fontSize = '12px';
                        
                        const tagHtml = (activeSession.is_merged && t.session_title)
                            ? `<span class="session-todo-tag" style="font-size: 9px; padding: 1px 4px;">[${t.session_title}]</span>`
                            : '';

                        label.innerHTML = `
                            <input type="checkbox" ${t.done ? 'checked' : ''} data-index="${idx}">
                            <span style="flex: 1; word-break: break-word;">${tagHtml}${t.text}</span>
                        `;
                        label.querySelector('input').addEventListener('change', async (e) => {
                            const sId = t.session_id || activeSession.id;
                            const tId = t.id || String(idx);
                            t.done = e.target.checked;
                            label.classList.toggle('done', e.target.checked);
                            await sessionApi('/api/sessions/todo/toggle', 'POST', {
                                session_id: sId,
                                todo_id: tId,
                                done: e.target.checked
                            });
                            window.dispatchEvent(new CustomEvent('session-state-changed'));
                        });
                        listEl.appendChild(label);
                    });
                }

                updatePipTodos();

                container.querySelector('.btn-pip-close').onclick = () => {
                    pipWindow.close();
                };

                container.querySelector('.btn-pip-toggle').onclick = async () => {
                    if (!activeSession) return;
                    if (activeSession.status === 'running') {
                        const res = await sessionApi('/api/sessions/pause', 'POST', { id: activeSession.id });
                        if (res.data) activeSession = res.data;
                    } else {
                        const res = await sessionApi('/api/sessions/resume', 'POST', { id: activeSession.id });
                        if (res.data) activeSession = res.data;
                    }
                    const btn = container.querySelector('.btn-pip-toggle');
                    btn.textContent = activeSession.status === 'running' ? '⏸ Pause' : '▶ Resume';
                    const pill = container.querySelector('.pip-status-pill');
                    pill.className = `pip-status-pill session-widget-status-pill ${activeSession.status}`;
                    container.querySelector('.pip-status-text').textContent = activeSession.status === 'running' ? 'Running' : 'Paused';
                    renderWidget(activeSession);
                    window.dispatchEvent(new CustomEvent('session-state-changed'));
                };

                container.querySelector('.btn-pip-finish').onclick = async () => {
                    if (!activeSession) return;
                    const confirmMsg = activeSession.is_merged
                        ? `Complete all ${activeSession.active_count} active sessions now?`
                        : `Finish session "${activeSession.title}" now?`;
                    if (confirm(confirmMsg)) {
                        if (activeSession.is_merged) {
                            await sessionApi('/api/sessions/complete', 'POST', { complete_all: true });
                        } else {
                            await sessionApi('/api/sessions/complete', 'POST', { id: activeSession.id });
                        }
                        playChime();
                        pipWindow.close();
                        await checkActiveSession();
                        window.dispatchEvent(new CustomEvent('session-state-changed'));
                    }
                };

                const addInput = container.querySelector('.pip-todo-input');
                const btnAdd = container.querySelector('.btn-pip-add-todo');
                const addPipGoal = async () => {
                    if (!activeSession || !addInput) return;
                    const txt = addInput.value.trim();
                    if (txt) {
                        activeSession.todos.push({ id: String(Date.now()), text: txt, done: false });
                        await sessionApi('/api/sessions/todos', 'PUT', { id: activeSession.id, todos: activeSession.todos });
                        addInput.value = '';
                        updatePipTodos();
                        renderWidgetTodos(activeSession.todos, activeSession.is_merged);
                        window.dispatchEvent(new CustomEvent('session-state-changed'));
                    }
                };
                btnAdd.onclick = addPipGoal;
                addInput.onkeydown = (e) => { if (e.key === 'Enter') addPipGoal(); };

                pipWindow.addEventListener('pagehide', () => {
                    pipWindowInstance = null;
                    const w = getWidgetEl();
                    if (w && activeSession) w.style.display = 'flex';
                });

                // Hide in-page widget when PiP is active so they don't duplicate on screen
                const w = getWidgetEl();
                if (w) w.style.display = 'none';

                if (window.showToast) window.showToast("📌 Pop out: Timer is now floating always-on-top over VSCode & all apps!", "success");
                return;
            } catch (err) {
                console.warn("Document PiP request failed, falling back to window.open:", err);
            }
        }

        // Fallback: window.open
        openPopoutWindow();
    }

    function openPopoutWindow() {
        window.open(
            '/session-widget-popout',
            'LockedSessionTargetPopout',
            'width=340,height=76,resizable=yes,scrollbars=no,status=no,location=no'
        );
    }

    // Refresh active session from server
    async function checkActiveSession() {
        const res = await sessionApi('/api/sessions/active');
        if (res.data) {
            renderWidget(res.data);
        } else {
            const widget = getWidgetEl();
            if (widget) widget.style.display = 'none';
            if (timerInterval) clearInterval(timerInterval);
            activeSession = null;
        }
    }

    // =========================================================================
    // QUICK SESSION MODAL (ALT + S)
    // =========================================================================
    let newSessionTodos = [];

    function setQuickSessionMode(mode) {
        document.querySelectorAll('.session-mode-card').forEach(c => c.classList.remove('active'));
        const activeCard = document.getElementById(`mode-card-${mode}`);
        if (activeCard) {
            activeCard.classList.add('active');
            const radio = activeCard.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        }

        const scheduleBox = document.getElementById('quick-session-schedule-box');
        const submitBtn = document.getElementById('btn-submit-quick-session');

        if (mode === 'scheduled') {
            if (scheduleBox) scheduleBox.style.display = 'flex';
            if (submitBtn) submitBtn.textContent = 'Schedule Session Target';
            updateSchedulePreview();
        } else if (mode === 'pending') {
            if (scheduleBox) scheduleBox.style.display = 'none';
            if (submitBtn) submitBtn.textContent = 'Save Planned Target';
        } else {
            if (scheduleBox) scheduleBox.style.display = 'none';
            if (submitBtn) submitBtn.textContent = 'Start Session Target';
        }
    }

    function setupDefaultScheduleTime() {
        const input = document.getElementById('quick-session-scheduled-datetime');
        if (!input) return;
        const now = new Date();
        now.setMinutes(Math.ceil((now.getMinutes() + 10) / 15) * 15);
        now.setSeconds(0);
        now.setMilliseconds(0);
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const mins = String(now.getMinutes()).padStart(2, '0');
        input.value = `${year}-${month}-${day}T${hours}:${mins}`;
        updateSchedulePreview();
    }

    function updateSchedulePreview() {
        const preview = document.getElementById('quick-session-schedule-preview');
        const dtInput = document.getElementById('quick-session-scheduled-datetime');
        const minsInput = document.getElementById('quick-session-custom-mins');
        if (!preview || !dtInput || !dtInput.value) return;

        const startDt = new Date(dtInput.value);
        if (isNaN(startDt.getTime())) return;

        const durationMins = parseInt(minsInput ? minsInput.value : 25, 10) || 25;
        const endDt = new Date(startDt.getTime() + durationMins * 60 * 1000);

        const formatTime = (d) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        const formatDate = (d) => `${d.getDate()}/${d.getMonth() + 1}`;

        preview.textContent = `📅 Diễn ra: ${formatDate(startDt)} từ ${formatTime(startDt)} đến ${formatTime(endDt)} (${durationMins}m)`;
    }

    function openQuickSessionModal() {
        const overlay = document.getElementById('quick-session-overlay');
        const modal = document.getElementById('quick-session-modal');
        if (!overlay || !modal) return;

        // Reset fields
        const titleInput = document.getElementById('quick-session-title');
        titleInput.value = '';
        newSessionTodos = [];
        renderQuickModalTodos();

        // Default duration 25
        document.querySelectorAll('.duration-pill').forEach(p => p.classList.remove('active'));
        const defaultPill = document.querySelector('.duration-pill[data-mins="25"]');
        if (defaultPill) defaultPill.classList.add('active');
        document.getElementById('quick-session-custom-mins').value = '25';

        // Timing mode setup: default to immediate
        setQuickSessionMode('immediate');

        // Concurrent session option: show if active session is currently running/paused
        const concurrentRow = document.getElementById('quick-session-concurrent-row');
        if (concurrentRow) {
            concurrentRow.style.display = (activeSession && (activeSession.status === 'running' || activeSession.status === 'paused')) ? 'flex' : 'none';
        }

        // Setup default scheduled datetime
        setupDefaultScheduleTime();

        overlay.classList.remove('hidden');
        modal.classList.remove('hidden');
        titleInput.focus();
    }

    function closeQuickSessionModal() {
        const overlay = document.getElementById('quick-session-overlay');
        const modal = document.getElementById('quick-session-modal');
        if (overlay) overlay.classList.add('hidden');
        if (modal) modal.classList.add('hidden');
    }

    function renderQuickModalTodos() {
        const container = document.getElementById('quick-session-todos-list');
        if (!container) return;
        container.innerHTML = '';

        if (newSessionTodos.length === 0) {
            container.innerHTML = `<div style="font-size: 11px; color: var(--text-muted); font-style: italic; padding: 4px 0;">No goals added yet. Type below and press Enter.</div>`;
            return;
        }

        newSessionTodos.forEach((item, idx) => {
            const div = document.createElement('div');
            div.className = 'session-todo-build-item';
            div.innerHTML = `
                <span>${idx + 1}. ${item.text}</span>
                <button type="button" data-index="${idx}">✕</button>
            `;
            div.querySelector('button').onclick = () => {
                newSessionTodos.splice(idx, 1);
                renderQuickModalTodos();
            };
            container.appendChild(div);
        });
    }

    // =========================================================================
    // INITIALIZATION & EVENT LISTENERS
    // =========================================================================
    function initSessionWidget() {
        const widget = getWidgetEl();
        if (widget) {
            initDraggable(widget);
        }

        // ==========================================
        // Widget Scale Management
        // ==========================================
        let widgetScale = parseFloat(localStorage.getItem('locked-widget-scale')) || 0.85;

        function setWidgetScale(scale) {
            scale = Math.min(1.4, Math.max(0.5, Math.round(scale * 100) / 100));
            widgetScale = scale;
            localStorage.setItem('locked-widget-scale', String(scale));
            applyWidgetScale();
        }

        function applyWidgetScale() {
            document.documentElement.style.setProperty('--widget-scale', widgetScale);
            const pct = Math.round(widgetScale * 100);
            const cycleBtn = document.getElementById('btn-inpage-scale-cycle');
            const scaleText = document.getElementById('inpage-widget-scale-text');
            if (cycleBtn) cycleBtn.textContent = `${pct}%`;
            if (scaleText) scaleText.textContent = `${pct}%`;
        }

        applyWidgetScale();

        const scalePresets = [0.85, 0.75, 0.65, 1.0];
        const inpageCycleBtn = document.getElementById('btn-inpage-scale-cycle');
        if (inpageCycleBtn) {
            inpageCycleBtn.onclick = (e) => {
                e.stopPropagation();
                let currIdx = scalePresets.findIndex(p => Math.abs(p - widgetScale) < 0.04);
                let nextIdx = (currIdx + 1) % scalePresets.length;
                setWidgetScale(scalePresets[nextIdx]);
            };
        }

        document.querySelectorAll('.btn-inpage-scale-dec').forEach(btn => {
            btn.onclick = () => setWidgetScale(widgetScale - 0.05);
        });

        document.querySelectorAll('.btn-inpage-scale-inc').forEach(btn => {
            btn.onclick = () => setWidgetScale(widgetScale + 0.05);
        });

        document.querySelectorAll('.btn-inpage-scale-reset').forEach(btn => {
            btn.onclick = () => setWidgetScale(0.85);
        });

        // ==========================================
        // DMOJ Contest Drawer Listeners
        // ==========================================
        const btnCloseDrawer = document.getElementById('btn-close-session-drawer');
        const drawerOverlay = document.getElementById('session-drawer-overlay');
        if (btnCloseDrawer) btnCloseDrawer.onclick = closeSessionDrawer;
        if (drawerOverlay) drawerOverlay.onclick = closeSessionDrawer;

        // Escape key to close drawer
        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const drawer = document.getElementById('session-drawer');
                if (drawer && drawer.classList.contains('open')) {
                    closeSessionDrawer();
                }
            }
        });

        // Desktop PiP (Always-on-top over other apps)
        document.querySelectorAll('.btn-widget-pip').forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                toggleDesktopPiP();
            };
        });

        // Pause / Resume buttons (pill & drawer)
        document.querySelectorAll('.btn-widget-toggle-pause').forEach(btn => {
            btn.onclick = async (e) => {
                e.stopPropagation();
                if (!activeSession) return;
                const targetId = activeSession.primary_session ? activeSession.primary_session.id : activeSession.id;
                if (activeSession.status === 'running') {
                    const res = await sessionApi('/api/sessions/pause', 'POST', { id: targetId });
                    if (res.data) renderWidget(res.data);
                } else if (activeSession.status === 'paused') {
                    const res = await sessionApi('/api/sessions/resume', 'POST', { id: targetId });
                    if (res.data) renderWidget(res.data);
                }
                window.dispatchEvent(new CustomEvent('session-state-changed'));
            };
        });

        // Finish session buttons (pill & drawer)
        document.querySelectorAll('.btn-widget-finish').forEach(btn => {
            btn.onclick = async (e) => {
                e.stopPropagation();
                if (!activeSession) return;
                const confirmMsg = activeSession.is_merged
                    ? `Hoàn thành tất cả ${activeSession.active_count} phiên đang chạy?`
                    : `Hoàn thành phiên "${activeSession.title}" bây giờ?`;
                if (confirm(confirmMsg)) {
                    if (activeSession.is_merged) {
                        await sessionApi('/api/sessions/complete', 'POST', { complete_all: true });
                    } else {
                        const targetId = activeSession.primary_session ? activeSession.primary_session.id : activeSession.id;
                        await sessionApi('/api/sessions/complete', 'POST', { id: targetId });
                    }
                    if (window.showToast) window.showToast("🎉 Chúc mừng! Phiên mục tiêu đã hoàn thành!", "success");
                    playChime();
                    closeSessionDrawer();
                    await checkActiveSession();
                    window.dispatchEvent(new CustomEvent('session-state-changed'));
                }
            };
        });

        // Abandon / Cancel session buttons
        document.querySelectorAll('.btn-widget-abandon, #drawer-btn-abandon').forEach(btn => {
            btn.onclick = async (e) => {
                e.stopPropagation();
                if (!activeSession) return;
                const confirmMsg = activeSession.is_merged
                    ? `Hủy bỏ tất cả ${activeSession.active_count} phiên đang chạy?`
                    : `Hủy bỏ phiên "${activeSession.title}"?`;
                if (confirm(confirmMsg)) {
                    if (activeSession.is_merged) {
                        await sessionApi('/api/sessions/abandon', 'POST', { abandon_all: true });
                    } else {
                        const targetId = activeSession.primary_session ? activeSession.primary_session.id : activeSession.id;
                        await sessionApi('/api/sessions/abandon', 'POST', { id: targetId });
                    }
                    if (window.showToast) window.showToast("Đã hủy phiên làm việc.", "info");
                    closeSessionDrawer();
                    await checkActiveSession();
                    window.dispatchEvent(new CustomEvent('session-state-changed'));
                }
            };
        });

        // Quick add to-do from drawer / widget input
        const submitWidgetTodo = async (input) => {
            if (!activeSession || !input) return;
            const txt = input.value.trim();
            if (txt) {
                const targetId = activeSession.primary_session ? activeSession.primary_session.id : activeSession.id;
                const newTodo = { id: String(Date.now()), text: txt, done: false };
                activeSession.todos = activeSession.todos || [];
                activeSession.todos.push(newTodo);
                await sessionApi('/api/sessions/todos', 'PUT', {
                    id: targetId,
                    todos: activeSession.todos.filter(t => !t.session_id || t.session_id === targetId)
                });
                input.value = '';
                renderWidgetTodos(activeSession.todos, activeSession.is_merged);
                window.dispatchEvent(new CustomEvent('session-state-changed'));
            }
        };

        document.querySelectorAll('.session-widget-btn-add-todo').forEach(btn => {
            btn.onclick = () => {
                const parent = btn.closest('.session-drawer-add-row') || btn.parentElement;
                const input = parent ? parent.querySelector('.session-widget-add-todo-input') : document.querySelector('.session-widget-add-todo-input');
                submitWidgetTodo(input);
            };
        });

        document.querySelectorAll('.session-widget-add-todo-input').forEach(input => {
            input.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submitWidgetTodo(input);
                }
            };
        });

        // ==========================================
        // Hotkey Modal Listeners
        // ==========================================
        const overlay = document.getElementById('quick-session-overlay');
        const btnClose = document.getElementById('btn-close-quick-session');
        const btnCancel = document.getElementById('btn-cancel-quick-session');
        if (overlay) overlay.onclick = closeQuickSessionModal;
        if (btnClose) btnClose.onclick = closeQuickSessionModal;
        if (btnCancel) btnCancel.onclick = closeQuickSessionModal;

        // Preset Duration Chips
        document.querySelectorAll('.duration-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                document.querySelectorAll('.duration-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                const mins = pill.dataset.mins;
                const customInput = document.getElementById('quick-session-custom-mins');
                if (customInput && mins) customInput.value = mins;
                updateSchedulePreview();
            });
        });

        // Mode cards
        document.querySelectorAll('.session-mode-card').forEach(card => {
            card.addEventListener('click', () => {
                const radio = card.querySelector('input[type="radio"]');
                if (radio) {
                    setQuickSessionMode(radio.value);
                }
            });
        });

        const schedInput = document.getElementById('quick-session-scheduled-datetime');
        if (schedInput) schedInput.addEventListener('input', updateSchedulePreview);
        const minsCustomInput = document.getElementById('quick-session-custom-mins');
        if (minsCustomInput) minsCustomInput.addEventListener('input', updateSchedulePreview);

        // Add To-do inside Quick Modal
        const quickTodoInput = document.getElementById('quick-session-todo-input');
        const btnQuickAddTodo = document.getElementById('btn-quick-add-todo');
        const addModalTodo = () => {
            if (!quickTodoInput) return;
            const text = quickTodoInput.value.trim();
            if (text) {
                newSessionTodos.push({ id: String(Date.now()), text: text, done: false });
                quickTodoInput.value = '';
                renderQuickModalTodos();
                quickTodoInput.focus();
            }
        };

        if (btnQuickAddTodo) btnQuickAddTodo.onclick = addModalTodo;
        if (quickTodoInput) {
            quickTodoInput.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    addModalTodo();
                }
            };
        }

        // Submit Quick Session Form
        const quickForm = document.getElementById('quick-session-form');
        if (quickForm) {
            quickForm.onsubmit = async (e) => {
                e.preventDefault();
                const title = document.getElementById('quick-session-title').value.trim() || 'Focused Study Session';
                const mins = parseInt(document.getElementById('quick-session-custom-mins').value, 10) || 25;
                
                const selectedModeRadio = document.querySelector('input[name="quick_session_mode"]:checked');
                const mode = selectedModeRadio ? selectedModeRadio.value : 'immediate';

                let startNow = false;
                let scheduledStartAt = 0;

                if (mode === 'immediate') {
                    startNow = true;
                } else if (mode === 'scheduled') {
                    const dtVal = document.getElementById('quick-session-scheduled-datetime').value;
                    if (dtVal) {
                        const parsed = new Date(dtVal).getTime();
                        if (!isNaN(parsed)) {
                            scheduledStartAt = Math.floor(parsed / 1000);
                        }
                    }
                }

                const keepOthersEl = document.getElementById('quick-session-keep-others');
                const pauseOthers = keepOthersEl ? !keepOthersEl.checked : false;

                // If user typed something in todo input but forgot to click add
                if (quickTodoInput && quickTodoInput.value.trim()) {
                    newSessionTodos.push({ id: String(Date.now()), text: quickTodoInput.value.trim(), done: false });
                }

                const res = await sessionApi('/api/sessions', 'POST', {
                    title: title,
                    duration_minutes: mins,
                    todos: newSessionTodos,
                    start_immediately: startNow,
                    scheduled_start_at: scheduledStartAt,
                    pause_others: pauseOthers
                });

                closeQuickSessionModal();

                if (res.data) {
                    if (startNow) {
                        if (window.showToast) window.showToast(`🎯 Session started (${mins} mins). Focus time!`, "success");
                        renderWidget(res.data);
                    } else if (scheduledStartAt > 0) {
                        if (window.showToast) window.showToast(`📅 Session scheduled for ${new Date(scheduledStartAt * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`, "success");
                    } else {
                        if (window.showToast) window.showToast("Target created! Start whenever ready.", "info");
                    }
                    window.dispatchEvent(new CustomEvent('session-state-changed'));
                }
            };
        }

        // Global Hotkey Listener: Alt + S
        window.addEventListener('keydown', (e) => {
            if (e.altKey && (e.key === 's' || e.key === 'S')) {
                e.preventDefault();
                openQuickSessionModal();
            }
        });

        // Check active session on initial load
        checkActiveSession();

        // Listen for internal session changes
        window.addEventListener('session-state-changed', checkActiveSession);

        // Gentle background sync (keeps popout / other tabs synced)
        setInterval(checkActiveSession, 5000);

        // Immediate sync when tab becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) checkActiveSession();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener("DOMContentLoaded", initSessionWidget);
    } else {
        initSessionWidget();
    }

    // Expose helpers globally
    window.openQuickSessionModal = openQuickSessionModal;
    window.toggleDesktopPiP = toggleDesktopPiP;
    window.openSessionDrawer = openSessionDrawer;
    window.closeSessionDrawer = closeSessionDrawer;
    window.toggleSessionDrawer = toggleSessionDrawer;
})();

