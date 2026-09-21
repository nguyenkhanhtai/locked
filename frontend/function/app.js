document.addEventListener("DOMContentLoaded", () => {
    // 1. Toast Notification System
    window.showToast = (message, type = 'info') => {
        const container = document.getElementById("toast-container");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        else if (type === 'error') icon = '⚠️';

        toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.transition = "opacity 0.3s, transform 0.3s";
            toast.style.opacity = "0";
            toast.style.transform = "translateY(10px) scale(0.95)";
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    };

    // 2. Highlight Active Nav Item
    const currentPath = window.location.pathname;
    let activeTarget = "welcome";
    if (currentPath.includes("tasks")) activeTarget = "tasks";
    else if (currentPath.includes("study")) activeTarget = "study";

    const navLinkItems = document.querySelectorAll(".nav-link-item");
    navLinkItems.forEach(link => {
        if (link.dataset.target === activeTarget) {
            link.parentElement.classList.add("active");
        } else {
            link.parentElement.classList.remove("active");
        }
    });

    // 3. Settings Modal
    const btnSettings = document.getElementById("btn-settings");
    const settingsModal = document.getElementById("settings-modal");
    const btnCloseSettings = document.getElementById("btn-close-settings-modal");
    const btnCancelSettings = document.getElementById("btn-cancel-settings");
    const btnSaveSettings = document.getElementById("btn-save-settings");
    const themeColorInput = document.getElementById("theme-color");
    const overlay = document.getElementById("overlay");

    const openSettings = () => {
        if (overlay) overlay.classList.remove("hidden");
        if (settingsModal) settingsModal.classList.remove("hidden");
    };

    const closeSettings = () => {
        if (overlay) overlay.classList.add("hidden");
        if (settingsModal) settingsModal.classList.add("hidden");
    };

    if (btnSettings) btnSettings.addEventListener("click", openSettings);
    if (btnCloseSettings) btnCloseSettings.addEventListener("click", closeSettings);
    if (btnCancelSettings) btnCancelSettings.addEventListener("click", closeSettings);

    const applyThemeColor = (color) => {
        if (!color) return;
        document.documentElement.style.setProperty("--primary", color);
        // Generate subtle ring
        document.documentElement.style.setProperty("--primary-ring", `${color}40`);
    };

    if (themeColorInput) {
        themeColorInput.addEventListener("input", (e) => {
            applyThemeColor(e.target.value);
        });
    }

    // Load Settings
    const loadSettings = async () => {
        try {
            const res = await fetch("/api/settings");
            const data = await res.json();
            if (data.data && data.data.theme && data.data.theme.primary) {
                const primaryColor = data.data.theme.primary;
                if (themeColorInput) themeColorInput.value = primaryColor;
                applyThemeColor(primaryColor);
            }
        } catch (e) {
            console.error("Failed to load settings:", e);
        }
    };
    loadSettings();

    if (btnSaveSettings) {
        btnSaveSettings.addEventListener("click", async () => {
            try {
                const primaryColor = themeColorInput ? themeColorInput.value : "#4f46e5";
                const payload = {
                    theme: { primary: primaryColor },
                    ui: { compact_mode: false }
                };
                await fetch("/api/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                applyThemeColor(primaryColor);
                window.showToast("Settings saved!", "success");
                closeSettings();
            } catch (e) {
                window.showToast("Failed to save settings: " + e.message, "error");
            }
        });
    }

    // 4. Marked Global Init
    if (typeof marked !== 'undefined') {
        marked.use({ gfm: true, breaks: true });
        if (typeof markedKatex !== 'undefined') {
            marked.use(markedKatex({ throwOnError: false }));
        }
        window.markedConfigured = true;
    }
});
