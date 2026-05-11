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
            ...(data.temporary || []).map(b => ({ ...b, type: "Tạm thời" })),
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
                <button class="btn danger" onclick="deleteBlock('${b.url}', '${b.type === "Tạm thời" ? "temporary" : "permanent"}')">Gỡ Chặn</button>
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
        });
    }

    window.deleteBlock = async (url, mode) => {
        if(confirm(`Are you sure you want to unblock ${url}?`)) {
            const res = await fetch("/api/block", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, mode }) });
            const data = await res.json();
            if (!res.ok) alert("❌ Error: " + data.message);
            loadBlocks();
        }
    };

    loadBlocks();
    loadTopSites();
    setInterval(loadTopSites, 60000);
});
