document.addEventListener("DOMContentLoaded", () => {
    const btnAddTask = document.getElementById("btn-add-task");
    const btnCloseTaskDrawer = document.getElementById("btn-close-task-drawer");
    const taskForm = document.getElementById("task-form");
    const taskIdInput = document.getElementById("task-id");
    const btnDeleteTask = document.getElementById("btn-delete-task");
    const taskList = document.getElementById("task-list");
    const overlay = document.getElementById("overlay");

    const taskSort = document.getElementById("task-sort");
    const taskFilterLabel = document.getElementById("task-filter-label");
    const taskPageSize = document.getElementById("task-page-size");
    const btnPrevPage = document.getElementById("btn-prev-page");
    const btnNextPage = document.getElementById("btn-next-page");
    const pageInfo = document.getElementById("page-info");

    let currentGanttDate = new Date();
    currentGanttDate.setDate(1); // Tránh nhảy lỗi ngày khi chuyển tháng

    const ganttPrevMonth = document.getElementById("gantt-prev-month");
    const ganttNextMonth = document.getElementById("gantt-next-month");
    const ganttMonthDisplay = document.getElementById("gantt-month-display");
    const ganttChartContent = document.getElementById("gantt-chart-content");

    const GANTT_PALETTE = [
        '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b',
        '#fd7e14', '#6610f2', '#6f42c1', '#e83e8c', '#20c997',
        '#007bff', '#28a745', '#17a2b8', '#ffc107', '#dc3545'
    ];

    const getTaskColor = (task) => {
        if (task.done) return '#28a745'; // Green for finished tasks
        if (task.priority >= 5) return '#dc3545'; // Red for critical tasks

        // Use labels to determine color if available
        if (task.labels) {
            const firstLabel = task.labels.split(',')[0].trim().toLowerCase();
            let hash = 0;
            for (let i = 0; i < firstLabel.length; i++) {
                hash = firstLabel.charCodeAt(i) + ((hash << 5) - hash);
            }
            return GANTT_PALETTE[Math.abs(hash) % GANTT_PALETTE.length];
        }

        // Fallback to name-based hash
        let hash = 0;
        const str = task.name || "";
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        return GANTT_PALETTE[Math.abs(hash) % GANTT_PALETTE.length];
    };

    // Tabs logic cho Tasks
    const taskTabBtns = document.querySelectorAll('.task-tab-btn');
    taskTabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            taskTabBtns.forEach(b => {
                b.classList.remove('primary');
                b.classList.add('outline');
            });
            const currentBtn = e.currentTarget;
            currentBtn.classList.remove('outline');
            currentBtn.classList.add('primary');

            const targetTab = currentBtn.getAttribute('data-tab');
            document.querySelectorAll('.task-tab-content').forEach(tab => tab.style.display = 'none');
            const targetId = `task-tab-${targetTab}`;
            document.getElementById(targetId).style.display = 'block';
        });
    });

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

    const renderGanttChart = (tasks) => {
        if (!ganttChartContent || !ganttMonthDisplay) return;

        const year = currentGanttDate.getFullYear();
        const month = currentGanttDate.getMonth();

        ganttMonthDisplay.innerText = `${month + 1} / ${year}`;

        const monthStart = new Date(year, month, 1);
        const numDays = new Date(year, month + 1, 0).getDate();
        const numWeeks = Math.ceil(numDays / 7);
        const monthEnd = new Date(year, month, numWeeks * 7 + 1); // Kéo dài đến hết tuần cuối cùng
        const monthStartTs = Math.floor(monthStart.getTime() / 1000);
        const monthEndTs = Math.floor(monthEnd.getTime() / 1000);

        // Lọc các task có diễn ra trong tháng hiện tại (và tuần cuối cùng lấn sang tháng sau)
        const monthlyTasks = tasks.filter(t => {
            let startTs = t.start_date || t.created_at || (t.end_date - 86400 * 3);
            if (startTs > t.end_date) startTs = t.end_date - 86400;
            return startTs < monthEndTs && t.end_date >= monthStartTs;
        });

        ganttMonthDisplay.innerText = `Tháng ${month + 1} / ${year} (${monthlyTasks.length} tasks)`;

        let html = `<div style="display: flex; flex-direction: column; gap: 20px;">`;

        // Chia tháng thành các Week (hàng), mỗi Week 7 ngày.
        for (let w = 0; w < numWeeks; w++) {
            const weekStartDay = w * 7 + 1;
            const weekEndDay = weekStartDay + 6; // Luôn hiển thị 7 ngày

            const wStartObj = new Date(year, month, weekStartDay);
            const wEndObj = new Date(year, month, weekEndDay + 1); // Đầu ngày hôm sau
            const wStartTs = Math.floor(wStartObj.getTime() / 1000);
            const wEndTs = Math.floor(wEndObj.getTime() / 1000);
            // 1 Week luôn có width chuẩn là 7 ngày để scale các vạch thống nhất
            const weekDuration = 7 * 86400;

            const wStartDisplay = new Date(year, month, weekStartDay);
            const wEndDisplay = new Date(year, month, weekEndDay);
            const titleStart = `${wStartDisplay.getDate()}/${wStartDisplay.getMonth() + 1}`;
            const titleEnd = `${wEndDisplay.getDate()}/${wEndDisplay.getMonth() + 1}`;

            html += `<div class="gantt-week" style="border: 1px solid var(--border); border-radius: 8px; padding: 15px; background: #fafafa;">
                        <h4 style="margin: 0 0 15px 0; font-size: 14px; color: var(--text);">Week ${w + 1} (${titleStart} - ${titleEnd})</h4>
                        <div style="position: relative; min-height: 60px; padding-top: 20px;">`;

            // Vẽ vạch dọc chia 7 ngày
            for (let i = 0; i < 7; i++) {
                const dayObj = new Date(year, month, weekStartDay + i);
                const dNum = dayObj.getDate();
                const dMonth = dayObj.getMonth() + 1;
                const dDayOfWeek = dayObj.getDay();
                const isExtraDay = dayObj.getMonth() !== month; // Kiểm tra ngày có lấn sang tháng khác 
                const isWeekend = dDayOfWeek === 0 || dDayOfWeek === 6;

                const leftPct = (i / 7) * 100;
                let bgStyle = isExtraDay ? 'background: rgba(0,0,0,0.04);' : (isWeekend ? 'background: rgba(0,123,255,0.03);' : '');
                const textColor = isExtraDay ? '#bbb' : (isWeekend ? 'var(--primary)' : '#888');

                html += `
                    <div style="position: absolute; top: 0; bottom: 0; left: ${leftPct}%; border-left: 1px dashed #ccc; width: ${100 / 7}%; ${bgStyle} pointer-events: none;">
                        <span style="position: absolute; top: 0; left: 4px; font-size: 11px; color: ${textColor}; font-weight: bold;">${dNum} / ${dMonth}</span>
                    </div>
                `;
            }

            // Lọc task nằm trong khoảng Week này
            const weekTasks = monthlyTasks.filter(t => {
                let startTs = t.start_date || t.created_at || (t.end_date - 86400 * 3);
                if (startTs > t.end_date) startTs = t.end_date - 86400;
                return startTs < wEndTs && t.end_date >= wStartTs;
            });

            if (weekTasks.length === 0) {
                html += `<div style="text-align: center; color: #999; font-size: 12px; padding: 10px 0; font-style: italic;">No tasks to show here</div>`;
            } else {
                // TỐI ƯU HÓA: Sử dụng Min-Heap và Thuật toán Tham lam (Greedy)
                // Thuật toán: Sắp xếp task theo start time, dùng Min-Heap để quản lý thời gian kết thúc của các hàng.

                // 1. Chuẩn bị dữ liệu và sắp xếp theo start time
                const tasksWithBounds = weekTasks.map(t => {
                    let taskStart = t.start_date || t.created_at || (t.end_date - 86400 * 3);
                    if (taskStart > t.end_date) taskStart = t.end_date - 86400;
                    return {
                        ...t,
                        clampedStart: Math.max(taskStart, wStartTs),
                        clampedEnd: Math.min(t.end_date, wEndTs)
                    };
                });
                tasksWithBounds.sort((a, b) => a.clampedStart - b.clampedStart);

                // 2. Định nghĩa lớp MinHeap đơn giản để quản lý EndTimes của các Rows
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
                        while (true) {
                            let l = 2 * idx + 1, r = 2 * idx + 2, small = idx;
                            if (l < this.heap.length && this.heap[l].endTime < this.heap[small].endTime) small = l;
                            if (r < this.heap.length && this.heap[r].endTime < this.heap[small].endTime) small = r;
                            if (small !== idx) {
                                [this.heap[idx], this.heap[small]] = [this.heap[small], this.heap[idx]];
                                idx = small;
                            } else break;
                        }
                    }
                }

                // 3. Phân bổ Row bằng thuật toán tham lam
                const heap = new MinHeap();
                const finalTasks = [];
                let rowCounter = 0;

                tasksWithBounds.forEach(t => {
                    // Nếu heap không trống và task bắt đầu sau khi row kết thúc sớm nhất xong việc
                    if (heap.size() > 0 && t.clampedStart >= heap.peek().endTime) {
                        const bestRow = heap.pop();
                        t.rowIndex = bestRow.rowIndex;
                        heap.push({ endTime: t.clampedEnd, rowIndex: t.rowIndex });
                    } else {
                        // Cần một hàng mới
                        t.rowIndex = rowCounter++;
                        heap.push({ endTime: t.clampedEnd, rowIndex: t.rowIndex });
                    }
                    finalTasks.push(t);
                });

                // 4. Render giao diện
                html += `<div style="position: relative; height: ${rowCounter * 34}px;">`;

                // Vẽ các nền xám cho từng hàng
                for (let r = 0; r < rowCounter; r++) {
                    html += `<div style="position: absolute; top: ${r * 34}px; left: 0; right: 0; height: 26px; background: rgba(0,0,0,0.05); border-radius: 4px; z-index: 1; pointer-events: none;"></div>`;
                }

                // Vẽ thanh công việc
                finalTasks.forEach(t => {
                    let leftPct = ((t.clampedStart - wStartTs) / weekDuration) * 100;
                    let widthPct = ((t.clampedEnd - t.clampedStart) / weekDuration) * 100;

                    if (widthPct < 2) widthPct = 2; 
                    if (leftPct + widthPct > 100) widthPct = 100 - leftPct;

                    const color = getTaskColor(t);
                    const opacity = t.done ? '0.6' : '1';
                    const topPos = t.rowIndex * 34;

                    html += `
                        <div style="position: absolute; top: ${topPos}px; left: ${leftPct}%; width: ${widthPct}%; height: 26px; background: ${color}; opacity: ${opacity}; border-radius: 4px; display: flex; align-items: center; padding: 0 5px; color: #fff; font-size: 11px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; z-index: 5; transition: transform 0.2s;" title="${t.name}" onclick="editTask(${t.id})" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
                            ${t.name}
                        </div>
                    `;
                });

                html += `</div>`;
            }

            // Vẽ đường màu đỏ thể hiện thời điểm hiện tại
            const nowTs = Math.floor(Date.now() / 1000);
            if (nowTs >= wStartTs && nowTs < wEndTs) {
                const nowPct = ((nowTs - wStartTs) / weekDuration) * 100;
                html += `<div style="position: absolute; top: 0; bottom: 0; left: ${nowPct}%; border-left: 2px solid red; z-index: 10; pointer-events: none;" title="Thời điểm hiện tại"></div>`;
            }

            html += `</div></div>`; // end week relative div & gantt-week
        }

        html += `</div>`;
        ganttChartContent.innerHTML = html;
    };

    // Cập nhật đường đỏ hiển thị thời gian hiện tại cứ mỗi phút
    setInterval(() => {
        if (tasksData.length > 0) {
            renderGanttChart(tasksData);
        }
    }, 60000);

    let tasksData = [];
    let taskState = { page: 1, size: 10, sort: 'deadline_asc', filter: '' };

    const closeTaskDrawer = () => {
        const drawerEl = document.getElementById("task-drawer");
        if (!drawerEl || drawerEl.classList.contains("hidden")) return;
        window.closeDrawer("task-drawer");
        if (taskForm) taskForm.reset();
    };

    if (btnAddTask) {
        btnAddTask.addEventListener("click", () => {
            document.getElementById("task-drawer-title").innerText = "Add Task";
            if (taskIdInput) taskIdInput.value = "";
            if (btnDeleteTask) btnDeleteTask.classList.add("hidden");

            // Set default start time to now
            if (taskForm) {
                taskForm.reset();
                const now = new Date();
                const pad = n => n.toString().padStart(2, '0');
                taskForm.elements["start_date"].value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
                taskForm.elements["start_hour"].value = now.getHours();
                taskForm.elements["start_minute"].value = now.getMinutes();
            }

            window.openDrawer("task-drawer");
        });
    }

    if (btnCloseTaskDrawer) btnCloseTaskDrawer.addEventListener("click", closeTaskDrawer);
    if (overlay) overlay.addEventListener("click", closeTaskDrawer);

    if (taskForm) {
        taskForm.addEventListener("submit", async (e) => {
            try {
                e.preventDefault();
                const fd = new FormData(taskForm);

                const dateStr = fd.get("end_date");
                let hour = fd.get("end_hour") || "23";
                let minute = fd.get("end_minute") || "59";

                const endDateObj = new Date(`${dateStr}T${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}:00`);
                const endTs = Math.floor(endDateObj.getTime() / 1000);

                const startStr = fd.get("start_date");
                let startHour = fd.get("start_hour") || "0";
                let startMinute = fd.get("start_minute") || "0";
                let startTs = endTs - 86400;
                if (startStr) {
                    const startDateObj = new Date(`${startStr}T${startHour.toString().padStart(2, '0')}:${startMinute.toString().padStart(2, '0')}:00`);
                    startTs = Math.floor(startDateObj.getTime() / 1000);
                }

                const payload = {
                    name: fd.get("name"),
                    description: fd.get("description"),
                    start_date: startTs,
                    end_date: endTs,
                    priority: parseInt(fd.get("priority")),
                    labels: fd.get("labels"),
                    done: fd.get("done") === "on"
                };
                if (fd.get("id")) payload.id = fd.get("id");
                await fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
                closeTaskDrawer();
                window.loadTasks();
            } catch (err) {
                console.error("Error submitting task:", err);
                alert("Failed to save task.");
            }
        });
    }

    window.loadTasks = async () => {
        try {
            const res = await fetch(`/api/events?_t=${Date.now()}`, { cache: 'no-store' });
            const json = await res.json();
            tasksData = json.data || [];
            renderTasks();
            renderGanttChart(tasksData);
        } catch (err) {
            console.error("Failed to load tasks:", err);
        }
    };

    const formatDiff = (diff) => {
        const d = Math.floor(diff / 86400);
        const h = Math.floor((diff % 86400) / 3600);
        const m = Math.floor((diff % 3600) / 60);
        if (d > 0) return `${d}d ${h}h`;
        if (h > 0) return `${h}h ${m}m`;
        return `${m}m`;
    };

    const getTaskTimingDisplay = (t) => {
        const now = Math.floor(Date.now() / 1000);
        let startTs = t.start_date || t.created_at || (t.end_date - 86400 * 3);
        if (startTs > t.end_date) startTs = t.end_date - 86400;

        if (t.done) {
            return `<span style="color:#888;">Đã hoàn thành</span>`;
        }
        if (now < startTs) {
            const diff = startTs - now;
            return `<span style="color:var(--primary); font-weight:bold;">Còn ${formatDiff(diff)} trước khi bắt đầu</span>`;
        } else if (now >= startTs && now < t.end_date) {
            const diff = t.end_date - now;
            return `<span style="color:#28a745; font-weight:bold;">Còn ${formatDiff(diff)} trước khi kết thúc</span>`;
        } else {
            return `<span style="color:#dc3545; font-weight:bold;">Đã quá thời hạn</span>`;
        }
    };

    const renderTasks = () => {
        if (!taskList) return;
        let filtered = [...tasksData];

        if (taskState.filter) {
            filtered = filtered.filter(t => (t.labels || "").toLowerCase().includes(taskState.filter.toLowerCase()));
        }

        if (taskState.sort === 'deadline_asc') {
            filtered.sort((a, b) => a.end_date - b.end_date);
        } else if (taskState.sort === 'priority_desc') {
            filtered.sort((a, b) => b.priority - a.priority);
        }

        const totalPages = Math.ceil(filtered.length / taskState.size) || 1;
        if (taskState.page > totalPages) taskState.page = totalPages;

        const startIdx = (taskState.page - 1) * taskState.size;
        const paginated = filtered.slice(startIdx, startIdx + taskState.size);

        if (pageInfo) pageInfo.innerText = `Trang ${taskState.page} / ${totalPages}`;
        if (btnPrevPage) btnPrevPage.disabled = taskState.page === 1;
        if (btnNextPage) btnNextPage.disabled = taskState.page === totalPages;

        taskList.innerHTML = "";
        if (paginated.length === 0) {
            taskList.innerHTML = `<div class="empty-state">No tasks found.</div>`;
            return;
        }

        paginated.forEach(t => {
            const tagsHtml = (t.labels || "").split(",").filter(l => l.trim()).map(l => `<span class="task-tag tag-label">#${l.trim()}</span>`).join("");
            const doneChecked = t.done ? "checked" : "";

            let rowClass = "";
            if (t.done) {
                rowClass = "is-done";
            } else if (t.end_date < Math.floor(Date.now() / 1000)) {
                rowClass = "is-overdue";
            }

            const shortDesc = t.description ? (t.description.length > 20 ? t.description.substring(0, 20) + "..." : t.description) : "No description";

            taskList.innerHTML += `
                <article class="task-row ${rowClass}" onclick="editTask(${t.id})" style="cursor: pointer;" title="Nhấn để chỉnh sửa">
                    <div class="task-col task-main">
                        <div class="col-header">Task</div>
                        <div class="task-title" title="${t.name}">${t.name}</div>
                        <div class="task-desc" title="${t.description || ''}">${shortDesc}</div>
                    </div>
                    <div class="task-col task-priority">
                        <div class="col-header">Priority</div>
                        <div class="task-tags"><span class="task-tag tag-priority">Priority: ${t.priority}</span></div>
                    </div>
                    <div class="task-col task-tags-col">
                        <div class="col-header">Labels</div>
                        <div class="task-tags">${tagsHtml || '<span class="task-tag" style="background:#eee;color:#777;">Trống</span>'}</div>
                    </div>
                    <div class="task-col task-time">
                        <div class="col-header">Thời gian</div>
                        <div class="task-deadline">⏳ ${getTaskTimingDisplay(t)}</div>
                    </div>
                    <div class="task-actions">
                        <input type="checkbox" onclick="event.stopPropagation()" onchange="toggleTaskDone(${t.id}, this.checked)" ${doneChecked} style="transform: scale(1.3); cursor: pointer;">
                        <button class="btn danger" onclick="deleteTaskDirect(event, ${t.id})">Delete</button>
                    </div>
                </article>
            `;
        });
    };

    if (taskSort) taskSort.addEventListener("change", e => { taskState.sort = e.target.value; renderTasks(); });
    if (taskPageSize) taskPageSize.addEventListener("change", e => { taskState.size = parseInt(e.target.value); taskState.page = 1; renderTasks(); });
    if (taskFilterLabel) taskFilterLabel.addEventListener("input", e => { taskState.filter = e.target.value; taskState.page = 1; renderTasks(); });
    if (btnPrevPage) btnPrevPage.addEventListener("click", () => { if (taskState.page > 1) { taskState.page--; renderTasks(); } });
    if (btnNextPage) btnNextPage.addEventListener("click", () => { taskState.page++; renderTasks(); });

    window.toggleTaskDone = async (id, isDone) => {
        try {
            const t = tasksData.find(x => x.id === id);
            if (!t) return;
            const payload = { ...t, done: isDone };
            await fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
            window.loadTasks();
        } catch (err) {
            console.error("Error toggling task done:", err);
        }
    };

    window.deleteTaskDirect = async (event, id) => {
        try {
            event.stopPropagation();
            if (confirm(`Are you sure you want to delete this task?`)) {
                await fetch("/api/events", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id }) });
                window.loadTasks();
            }
        } catch (err) {
            console.error("Error deleting task:", err);
        }
    };

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

                let startTs = t.start_date || t.created_at || (t.end_date - 86400 * 3);
                if (startTs > t.end_date) startTs = t.end_date - 86400;
                const sd = new Date(startTs * 1000);
                taskForm.elements["start_date"].value = `${sd.getFullYear()}-${pad(sd.getMonth() + 1)}-${pad(sd.getDate())}`;
                taskForm.elements["start_hour"].value = sd.getHours();
                taskForm.elements["start_minute"].value = sd.getMinutes();
            }

            if (btnDeleteTask) btnDeleteTask.classList.remove("hidden");
            window.openDrawer("task-drawer");
        } catch (err) {
            console.error("Error editing task:", err);
        }
    };

    if (btnDeleteTask) {
        btnDeleteTask.addEventListener("click", async () => {
            try {
                const id = taskIdInput ? taskIdInput.value : null;
                if (id && confirm(`Are you sure you want to delete this task?`)) {
                    await fetch("/api/events", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id }) });
                    closeTaskDrawer();
                    window.loadTasks();
                }
            } catch (err) {
                console.error("Error deleting task from drawer:", err);
            }
        });
    }

    window.loadTasks();
});
