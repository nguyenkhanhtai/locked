document.addEventListener("DOMContentLoaded", async () => {
    const statusIndicator = document.getElementById("status-indicator");
    const statusLabel = document.getElementById("status-label");
    const rulesContainer = document.getElementById("rules-container");
    const btnOpenApp = document.getElementById("btn-open-app");

    btnOpenApp.addEventListener("click", () => {
        chrome.tabs.create({ url: "http://127.0.0.1:8765/blocker" });
    });

    async function renderPopup() {
        const stored = await chrome.storage.local.get(["activeRules", "isConnected"]);
        const isConnected = stored.isConnected !== false;
        const activeRules = stored.activeRules || [];

        if (statusIndicator && statusLabel) {
            if (isConnected) {
                statusIndicator.className = "status-dot";
                statusLabel.textContent = "Connected";
            } else {
                statusIndicator.className = "status-dot disconnected";
                statusLabel.textContent = "Offline (Cached)";
            }
        }

        const now = Math.floor(Date.now() / 1000);
        const validRules = activeRules.filter(r => r.blocked_until > now);

        if (!rulesContainer) return;

        if (validRules.length === 0) {
            rulesContainer.innerHTML = '<div class="empty-state">No sites currently locked.<br>Add one in Locked App!</div>';
            return;
        }

        rulesContainer.innerHTML = "";
        validRules.forEach(rule => {
            const item = document.createElement("div");
            item.className = "rule-item";

            const remaining = Math.max(0, rule.blocked_until - now);
            const h = Math.floor(remaining / 3600);
            const m = Math.floor((remaining % 3600) / 60);
            const s = remaining % 60;
            const timeStr = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;

            const targetDiv = document.createElement("div");
            targetDiv.className = "rule-target";
            targetDiv.title = rule.url_pattern;
            targetDiv.textContent = `🚫 ${rule.url_pattern}`;

            const timeDiv = document.createElement("div");
            timeDiv.className = "rule-time";
            timeDiv.setAttribute("data-until", rule.blocked_until);
            timeDiv.textContent = timeStr;

            item.appendChild(targetDiv);
            item.appendChild(timeDiv);
            rulesContainer.appendChild(item);

        });
    }

    renderPopup();

    // Tick every second
    setInterval(() => {
        const now = Math.floor(Date.now() / 1000);
        document.querySelectorAll(".rule-time[data-until]").forEach(el => {
            const until = parseInt(el.getAttribute("data-until"), 10);
            const rem = Math.max(0, until - now);
            const h = Math.floor(rem / 3600);
            const m = Math.floor((rem % 3600) / 60);
            const s = rem % 60;
            el.textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        });
    }, 1000);
});

