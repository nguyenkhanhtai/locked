function initApp() {
    // 1. Theme Management (Dark / Light)
    const getSavedTheme = () => localStorage.getItem("locked-theme") || "dark";
    
    const setTheme = (theme) => {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("locked-theme", theme);

        // Update sidebar toggle button UI
        const themeIcon = document.getElementById("theme-toggle-icon");
        const themeLabel = document.getElementById("theme-toggle-label");
        if (themeIcon) {
            themeIcon.innerHTML = theme === 'dark' ? '<use href="#icon-sun"></use>' : '<use href="#icon-moon"></use>';
        }
        if (themeLabel) {
            themeLabel.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
        }

        // Update modal buttons if open
        const btnDark = document.getElementById("theme-btn-dark");
        const btnLight = document.getElementById("theme-btn-light");
        if (btnDark && btnLight) {
            if (theme === 'dark') {
                btnDark.classList.add("primary");
                btnDark.classList.remove("outline");
                btnLight.classList.add("outline");
                btnLight.classList.remove("primary");
            } else {
                btnLight.classList.add("primary");
                btnLight.classList.remove("outline");
                btnDark.classList.add("outline");
                btnDark.classList.remove("primary");
            }
        }
    };

    // Initialize theme UI
    setTheme(getSavedTheme());

    // Sidebar theme toggle click
    const btnThemeToggle = document.getElementById("btn-theme-toggle");
    if (btnThemeToggle) {
        btnThemeToggle.addEventListener("click", () => {
            const current = getSavedTheme();
            const next = current === "dark" ? "light" : "dark";
            setTheme(next);
        });
    }

    // Modal theme buttons
    const btnDark = document.getElementById("theme-btn-dark");
    const btnLight = document.getElementById("theme-btn-light");
    if (btnDark) btnDark.addEventListener("click", () => setTheme("dark"));
    if (btnLight) btnLight.addEventListener("click", () => setTheme("light"));

    // 2. Toast Notification System with Clean SVGs
    window.showToast = (message, type = 'info') => {
        const container = document.getElementById("toast-container");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        let iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
        if (type === 'success') {
            iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg>';
        } else if (type === 'error') {
            iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
        }

        toast.innerHTML = `${iconSvg}<span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.transition = "opacity 0.2s, transform 0.2s";
            toast.style.opacity = "0";
            toast.style.transform = "translateY(8px) scale(0.96)";
            setTimeout(() => toast.remove(), 200);
        }, 2800);
    };

    // 3. Highlight Active Nav Item
    const currentPath = window.location.pathname;
    let activeTarget = "welcome";
    if (currentPath.includes("tasks")) activeTarget = "tasks";
    else if (currentPath.includes("study")) activeTarget = "study";

    const navLinkItems = document.querySelectorAll(".nav-link-item");
    navLinkItems.forEach(link => {
        if (link.dataset.target === activeTarget) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });

    // 4. Preferences Modal
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
        document.documentElement.style.setProperty("--primary-ring", `${color}40`);
    };

    if (themeColorInput) {
        themeColorInput.addEventListener("input", (e) => {
            applyThemeColor(e.target.value);
        });
    }

    // Load Settings from server
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
                const primaryColor = themeColorInput ? themeColorInput.value : "#4c6ef5";
                const payload = {
                    theme: { primary: primaryColor },
                    ui: { compact_mode: false }
                };
                await fetch("/api/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                closeSettings();
                showToast("Preferences saved", "success");
            } catch (e) {
                showToast("Failed to save preferences", "error");
            }
        });
    }
}

if (document.readyState === 'loading') {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}
