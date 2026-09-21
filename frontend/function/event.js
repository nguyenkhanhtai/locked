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
        sort: "deadline_asc"
    };

    // Color Palette for Tasks
    const GANTT_PALETTE = [
        '#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
        '#8b5cf6', '#ec4899', '#3b82f6', '#14b8a6', '#f97316'
    ];

    const getTaskColor = (task) => {
        if (task.done) return '#94a3b8'; // Slate for completed tasks
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

    // Month Navigation for Gantt
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

        const monthStart = new Date(year, month, 1);
        const numDays = new Date(year, month + 1, 0).getDate();
        const numWeeks = Math.ceil(numDays / 7);
        const monthEnd = new Date(year, month, numWeeks * 7 + 1);
        const monthStartTs = Math.floor(monthStart.getTime() / 1000);
        const monthEndTs = Math.floor(monthEnd.getTime() / 1000);

        const monthlyTasks = tasks.filter(t => {
            let startTs = t.start_date || (t.end_date - 86400 * 3);
            if (startTs > t.end_date) startTs = t.end_date - 86400;
            return startTs < monthEndTs && t.end_date >= monthStartTs;
        });

        ganttMonthDisplay.innerText = `${monthNames[month]} ${year} (${monthlyTasks.length} tasks)`;

        let html = `<div style="display: flex; flex-direction: column; gap: 16px;">`;

        for (let w = 0; w < numWeeks; w++) {
            const weekStartDay = w * 7 + 1;
            const weekEndDay = weekStartDay + 6;

            const wStartObj = new Date(year, month, weekStartDay);
            const wEndObj = new Date(year, month, weekEndDay + 1);
            const wStartTs = Math.floor(wStartObj.getTime() / 1000);
            const wEndTs = Math.floor(wEndObj.getTime() / 1000);
            const weekDuration = 7 * 86400;

            const wStartDisplay = new Date(year, month, weekStartDay);
            const wEndDisplay = new Date(year, month, weekEndDay);
            const titleStart = `${wStartDisplay.getDate()}/${wStartDisplay.getMonth() + 1}`;
            const titleEnd = `${wEndDisplay.getDate()}/${wEndDisplay.getMonth() + 1}`;

            html += `<div class="gantt-week">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <span style="font-weight: 700; font-size: 13px; color: var(--text);">Week ${w + 1} (${titleStart} - ${titleEnd})</span>
                        </div>
                        <div style="position: relative; min-height: 70px; padding-top: 24px;">`;

            // Draw 7-day grid lines
            for (let i = 0; i < 7; i++) {
                const dayObj = new Date(year, month, weekStartDay + i);
                const dNum = dayObj.getDate();
                const dMonth = dayObj.getMonth() + 1;
                const dDayOfWeek = dayObj.getDay();
                const isExtraDay = dayObj.getMonth() !== month;
                const isWeekend = dDayOfWeek === 0 || dDayOfWeek === 6;

                const leftPct = (i / 7) * 100;
                let bgStyle = isExtraDay ? 'background: rgba(0,0,0,0.02);' : (isWeekend ? 'background: rgba(79, 70, 229, 0.03);' : '');
                const textColor = isExtraDay ? '#cbd5e1' : (isWeekend ? 'var(--primary)' : 'var(--text-muted)');

                html += `
                    <div style="position: absolute; top: 0; bottom: 0; left: ${leftPct}%; border-left: 1px solid var(--border); width: ${100 / 7}%; ${bgStyle} pointer-events: none;">
                        <span style="position: absolute; top: 2px; left: 6px; font-size: 11px; color: ${textColor}; font-weight: 700;">${dNum}/${dMonth}</span>
                    </div>
                `;
            }

            // Tasks in this week
            const weekTasks = monthlyTasks.filter(t => {
                let startTs = t.start_date || (t.end_date - 86400 * 3);
                if (startTs > t.end_date) startTs = t.end_date - 86400;
                return startTs < wEndTs && t.end_date >= wStartTs;
            });

            if (weekTasks.length === 0) {
                html += `<div style="text-align: center; color: var(--text-subtle); font-size: 12px; padding: 14px 0; font-style: italic;">No tasks scheduled for this week</div>`;
            } else {
                // Greedy Interval Partitioning via Min-Heap
                const tasksWithBounds = weekTasks.map(t => {
                    let taskStart = t.start_date || (t.end_date - 86400 * 3);
                    if (taskStart > t.end_date) taskStart = t.end_date - 86400;
                    return {
                        ...t,
                        clampedStart: Math.max(taskStart, wStartTs),
                        clampedEnd: Math.min(t.end_date, wEndTs)
                    };
                });
                tasksWithBounds.sort((a, b) => a.clampedStart - b.clampedStart);

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
                    heap.push({ endTime: t.clampedEnd, row: assignedRow });
                    t.rowIndex = assignedRow;
                });

                const totalRows = Math.max(maxRow, 1);
                const rowHeight = 36;
                const containerHeight = totalRows * rowHeight + 28;

                html = html.replace(`min-height: 70px;`, `min-height: ${containerHeight}px;`);

                tasksWithBounds.forEach(t => {
                    const startOffset = t.clampedStart - wStartTs;
                    const duration = Math.max(t.clampedEnd - t.clampedStart, 3600 * 4); // Minimum visible width

                    let leftPct = (startOffset / weekDuration) * 100;
                    let widthPct = (duration / weekDuration) * 100;

                    if (leftPct < 0) leftPct = 0;
                    if (leftPct + widthPct > 100) widthPct = 100 - leftPct;

                    const topPx = 26 + (t.rowIndex * rowHeight);
                    const color = getTaskColor(t);

                    html += `
                        <div class="gantt-bar" onclick="editTask(${t.id})"
                             style="left: ${leftPct}%; width: ${widthPct}%; top: ${topPx}px; background: ${color};"
                             title="${t.name} (Priority: ${t.priority})">
                            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                ${t.done ? '✓ ' : ''}${t.name}
                            </span>
                        </div>
                    `;
                });
            }

            html += `   </div>
                    </div>`;
        }

        html += `</div>`;
        ganttChartContent.innerHTML = html;
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

        if (pageInfo) pageInfo.innerText = `Page ${taskState.page} of ${totalPages} (${totalItems} tasks)`;
        if (btnPrevPage) btnPrevPage.disabled = taskState.page <= 1;
        if (btnNextPage) btnNextPage.disabled = taskState.page >= totalPages;

        taskList.innerHTML = "";
        if (pageItems.length === 0) {
            taskList.innerHTML = `
                <div style="text-align: center; padding: 48px 20px; background: var(--surface); border-radius: var(--radius); border: 1px dashed var(--border);">
                    <div style="font-size: 36px; margin-bottom: 12px;">📝</div>
                    <h4 style="font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 6px;">No tasks found</h4>
                    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">Create a new task or adjust your filters above.</p>
                    <button class="btn primary btn-sm" onclick="document.getElementById('btn-add-task').click()">+ Create Task</button>
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
                    `<span class="tag-label">${l}</span>`
                ).join(" ");
            }

            const endDate = new Date(t.end_date * 1000);
            const dateFormatted = `${endDate.getDate()}/${endDate.getMonth() + 1}/${endDate.getFullYear()} ${String(endDate.getHours()).padStart(2, '0')}:${String(endDate.getMinutes()).padStart(2, '0')}`;

            taskList.innerHTML += `
                <article class="task-row ${rowClass}" onclick="editTask(${t.id})" style="cursor: pointer;">
                    <div style="display: flex; flex-direction: column; overflow: hidden;">
                        <div class="task-title">${t.name}</div>
                        <div class="task-desc">${t.description || "No description"}</div>
                    </div>
                    <div>
                        <span class="badge priority-badge-${t.priority}">Priority ${t.priority}</span>
                    </div>
                    <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                        ${tagsHtml || '<span style="font-size: 11px; color: var(--text-subtle);">None</span>'}
                    </div>
                    <div class="task-deadline">
                        ⏳ ${dateFormatted}
                    </div>
                    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 10px;">
                        <input type="checkbox" onclick="event.stopPropagation()" onchange="toggleTaskDone(${t.id}, this.checked)" ${doneChecked} style="width: 18px; height: 18px; cursor: pointer;">
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
                    done
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

    window.loadTasks();
});
