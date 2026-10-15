document.addEventListener("DOMContentLoaded", () => {
    const btnAddTask = document.getElementById("btn-add-task");
    const btnCloseTaskDrawer = document.getElementById("btn-close-task-drawer");
    const btnCancelTaskDrawer = document.getElementById("btn-cancel-task-drawer");
    const taskForm = document.getElementById("task-form");
    const taskIdInput = document.getElementById("task-id");
    const btnDeleteTask = document.getElementById("btn-delete-task");
    const taskList = document.getElementById("task-list");
    const overlay = document.getElementById("overlay");

    const taskSort = document.getElementById("task-sort");
    const taskFilterLabel = document.getElementById("task-filter-label");
    const taskFilterPriority = document.getElementById("task-filter-priority");
    const taskPageSize = document.getElementById("task-page-size");
    const btnPrevPage = document.getElementById("btn-prev-page");
    const btnNextPage = document.getElementById("btn-next-page");
    const pageInfo = document.getElementById("page-info");

    let currentGanttDate = new Date();
    currentGanttDate.setDate(1);

    const ganttPrevMonth = document.getElementById("gantt-prev-month");
    const ganttNextMonth = document.getElementById("gantt-next-month");
    const ganttMonthDisplay = document.getElementById("gantt-month-display");
    const ganttChartContent = document.getElementById("gantt-chart-content");

    let tasksData = [];
    let taskState = {
        page: 1,
        size: 10,
        filter: "",
        priorityFilter: "all",
        calendarFilter: "all",
        sort: "deadline_asc"
    };

    // Color Palette for Tasks
    const GANTT_PALETTE = [
        '#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
        '#8b5cf6', '#ec4899', '#3b82f6', '#14b8a6', '#f97316'
    ];

    const getTaskColor = (task) => {
        if (task.done) return '#94a3b8'; // Slate for completed tasks
        if (task.calendar_type === 'routine') return '#06b6d4'; // Cyan for daily routine
        if (task.priority >= 5) return '#ef4444'; // Red for urgent
        if (task.priority === 4) return '#f59e0b'; // Amber for high

        if (task.labels) {
            const firstLabel = task.labels.split(',')[0].trim().toLowerCase();
            let hash = 0;
            for (let i = 0; i < firstLabel.length; i++) {
                hash = firstLabel.charCodeAt(i) + ((hash << 5) - hash);
            }
            return GANTT_PALETTE[Math.abs(hash) % GANTT_PALETTE.length];
        }

        return '#4f46e5';
    };

    // Tab Switching
    const taskTabBtns = document.querySelectorAll('.task-tab-btn');
    taskTabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            taskTabBtns.forEach(b => b.classList.remove('active'));
            const currentBtn = e.currentTarget;
            currentBtn.classList.add('active');

            const targetTab = currentBtn.getAttribute('data-tab');
            document.querySelectorAll('.task-tab-content').forEach(tab => tab.style.display = 'none');
            const targetId = `task-tab-${targetTab}`;
            const targetEl = document.getElementById(targetId);
            if (targetEl) targetEl.style.display = 'block';

            if (targetTab === 'gantt') {
                renderGanttChart(tasksData);
            }
        });
    });

    // Calendar Scope Filter (All / Routine / Task)
    const calScopeBtns = document.querySelectorAll('.cal-scope-btn');
    calScopeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            calScopeBtns.forEach(b => {
                b.classList.remove('primary');
                b.classList.add('ghost');
            });
            const currentBtn = e.currentTarget;
            currentBtn.classList.add('primary');
            currentBtn.classList.remove('ghost');

            taskState.calendarFilter = currentBtn.getAttribute('data-scope') || 'all';
            taskState.page = 1;
            renderTasks();
            const activeTab = document.querySelector('.task-tab-btn.active');
            if (activeTab && activeTab.getAttribute('data-tab') === 'gantt') {
                renderGanttChart(tasksData);
            }
        });
    });

    // Month Navigation for Calendar Grid
    const ganttTodayBtn = document.getElementById("gantt-today-btn");
    if (ganttTodayBtn) {
        ganttTodayBtn.addEventListener("click", () => {
            currentGanttDate = new Date();
            currentGanttDate.setDate(1);
            renderGanttChart(tasksData);
        });
    }
    if (ganttPrevMonth) {
        ganttPrevMonth.addEventListener("click", () => {
            currentGanttDate.setMonth(currentGanttDate.getMonth() - 1);
            renderGanttChart(tasksData);
        });
    }
    if (ganttNextMonth) {
        ganttNextMonth.addEventListener("click", () => {
            currentGanttDate.setMonth(currentGanttDate.getMonth() + 1);
            renderGanttChart(tasksData);
        });
    }

    // Min-Heap Implementation for Interval Partitioning
    class MinHeap {
        constructor() { this.heap = []; }
        push(val) {
            this.heap.push(val);
            this.bubbleUp();
        }
        pop() {
            if (this.size() === 1) return this.heap.pop();
            const top = this.heap[0];
            this.heap[0] = this.heap.pop();
            this.bubbleDown();
            return top;
        }
        size() { return this.heap.length; }
        peek() { return this.heap[0]; }
        bubbleUp() {
            let idx = this.heap.length - 1;
            while (idx > 0) {
                let pIdx = Math.floor((idx - 1) / 2);
                if (this.heap[idx].endTime <= this.heap[pIdx].endTime) {
                    [this.heap[idx], this.heap[pIdx]] = [this.heap[pIdx], this.heap[idx]];
                    idx = pIdx;
                } else break;
            }
        }
        bubbleDown() {
            let idx = 0;
            const length = this.heap.length;
            while (true) {
                let left = 2 * idx + 1;
                let right = 2 * idx + 2;
                let smallest = idx;
                if (left < length && this.heap[left].endTime < this.heap[smallest].endTime) smallest = left;
                if (right < length && this.heap[right].endTime < this.heap[smallest].endTime) smallest = right;
                if (smallest !== idx) {
                    [this.heap[idx], this.heap[smallest]] = [this.heap[smallest], this.heap[idx]];
                    idx = smallest;
                } else break;
            }
        }
    }

    const renderGanttChart = (tasks) => {
        if (!ganttChartContent || !ganttMonthDisplay) return;

        const year = currentGanttDate.getFullYear();
        const month = currentGanttDate.getMonth();
        const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

        const numDays = new Date(year, month + 1, 0).getDate();
        const monthStartTs = Math.floor(new Date(year, month, 1, 0, 0, 0).getTime() / 1000);
        const monthEndTs = Math.floor(new Date(year, month, numDays, 23, 59, 59).getTime() / 1000);

        let scopedTasks = [...tasks];
        if (taskState.calendarFilter && taskState.calendarFilter !== "all") {
            scopedTasks = scopedTasks.filter(t => (t.calendar_type || "task") === taskState.calendarFilter);
        }

        const monthlyTasks = scopedTasks.filter(t => {
            let startTs = t.start_date || (t.end_date - 86400 * 3);
            if (startTs > t.end_date) startTs = t.end_date - 86400;
            return startTs <= monthEndTs && t.end_date >= monthStartTs;
        });

        ganttMonthDisplay.innerText = `${monthNames[month]} ${year} (${monthlyTasks.length} task${monthlyTasks.length === 1 ? '' : 's'})`;

        renderWeekGrid(monthlyTasks, year, month, numDays);
    };

    const renderWeekGrid = (monthlyTasks, year, month, numDays) => {
        // Find first Monday on or before day 1
        const firstOfMonth = new Date(year, month, 1);
        let firstDayOfWeek = firstOfMonth.getDay(); // 0 is Sun, 1 is Mon...
        let diffToMonday = (firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1);
        let startMonday = new Date(year, month, 1 - diffToMonday, 0, 0, 0);

        // Find last Sunday on or after last day of month
        const lastOfMonth = new Date(year, month, numDays);
        let lastDayOfWeek = lastOfMonth.getDay();
        let diffToSunday = (lastDayOfWeek === 0 ? 0 : 7 - lastDayOfWeek);
        let endSunday = new Date(year, month, numDays + diffToSunday, 23, 59, 59);

        const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const today = new Date();
        const pad = n => String(n).padStart(2, '0');

        let weeksHtml = '<div style="display: flex; flex-direction: column; gap: 16px;">';
        let currentIter = new Date(startMonday.getTime());
        let weekIndex = 1;

        while (currentIter < endSunday) {
            const wStart = new Date(currentIter.getTime());
            wStart.setHours(0, 0, 0, 0);
            const wEnd = new Date(currentIter.getTime() + 6 * 86400 * 1000);
            wEnd.setHours(23, 59, 59, 999);

            const wStartTs = Math.floor(wStart.getTime() / 1000);
            const wEndTs = Math.floor(wEnd.getTime() / 1000);
            const weekDuration = 7 * 86400;

            const wTitleStart = `${pad(wStart.getDate())}/${pad(wStart.getMonth() + 1)}`;
            const wTitleEnd = `${pad(wEnd.getDate())}/${pad(wEnd.getMonth() + 1)}`;

            let weekDaysHeaderHtml = '';
            let weekGridColsHtml = '';
            const dayColPct = 100 / 7;

            for (let i = 0; i < 7; i++) {
                const dayObj = new Date(wStart.getTime() + i * 86400 * 1000);
                const dMonth = dayObj.getMonth();
                const dDate = dayObj.getDate();
                const isOutsideMonth = (dMonth !== month);
                const isWeekend = (i >= 5);
                const isToday = (today.getFullYear() === dayObj.getFullYear() &&
                                 today.getMonth() === dMonth &&
                                 today.getDate() === dDate);

                const textCol = isOutsideMonth ? 'var(--text-subtle)' : (isToday ? 'var(--primary)' : 'var(--text)');
                const headerBg = isToday ? 'var(--primary-light)' : (isWeekend ? 'var(--calendar-weekend-bg)' : '');

                weekDaysHeaderHtml += `
                    <div class="gantt-week-day-title ${isWeekend ? 'weekend' : ''} ${isToday ? 'today' : ''}" 
                         style="${headerBg ? 'background:' + headerBg + ';' : ''} ${i === 6 ? 'border-right: none;' : ''}">
                        <span style="font-weight: 700; color: ${textCol}; font-size: 11px;">${dayNames[i]}</span>
                        <span style="color: ${textCol}; opacity: 0.85; margin-left: 4px; font-weight: 600;">${pad(dDate)}/${pad(dMonth + 1)}</span>
                    </div>
                `;

                let colStyle = `left: ${i * dayColPct}%; width: ${dayColPct}%;`;
                if (i === 6) {
                    colStyle += ' border-right: none;';
                }
                if (isOutsideMonth) {
                    colStyle += ' background: rgba(0, 0, 0, 0.22); opacity: 0.7;';
                } else if (isToday) {
                    colStyle += ' background: var(--calendar-today-bg); border-right: 1px solid var(--calendar-today-border); border-left: 1px solid var(--calendar-today-border);';
                } else if (isWeekend) {
                    colStyle += ' background: var(--calendar-weekend-bg);';
                } else if (i % 2 === 1) {
                    colStyle += ' background: var(--calendar-col-alt);';
                }

                weekGridColsHtml += `
                    <div class="gantt-grid-column ${isWeekend ? 'weekend' : ''} ${isToday ? 'today' : ''}"
                         style="${colStyle}"></div>
                `;
            }

            const weekTasks = monthlyTasks.filter(t => {
                let startTs = t.start_date || (t.end_date - 86400 * 3);
                if (startTs > t.end_date) startTs = t.end_date - 86400;
                return startTs <= wEndTs && t.end_date >= wStartTs;
            });

            let weekBarsHtml = '';
            let bodyHeight = 70;

            if (weekTasks.length === 0) {
                weekBarsHtml = `
                    <div style="position: relative; z-index: 5; text-align: center; color: var(--text-subtle); font-size: 12px; padding: 24px 0; font-style: italic;">
                        No tasks scheduled for this week
                    </div>
                `;
            } else {
                const tasksWithBounds = weekTasks.map(t => {
                    let taskStart = t.start_date || (t.end_date - 86400 * 3);
                    if (taskStart > t.end_date) taskStart = t.end_date - 86400;
                    const clampedStart = Math.max(taskStart, wStartTs);
                    const clampedEnd = Math.min(t.end_date, wEndTs);

                    // 2 hours visual buffer for interval partitioning to prevent label overlaps
                    const minVisualSec = 7200;
                    const visualEnd = Math.max(clampedEnd, clampedStart + minVisualSec);

                    return {
                        ...t,
                        clampedStart,
                        clampedEnd,
                        visualEnd,
                        origStart: taskStart,
                        origEnd: t.end_date
                    };
                });

                // Sort tasks by start timestamp
                tasksWithBounds.sort((a, b) => a.clampedStart - b.clampedStart);

                // MinHeap Interval Partitioning using visualEnd
                const heap = new MinHeap();
                let maxRow = 0;
                tasksWithBounds.forEach(t => {
                    let assignedRow = 0;
                    if (heap.size() > 0 && heap.peek().endTime <= t.clampedStart) {
                        const earliest = heap.pop();
                        assignedRow = earliest.row;
                    } else {
                        assignedRow = maxRow++;
                    }
                    heap.push({ endTime: t.visualEnd, row: assignedRow });
                    t.rowIndex = assignedRow;
                });

                const totalRows = Math.max(maxRow, 1);
                const rowHeight = 32;
                bodyHeight = Math.max(totalRows * rowHeight + 18, 70);

                tasksWithBounds.forEach(t => {
                    const startOffset = t.clampedStart - wStartTs;
                    const duration = t.clampedEnd - t.clampedStart;

                    // Exact proportional position and width according to real duration
                    let leftPct = (startOffset / weekDuration) * 100;
                    let widthPct = (duration / weekDuration) * 100;

                    if (leftPct + widthPct > 100) {
                        widthPct = Math.max(0.5, 100 - leftPct);
                    }
                    if (leftPct < 0) leftPct = 0;

                    const topPx = 9 + (t.rowIndex * rowHeight);
                    const color = getTaskColor(t);

                    const dStart = new Date(t.origStart * 1000);
                    const dEnd = new Date(t.origEnd * 1000);

                    const startFmt = `${pad(dStart.getDate())}/${pad(dStart.getMonth() + 1)} ${pad(dStart.getHours())}:${pad(dStart.getMinutes())}`;
                    const endFmt = `${pad(dEnd.getDate())}/${pad(dEnd.getMonth() + 1)} ${pad(dEnd.getHours())}:${pad(dEnd.getMinutes())}`;

                    const isSingleDay = (dStart.toDateString() === dEnd.toDateString());
                    let timeBadge = '';
                    if (isSingleDay) {
                        timeBadge = `${pad(dStart.getHours())}:${pad(dStart.getMinutes())} - ${pad(dEnd.getHours())}:${pad(dEnd.getMinutes())}`;
                    } else {
                        timeBadge = `Due ${pad(dEnd.getDate())}/${pad(dEnd.getMonth() + 1)}`;
                    }

                    const continuesLeft = t.origStart < wStartTs;
                    const continuesRight = t.origEnd > wEndTs;

                    weekBarsHtml += `
                        <div class="gantt-bar ${t.calendar_type === 'routine' ? 'routine-bar' : ''}" onclick="editTask(${t.id})"
                             style="left: ${leftPct}%; width: ${widthPct}%; top: ${topPx}px; background: ${color};"
                             title="${t.name} (P${t.priority})${t.done ? ' [Completed]' : ''}&#10;Start: ${startFmt}&#10;Due: ${endFmt}">
                            ${continuesLeft ? '<span style="font-size: 9px; opacity: 0.85;">◀</span>' : ''}
                            <span class="gantt-bar-title" style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                ${t.done ? '✓ ' : ''}${t.name}
                            </span>
                            <span class="gantt-bar-time" style="font-size: 10px; margin-left: 4px; white-space: nowrap; opacity: 0.9;">${timeBadge}</span>
                            ${continuesRight ? '<span style="font-size: 9px; opacity: 0.85;">▶</span>' : ''}
                        </div>
                    `;
                });
            }

            const nowTs = Math.floor(today.getTime() / 1000);
            const isCurrentWeek = (nowTs >= wStartTs && nowTs <= wEndTs);
            let nowLineHtml = '';
            if (isCurrentWeek) {
                const nowOffset = nowTs - wStartTs;
                const nowLeftPct = (nowOffset / weekDuration) * 100;
                const nowFmt = `${pad(today.getHours())}:${pad(today.getMinutes())}`;
                nowLineHtml = `
                    <div class="gantt-now-line" style="left: ${nowLeftPct}%;" title="Current Time: ${nowFmt}">
                        <div class="gantt-now-dot"></div>
                        <div class="gantt-now-badge">NOW ${nowFmt}</div>
                    </div>
                `;
            }

            weeksHtml += `
                <div class="gantt-week">
                    <div class="gantt-week-header">
                        <span>Week ${weekIndex} (${wTitleStart} - ${wTitleEnd})</span>
                        <span style="font-size: 11px; opacity: 0.8; font-weight: 500;">${weekTasks.length} task${weekTasks.length === 1 ? '' : 's'}</span>
                    </div>
                    <div class="gantt-week-days">
                        ${weekDaysHeaderHtml}
                    </div>
                    <div class="gantt-week-body" style="min-height: ${bodyHeight}px;">
                        ${weekGridColsHtml}
                        ${nowLineHtml}
                        ${weekBarsHtml}
                    </div>
                </div>
            `;

            currentIter.setDate(currentIter.getDate() + 7);
            weekIndex++;
        }

        weeksHtml += '</div>';
        ganttChartContent.innerHTML = weeksHtml;
    };

    // Load Tasks from API
    window.loadTasks = async () => {
        try {
            const res = await fetch("/api/events");
            const data = await res.json();
            if (data.data) {
                tasksData = data.data;
                renderTasks();
                const activeTab = document.querySelector('.task-tab-btn.active');
                if (activeTab && activeTab.getAttribute('data-tab') === 'gantt') {
                    renderGanttChart(tasksData);
                }
            }
        } catch (e) {
            console.error("Error loading tasks:", e);
            if (window.showToast) window.showToast("Failed to load tasks", "error");
        }
    };

    const renderTasks = () => {
        if (!taskList) return;

        let filtered = [...tasksData];

        // Calendar scope filter (all / routine / task)
        if (taskState.calendarFilter && taskState.calendarFilter !== "all") {
            filtered = filtered.filter(t => (t.calendar_type || "task") === taskState.calendarFilter);
        }

        // Search & Label filter
        if (taskState.filter) {
            const q = taskState.filter.toLowerCase();
            filtered = filtered.filter(t =>
                t.name.toLowerCase().includes(q) ||
                (t.description && t.description.toLowerCase().includes(q)) ||
                (t.labels && t.labels.toLowerCase().includes(q))
            );
        }

        // Priority filter
        if (taskState.priorityFilter && taskState.priorityFilter !== "all") {
            const p = parseInt(taskState.priorityFilter);
            filtered = filtered.filter(t => t.priority === p);
        }

        // Sort
        if (taskState.sort === "deadline_asc") {
            filtered.sort((a, b) => a.end_date - b.end_date);
        } else if (taskState.sort === "deadline_desc") {
            filtered.sort((a, b) => b.end_date - a.end_date);
        } else if (taskState.sort === "priority_desc") {
            filtered.sort((a, b) => b.priority - a.priority);
        } else if (taskState.sort === "priority_asc") {
            filtered.sort((a, b) => a.priority - b.priority);
        }

        // Pagination
        const totalItems = filtered.length;
        const totalPages = Math.max(1, Math.ceil(totalItems / taskState.size));
        if (taskState.page > totalPages) taskState.page = totalPages;

        const start = (taskState.page - 1) * taskState.size;
        const pageItems = filtered.slice(start, start + taskState.size);

        if (pageInfo) pageInfo.innerText = `Page ${taskState.page} of ${totalPages} (${totalItems} items)`;
        if (btnPrevPage) btnPrevPage.disabled = taskState.page <= 1;
        if (btnNextPage) btnNextPage.disabled = taskState.page >= totalPages;

        taskList.innerHTML = "";
        if (pageItems.length === 0) {
            const scopeLabel = taskState.calendarFilter === 'routine' ? 'sinh hoạt (routine)' : (taskState.calendarFilter === 'task' ? 'nhiệm vụ (task)' : '');
            taskList.innerHTML = `
                <div style="text-align: center; padding: 48px 20px; background: var(--surface); border-radius: var(--radius); border: 1px dashed var(--border);">
                    <div style="color: var(--text-muted); margin-bottom: 12px;">
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
                        </svg>
                    </div>
                    <h4 style="font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 4px;">No items found</h4>
                    <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 14px;">Chưa có mục ${scopeLabel} nào trong khoảng này.</p>
                    <button class="btn primary btn-sm" onclick="document.getElementById('btn-add-task').click()">+ Add Item</button>
                </div>
            `;
            return;
        }

        pageItems.forEach(t => {
            const rowClass = t.done ? "task-done" : "";
            const doneChecked = t.done ? "checked" : "";

            let tagsHtml = "";
            if (t.labels) {
                tagsHtml = t.labels.split(",").map(l => l.trim()).filter(Boolean).map(l =>
                    `<span class="tag">${l}</span>`
                ).join(" ");
            }

            const endDate = new Date(t.end_date * 1000);
            const dateFormatted = `${endDate.getDate()}/${endDate.getMonth() + 1}/${endDate.getFullYear()} ${String(endDate.getHours()).padStart(2, '0')}:${String(endDate.getMinutes()).padStart(2, '0')}`;

            const badgeHtml = t.calendar_type === 'routine'
                ? `<span class="badge badge-routine" title="Lịch sinh hoạt hằng ngày">🕒 Sinh hoạt</span>`
                : `<span class="badge badge-p${t.priority}">P${t.priority}</span>`;

            taskList.innerHTML += `
                <article class="task-row ${rowClass}" onclick="editTask(${t.id})" style="cursor: pointer;">
                    <div style="display: flex; flex-direction: column; overflow: hidden; min-width: 0;">
                        <div class="task-title" style="font-size: 13px; font-weight: 500;">
                            ${t.calendar_type === 'routine' ? '<span style="color: var(--routine-color); font-size: 11px; margin-right: 4px;">🕒</span>' : ''}${t.name}
                        </div>
                        <div class="task-desc" style="font-size: 12px; color: var(--text-muted);">${t.description || "No description"}</div>
                    </div>
                    <div>
                        ${badgeHtml}
                    </div>
                    <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                        ${tagsHtml || '<span style="font-size: 11px; color: var(--text-subtle);">None</span>'}
                    </div>
                    <div class="task-deadline" style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); display: flex; align-items: center; gap: 4px;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        <span>${dateFormatted}</span>
                    </div>
                    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 10px;">
                        <input type="checkbox" onclick="event.stopPropagation()" onchange="toggleTaskDone(${t.id}, this.checked)" ${doneChecked} style="width: 15px; height: 15px; cursor: pointer;">
                        <button class="btn ghost btn-sm hover-only" onclick="event.stopPropagation(); deleteTaskDirect(${t.id})" title="Delete" style="padding: 2px 6px; color: var(--danger);">✕</button>
                    </div>
                </article>
            `;
        });
    };

    // Filters event listeners
    if (taskSort) taskSort.addEventListener("change", e => { taskState.sort = e.target.value; renderTasks(); });
    if (taskPageSize) taskPageSize.addEventListener("change", e => { taskState.size = parseInt(e.target.value); taskState.page = 1; renderTasks(); });
    if (taskFilterLabel) taskFilterLabel.addEventListener("input", e => { taskState.filter = e.target.value; taskState.page = 1; renderTasks(); });
    if (taskFilterPriority) taskFilterPriority.addEventListener("change", e => { taskState.priorityFilter = e.target.value; taskState.page = 1; renderTasks(); });

    if (btnPrevPage) btnPrevPage.addEventListener("click", () => { if (taskState.page > 1) { taskState.page--; renderTasks(); } });
    if (btnNextPage) btnNextPage.addEventListener("click", () => { taskState.page++; renderTasks(); });

    // Open & Close Drawer
    const openTaskDrawer = () => {
        if (overlay) overlay.classList.remove("hidden");
        const drawer = document.getElementById("task-drawer");
        if (drawer) drawer.classList.remove("hidden");
    };

    const closeTaskDrawer = () => {
        if (overlay) overlay.classList.add("hidden");
        const drawer = document.getElementById("task-drawer");
        if (drawer) drawer.classList.add("hidden");
    };

    if (btnAddTask) {
        btnAddTask.addEventListener("click", () => {
            document.getElementById("task-drawer-title").innerText = "Add Task";
            if (taskIdInput) taskIdInput.value = "";
            if (taskForm) {
                taskForm.reset();
                if (taskState.calendarFilter === "routine") {
                    const rBtn = document.getElementById("cal-type-routine");
                    if (rBtn) rBtn.checked = true;
                } else {
                    const tBtn = document.getElementById("cal-type-task");
                    if (tBtn) tBtn.checked = true;
                }
                const now = new Date();
                const pad = n => n.toString().padStart(2, '0');
                taskForm.elements["start_date"].value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
                taskForm.elements["start_hour"].value = now.getHours();
                taskForm.elements["start_minute"].value = now.getMinutes();

                const tomorrow = new Date(now.getTime() + 86400 * 1000);
                taskForm.elements["end_date"].value = `${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}`;
                taskForm.elements["end_hour"].value = 23;
                taskForm.elements["end_minute"].value = 59;
                taskForm.elements["priority"].value = "3";
            }
            if (btnDeleteTask) btnDeleteTask.classList.add("hidden");
            openTaskDrawer();
        });
    }

    if (btnCloseTaskDrawer) btnCloseTaskDrawer.addEventListener("click", closeTaskDrawer);
    if (btnCancelTaskDrawer) btnCancelTaskDrawer.addEventListener("click", closeTaskDrawer);
    if (overlay) overlay.addEventListener("click", closeTaskDrawer);

    // Save Task Form Handler
    if (taskForm) {
        taskForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            try {
                const formData = new FormData(taskForm);
                const id = formData.get("id");
                const name = formData.get("name").trim();
                const description = formData.get("description").trim();
                const priority = parseInt(formData.get("priority")) || 1;
                const labels = formData.get("labels").trim();
                const done = formData.get("done") === "on";
                const calendar_type = formData.get("calendar_type") || "task";

                const startDateStr = formData.get("start_date");
                const startHour = parseInt(formData.get("start_hour")) || 0;
                const startMinute = parseInt(formData.get("start_minute")) || 0;
                const startDateObj = new Date(startDateStr);
                startDateObj.setHours(startHour, startMinute, 0, 0);
                const start_date = Math.floor(startDateObj.getTime() / 1000);

                const endDateStr = formData.get("end_date");
                const endHour = parseInt(formData.get("end_hour")) || 23;
                const endMinute = parseInt(formData.get("end_minute")) || 59;
                const endDateObj = new Date(endDateStr);
                endDateObj.setHours(endHour, endMinute, 0, 0);
                const end_date = Math.floor(endDateObj.getTime() / 1000);

                const payload = {
                    id: id ? parseInt(id) : null,
                    name,
                    description,
                    start_date,
                    end_date,
                    priority,
                    labels,
                    done,
                    calendar_type
                };

                const res = await fetch("/api/events", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const json = await res.json();
                if (res.ok) {
                    if (window.showToast) window.showToast(id ? "Task updated!" : "Task created!", "success");
                    closeTaskDrawer();
                    window.loadTasks();
                } else {
                    if (window.showToast) window.showToast(json.message || "Failed to save task", "error");
                }
            } catch (err) {
                console.error("Save task error:", err);
                if (window.showToast) window.showToast("Network error saving task", "error");
            }
        });
    }

    // Toggle Task Done
    window.toggleTaskDone = async (id, isDone) => {
        try {
            const t = tasksData.find(x => x.id === id);
            if (!t) return;
            const payload = { ...t, done: isDone };
            await fetch("/api/events", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            window.loadTasks();
        } catch (err) {
            console.error("Error toggling task done:", err);
        }
    };

    // Delete Task
    window.deleteTaskDirect = async (id) => {
        try {
            const res = await fetch("/api/events", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id })
            });
            if (res.ok) {
                if (window.showToast) window.showToast("Task deleted", "info");
                window.loadTasks();
            }
        } catch (err) {
            console.error("Error deleting task:", err);
        }
    };

    // Edit Task (open drawer populated)
    window.editTask = (id) => {
        try {
            const t = tasksData.find(x => x.id === id);
            if (!t) return;

            document.getElementById("task-drawer-title").innerText = "Edit Task";
            if (taskIdInput) taskIdInput.value = t.id;
            if (taskForm) {
                taskForm.elements["name"].value = t.name;
                taskForm.elements["description"].value = t.description || "";
                taskForm.elements["priority"].value = t.priority || 1;
                taskForm.elements["labels"].value = t.labels || "";
                taskForm.elements["done"].checked = !!t.done;

                if (t.calendar_type === "routine") {
                    const rBtn = document.getElementById("cal-type-routine");
                    if (rBtn) rBtn.checked = true;
                } else {
                    const tBtn = document.getElementById("cal-type-task");
                    if (tBtn) tBtn.checked = true;
                }

                const pad = n => n.toString().padStart(2, '0');
                const d = new Date(t.end_date * 1000);
                taskForm.elements["end_date"].value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
                taskForm.elements["end_hour"].value = d.getHours();
                taskForm.elements["end_minute"].value = d.getMinutes();

                let startTs = t.start_date || (t.end_date - 86400 * 3);
                if (startTs > t.end_date) startTs = t.end_date - 86400;
                const sd = new Date(startTs * 1000);
                taskForm.elements["start_date"].value = `${sd.getFullYear()}-${pad(sd.getMonth() + 1)}-${pad(sd.getDate())}`;
                taskForm.elements["start_hour"].value = sd.getHours();
                taskForm.elements["start_minute"].value = sd.getMinutes();
            }

            if (btnDeleteTask) {
                btnDeleteTask.classList.remove("hidden");
                btnDeleteTask.onclick = async () => {
                    await deleteTaskDirect(t.id);
                    closeTaskDrawer();
                };
            }
            openTaskDrawer();
        } catch (err) {
            console.error("Error editing task:", err);
        }
    };

    // ICS Import & Export Handlers
    const btnImportIcs = document.getElementById("btn-import-ics");
    const btnExportIcs = document.getElementById("btn-export-ics");
    const icsFileInput = document.getElementById("ics-file-input");

    const uploadIcsFile = async (file) => {
        try {
            if (window.showToast) window.showToast("Importing .ics schedule...", "info");
            const formData = new FormData();
            formData.append("file", file);

            const targetCal = (taskState.calendarFilter && taskState.calendarFilter !== "all") ? taskState.calendarFilter : "task";
            const res = await fetch(`/api/events/import-ics?calendar_type=${targetCal}`, {
                method: "POST",
                body: formData
            });
            const json = await res.json();

            if (res.ok) {
                if (window.showToast) window.showToast(json.message || `Imported ${json.count || 0} tasks!`, "success");
                window.loadTasks();
            } else {
                if (window.showToast) window.showToast(json.message || "Failed to import .ics", "error");
            }
        } catch (err) {
            console.error("Error importing .ics:", err);
            if (window.showToast) window.showToast("Network error importing .ics file", "error");
        }
    };

    if (btnImportIcs && icsFileInput) {
        btnImportIcs.addEventListener("click", () => {
            icsFileInput.click();
        });

        icsFileInput.addEventListener("change", async () => {
            const file = icsFileInput.files[0];
            if (!file) return;
            await uploadIcsFile(file);
            icsFileInput.value = "";
        });
    }

    if (btnExportIcs) {
        btnExportIcs.addEventListener("click", () => {
            const calParam = (taskState.calendarFilter && taskState.calendarFilter !== "all") ? `?calendar_type=${taskState.calendarFilter}` : "";
            window.location.href = `/api/events/export-ics${calParam}`;
        });
    }

    // Drag & Drop .ics onto Tasks Page
    const tasksPageEl = document.getElementById("tasks");
    if (tasksPageEl) {
        ['dragenter', 'dragover'].forEach(eventName => {
            tasksPageEl.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                tasksPageEl.style.outline = "2px dashed var(--primary)";
                tasksPageEl.style.outlineOffset = "-4px";
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            tasksPageEl.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                tasksPageEl.style.outline = "none";
            });
        });

        tasksPageEl.addEventListener("drop", async (e) => {
            const dt = e.dataTransfer;
            const files = dt ? dt.files : null;
            if (files && files.length > 0) {
                const file = files[0];
                if (file.name.toLowerCase().endsWith(".ics") || file.type.includes("calendar")) {
                    await uploadIcsFile(file);
                } else {
                    if (window.showToast) window.showToast("Please drop a valid .ics calendar file", "warning");
                }
            }
        });
    }

    // Auto-update current time red indicator every 60 seconds
    setInterval(() => {
        if (tasksData && tasksData.length >= 0) {
            renderGanttChart(tasksData);
        }
    }, 60000);

    window.loadTasks();
});
