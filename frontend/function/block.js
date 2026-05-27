document.addEventListener("DOMContentLoaded", () => {
    const btnAddBlock = document.getElementById("btn-add-block");
    const btnCloseDrawer = document.getElementById("btn-close-drawer");
    const blockForm = document.getElementById("block-form");
    const selectMode = document.getElementById("select-mode");
    const groupDurationTemp = document.getElementById("group-duration-temp");
    const groupDurationPerm = document.getElementById("group-duration-perm");
    const modeDescription = document.getElementById("mode-description");
    const blockList = document.getElementById("block-list");
    const topSitesList = document.getElementById("top-sites-list");
    const overlay = document.getElementById("overlay");

    const closeBlockDrawer = () => {
        const drawerEl = document.getElementById("drawer");
        if (!drawerEl || drawerEl.classList.contains("hidden")) return;
        window.closeDrawer("drawer");
        if (blockForm) blockForm.reset();
        if (groupDurationTemp) groupDurationTemp.style.display = "flex";
        if (groupDurationPerm) groupDurationPerm.style.display = "none";
    };

    if (btnAddBlock) btnAddBlock.addEventListener("click", () => window.openDrawer("drawer"));
    if (btnCloseDrawer) btnCloseDrawer.addEventListener("click", closeBlockDrawer);
    if (overlay) overlay.addEventListener("click", closeBlockDrawer);

    if (selectMode) {
        selectMode.addEventListener("change", (e) => {
            if (e.target.value === "permanent") {
                groupDurationTemp.style.display = "none";
                groupDurationPerm.style.display = "flex";
                if (modeDescription) modeDescription.innerText = "* In this mode, the block duration is measured in days.";
            } else {
                groupDurationTemp.style.display = "flex";
                groupDurationPerm.style.display = "none";
                if (modeDescription) modeDescription.innerText = "* In this mode, you can block a website for up to 11 hours 59 minutes.";
            }
        });
    }

    const loadBlocks = async () => {
        try {
            const res = await fetch("/api/blocks");
            const json = await res.json();
            renderBlocks(json.data);
        } catch (err) {
            console.error("Failed to load blocks:", err);
        }
    };

    const renderBlocks = (data) => {
        const timeOpts = { hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' };
        
        if (!blockList) return;
        blockList.innerHTML = "";
        if (!data) return;
        
        const allBlocks = [
            ...(data.temporary || []).map(b => ({ ...b, type: "Temporary" })),
            ...(data.permanent || []).map(b => ({ ...b, type: "Permanent" }))
        ];

        if (allBlocks.length === 0) {
            blockList.innerHTML = "<p style='color:#777; font-style:italic'>All clear. No websites are currently blocked.</p>";
            return;
        }

        allBlocks.forEach(b => {
            const item = document.createElement("div");
            item.className = "list-item";
            const timeStr = b.open_at 
                ? `Until: ${new Date(b.open_at * 1000).toLocaleString(undefined, timeOpts)}` 
                : `Can remove at: ${new Date(b.unlock_at * 1000).toLocaleString(undefined, timeOpts)}`;

            item.innerHTML = `
                <div>
                    <strong style="font-size:16px;">${b.url}</strong><br>
                    <span class="meta-time">${b.type} | ${timeStr}</span>
                </div>
                <button class="btn danger" onclick="deleteBlock('${b.url}', '${b.type === "Temporary" ? "temporary" : "permanent"}')">Unblock</button>
            `;
            blockList.appendChild(item);
        });
    };

    const loadTopSites = async () => {
        try {
            const res = await fetch("/api/top-sites");
            const json = await res.json();
            renderTopSites(json.data);
        } catch (err) {
            console.error("Failed to load top sites:", err);
        }
    };

    const renderTopSites = (data) => {
        if (!topSitesList) return;
        topSitesList.innerHTML = "";
        if (!data || data.length === 0) {
            topSitesList.innerHTML = "<p style='color:#777; font-style:italic'>No tracking data yet.</p>";
            return;
        }
        const maxTime = Math.max(...data.map(d => d.time_spent));

        data.forEach(site => {
            const timeStr = site.formatted_time;

            const percent = maxTime > 0 ? (site.time_spent / maxTime) * 100 : 0;

            topSitesList.innerHTML += `<div class="bar-row"><div class="bar-head"><span>${site.domain}</span><span style="color:#777; font-weight:normal">${timeStr}</span></div><div class="bar-track"><div class="bar-fill" style="width: ${percent}%"></div></div></div>`;
        });
    };

    if (blockForm) {
        blockForm.addEventListener("submit", async (e) => {
            try {
                e.preventDefault();
                const formData = new FormData(blockForm);
                const mode = formData.get("mode");
                const payload = { url: formData.get("url"), mode: mode };

                if (mode === "temporary") {
                    const h = parseInt(formData.get("temp_hours") || 0);
                    const m = parseInt(formData.get("temp_minutes") || 0);
                    payload.duration = { hours: h, minutes: m, seconds: 0 };
                } else {
                    const d = parseInt(formData.get("perm_days") || 1);
                    payload.duration = { days: d, hours: 0, minutes: 0, seconds: 0 };
                }
                
                await fetch("/api/block", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
                closeBlockDrawer(); loadBlocks();
            } catch (err) {
                console.error("Error adding block:", err);
                alert("Failed to add block.");
            }
        });
    }

    window.deleteBlock = async (url, mode) => {
        try {
            if(confirm(`Are you sure you want to unblock ${url}?`)) {
                const res = await fetch("/api/block", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, mode }) });
                const data = await res.json();
                if (!res.ok) alert("❌ Error: " + data.message);
                loadBlocks();
            }
        } catch (err) {
            console.error("Error deleting block:", err);
            alert("Failed to delete block.");
        }
    };

    const loadFocusStatus = async () => {
        try {
            const res = await fetch("/api/focus/status");
            const json = await res.json();
            const status = json.data;
            
            const banner = document.getElementById("focus-active-banner");
            const btnFocusMode = document.getElementById("btn-focus-mode");
            const btnToggleFocus = document.getElementById("btn-toggle-focus");

            if (status.is_active) {
                if (banner) banner.style.display = "flex";
                if (btnFocusMode) btnFocusMode.innerText = "Focus Mode (Active)";
                if (btnToggleFocus) btnToggleFocus.innerText = "Tắt Focus";
                startFocusCountdown(status.end_at);
            } else {
                if (banner) banner.style.display = "none";
                if (btnFocusMode) btnFocusMode.innerText = "Focus Mode";
                if (btnToggleFocus) btnToggleFocus.innerText = "Bật Focus";
                stopFocusCountdown();
            }
        } catch (err) {
            console.error("Failed to load focus status:", err);
        }
    };

    let focusTimerInterval = null;
    const startFocusCountdown = (endAt) => {
        if (focusTimerInterval) clearInterval(focusTimerInterval);
        const countdownEl = document.getElementById("focus-countdown");
        if (!countdownEl) return;

        const update = () => {
            const now = Math.floor(Date.now() / 1000);
            const remaining = endAt - now;
            if (remaining <= 0) {
                countdownEl.innerText = "00:00:00";
                loadFocusStatus();
                clearInterval(focusTimerInterval);
                return;
            }
            const h = Math.floor(remaining / 3600);
            const m = Math.floor((remaining % 3600) / 60);
            const s = remaining % 60;
            countdownEl.innerText = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        };
        update();
        focusTimerInterval = setInterval(update, 1000);
    };

    const stopFocusCountdown = () => {
        if (focusTimerInterval) clearInterval(focusTimerInterval);
        focusTimerInterval = null;
    };

    const loadFocusList = async () => {
        try {
            const res = await fetch("/api/focus/list");
            const json = await res.json();
            renderFocusList(json.data);
        } catch (err) {
            console.error("Failed to load focus list:", err);
        }
    };

    const renderFocusList = (data) => {
        const container = document.getElementById("focus-list-container");
        if (!container) return;
        container.innerHTML = "";
        if (!data || data.length === 0) {
            container.innerHTML = "<p style='color:#777; font-style:italic; padding: 10px;'>No allowed websites.</p>";
            return;
        }

        data.forEach(url => {
            const item = document.createElement("div");
            item.className = "list-item";
            item.style.padding = "5px 10px";
            item.innerHTML = `
                <span style="font-size: 14px;">${url}</span>
                <button class="btn danger" style="padding: 2px 8px; font-size: 12px;" onclick="deleteFocusUrl('${url}')">Xóa</button>
            `;
            container.appendChild(item);
        });
    };

    window.deleteFocusUrl = async (url) => {
        try {
            await fetch("/api/focus/list", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url })
            });
            loadFocusList();
        } catch (err) {
            console.error("Error deleting focus url:", err);
        }
    };

    const btnFocusMode = document.getElementById("btn-focus-mode");
    const btnCloseFocusDrawer = document.getElementById("btn-close-focus-drawer");
    const btnToggleFocus = document.getElementById("btn-toggle-focus");
    const btnAddFocusUrl = document.getElementById("btn-add-focus-url");
    const btnStopFocus = document.getElementById("btn-stop-focus");

    if (btnFocusMode) btnFocusMode.addEventListener("click", () => {
        window.openDrawer("focus-drawer");
        loadFocusList();
    });

    if (btnCloseFocusDrawer) btnCloseFocusDrawer.addEventListener("click", () => window.closeDrawer("focus-drawer"));

    if (btnToggleFocus) btnToggleFocus.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/focus/status");
            const json = await res.json();
            const isActive = json.data.is_active;

            const duration = parseInt(document.getElementById("focus-duration").value || 25) * 60;
            
            await fetch("/api/focus/toggle", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_active: !isActive, duration })
            });
            
            loadFocusStatus();
            window.closeDrawer("focus-drawer");
        } catch (err) {
            console.error("Error toggling focus:", err);
        }
    });

    if (btnStopFocus) btnStopFocus.addEventListener("click", async () => {
        try {
            await fetch("/api/focus/toggle", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_active: false })
            });
            loadFocusStatus();
        } catch (err) {
            console.error("Error stopping focus:", err);
        }
    });

    if (btnAddFocusUrl) btnAddFocusUrl.addEventListener("click", async () => {
        try {
            const url = prompt("Nhập URL/Domain cho phép (VD: google.com):");
            if (url) {
                await fetch("/api/focus/list", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url })
                });
                loadFocusList();
            }
        } catch (err) {
            console.error("Error adding focus url:", err);
        }
    });

    loadBlocks();
    loadTopSites();
    loadFocusStatus();
    setInterval(loadTopSites, 60000);
    setInterval(loadFocusStatus, 10000); // Poll focus status every 10s
});
