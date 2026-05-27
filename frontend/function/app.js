document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements cho UI cốt lõi
    const navItems = document.querySelectorAll(".nav-links li");
    const pages = document.querySelectorAll(".page");
    const themeColor = document.getElementById("theme-color");
    const overlay = document.getElementById("overlay");

    // Element cho Cài đặt chung
    const btnSettings = document.getElementById("btn-settings");

    // 1. Đổi Tab Điều Hướng (Nav Bar)
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            try {
                navItems.forEach(n => n.classList.remove("active"));
                pages.forEach(p => p.classList.remove("active"));
                item.classList.add("active");
                const targetEl = document.getElementById(item.dataset.target);
                if (targetEl) targetEl.classList.add("active");

                // Lưu trạng thái tab hiện tại vào LocalStorage
                localStorage.setItem("locked_active_main_tab", item.dataset.target);

                // Hide AI button if not on study page
                const btnToggleAiGlobal = document.getElementById('btn-toggle-ai-assistant');
                if (btnToggleAiGlobal && item.dataset.target !== 'study') {
                    btnToggleAiGlobal.style.display = 'none';
                }

                // Tự động tải lại danh sách task mỗi khi người dùng chuyển sang tab Task List
                if (item.dataset.target === "tasks" && typeof window.loadTasks === "function") {
                    window.loadTasks();
                }
            } catch (err) {
                console.error("Navigation error:", err);
            }
        });
    });

    // Khôi phục trạng thái tab chính sau khi tải lại trang
    try {
        const savedMainTab = localStorage.getItem("locked_active_main_tab");
        if (savedMainTab) {
            const targetNav = Array.from(navItems).find(n => n.dataset.target === savedMainTab);
            if (targetNav && !targetNav.classList.contains("active")) {
                targetNav.click();
            }
        }
    } catch (err) {
        console.error("Failed to restore main tab:", err);
    }


    // 2. Mở Cài đặt chung (Modal)
    const settingsModalOverlay = document.getElementById("settings-modal-overlay");
    const btnCloseSettingsModal = document.getElementById("btn-close-settings-modal");

    if (btnSettings && settingsModalOverlay) {
        btnSettings.addEventListener("click", () => {
            settingsModalOverlay.classList.remove("hidden");
        });
    }

    if (btnCloseSettingsModal && settingsModalOverlay) {
        btnCloseSettingsModal.addEventListener("click", () => {
            settingsModalOverlay.classList.add("hidden");
        });
        settingsModalOverlay.addEventListener("click", (e) => {
            if (e.target === settingsModalOverlay) {
                settingsModalOverlay.classList.add("hidden");
            }
        });
    }

    // Xử lý chuyển tab trong Settings Modal
    const settingsTabBtns = document.querySelectorAll(".settings-tab-btn");
    const settingsTabContents = document.querySelectorAll(".settings-tab-content");

    settingsTabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            settingsTabBtns.forEach(b => {
                b.classList.remove("primary");
                b.classList.add("outline");
            });
            btn.classList.remove("outline");
            btn.classList.add("primary");

            settingsTabContents.forEach(content => {
                content.style.display = "none";
            });

            const targetId = btn.dataset.tab;
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                targetContent.style.display = "block";
            }
        });
    });

    // 2. Chỉnh màu chủ đạo
    themeColor.addEventListener("input", (e) => {
        document.documentElement.style.setProperty("--primary", e.target.value);
    });

    // 3. Quản lý Drawer (Màn hình phụ)
    // 4. Các hàm tiện ích dùng chung toàn cục (Window) để mở các Menu nổi
    window.openDrawer = (drawerId) => {
        if (overlay) overlay.classList.remove("hidden");
        const drawer = document.getElementById(drawerId);
        if (drawer) drawer.classList.remove("hidden");
    };

    window.closeDrawer = (drawerId) => {
        if (overlay) overlay.classList.add("hidden");
        const drawer = document.getElementById(drawerId);
        if (drawer) drawer.classList.add("hidden");
    };

    // 5. Quản lý cài đặt chung (Lưu API và Hotkeys)
    let apiKeysState = { provider: "gemini", gemini: "", openai: "", openrouter: "", chat_models: {}, eval_models: {} };
    const modeSelect = document.getElementById("settings-ai-eval-mode");

    const providerApiRows = Array.from(document.querySelectorAll(".ai-provider-api-row[data-provider]"));
    const providerModelRows = Array.from(document.querySelectorAll(".ai-provider-model-row[data-provider]"));

    const apiKeyInputs = Array.from(document.querySelectorAll(".ai-api-key[data-provider]"));
    const chatModelInputs = Array.from(document.querySelectorAll(".ai-chat-model[data-provider]"));
    const evalModelInputs = Array.from(document.querySelectorAll(".ai-eval-model[data-provider]"));
    const toggleKeyButtons = Array.from(document.querySelectorAll(".ai-toggle-key[data-provider]"));

    const providersInUI = [...providerApiRows, ...providerModelRows].map(r => r.dataset.provider).filter(Boolean);

    const setProviderInputValues = (provider) => {
        const apiKeyEl = apiKeyInputs.find(i => i.dataset.provider === provider);
        const chatModelEl = chatModelInputs.find(i => i.dataset.provider === provider);
        const evalModelEl = evalModelInputs.find(i => i.dataset.provider === provider);
        if (apiKeyEl) apiKeyEl.value = apiKeysState[provider] || "";
        if (chatModelEl) chatModelEl.value = apiKeysState.chat_models[provider] || "";
        if (evalModelEl) evalModelEl.value = apiKeysState.eval_models[provider] || "";
    };

    apiKeyInputs.forEach((el) => {
        el.addEventListener("input", (e) => {
            const provider = e.target.dataset.provider;
            if (!provider) return;
            apiKeysState[provider] = e.target.value;
        });
    });

    chatModelInputs.forEach((el) => {
        el.addEventListener("input", (e) => {
            const provider = e.target.dataset.provider;
            if (!provider) return;
            apiKeysState.chat_models[provider] = e.target.value;
        });
    });

    evalModelInputs.forEach((el) => {
        el.addEventListener("input", (e) => {
            const provider = e.target.dataset.provider;
            if (!provider) return;
            apiKeysState.eval_models[provider] = e.target.value;
        });
    });

    toggleKeyButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            const provider = btn.dataset.provider;
            const apiKeyEl = apiKeyInputs.find(i => i.dataset.provider === provider);
            if (!apiKeyEl) return;
            const showing = apiKeyEl.type === "text";
            apiKeyEl.type = showing ? "password" : "text";
            btn.textContent = showing ? "Show key" : "Hide key";
        });
    });

    const loadSettings = async () => {
        try {
            const res = await fetch("/api/settings");
            const json = await res.json();
            if (json.data) {
                const hk = json.data.hotkeys || {};
                const keys = json.data.api_keys || {};
                const params = json.data.model_params || {};
                const toolParams = json.data.tool_params || {};

                if (hk.block) document.getElementById("hotkey-block").value = hk.block;
                if (hk.task) document.getElementById("hotkey-task").value = hk.task;
                if (hk.memorize) document.getElementById("hotkey-memorize").value = hk.memorize;

                apiKeysState.provider = keys.provider || "gemini";
                apiKeysState.gemini = keys.gemini || "";
                apiKeysState.openai = keys.openai || "";
                apiKeysState.openrouter = keys.openrouter || "";
                apiKeysState.chat_models = keys.chat_models || { gemini: "", openai: "", openrouter: "" };
                apiKeysState.eval_models = keys.eval_models || { gemini: "", openai: "", openrouter: "" };
                if (keys.eval_mode && modeSelect) modeSelect.value = keys.eval_mode;

                providersInUI.forEach((provider) => setProviderInputValues(provider));

                if (params.temperature !== undefined) document.getElementById("model-temperature").value = params.temperature;
                if (params.top_k !== undefined) document.getElementById("model-top-k").value = params.top_k;
                if (params.top_p !== undefined) document.getElementById("model-top-p").value = params.top_p;

                if (toolParams.max_tool_rounds !== undefined) {
                    const toolRoundsEl = document.getElementById("tool-max-rounds");
                    if (toolRoundsEl) toolRoundsEl.value = toolParams.max_tool_rounds;
                }

                if (json.data.system_prompt !== undefined) document.getElementById("model-system-prompt").value = json.data.system_prompt;
            }
        } catch (e) {
            console.error("Failed to load settings:", e);
        }
    };
    loadSettings();

    const btnSaveSettings = document.getElementById("btn-save-settings");
    if (btnSaveSettings) {
        btnSaveSettings.addEventListener("click", async () => {
            providersInUI.forEach((provider) => {
                const apiKeyEl = apiKeyInputs.find(i => i.dataset.provider === provider);
                const chatModelEl = chatModelInputs.find(i => i.dataset.provider === provider);
                const evalModelEl = evalModelInputs.find(i => i.dataset.provider === provider);
                if (apiKeyEl) apiKeysState[provider] = apiKeyEl.value;
                if (chatModelEl) apiKeysState.chat_models[provider] = chatModelEl.value;
                if (evalModelEl) apiKeysState.eval_models[provider] = evalModelEl.value;
            });

            const payload = {
                hotkeys: {
                    block: document.getElementById("hotkey-block").value || "ctrl+alt+shift+b",
                    task: document.getElementById("hotkey-task").value || "ctrl+alt+shift+t",
                    memorize: document.getElementById("hotkey-memorize").value || "ctrl+alt+shift+m"
                },
                api_keys: {
                    provider: apiKeysState.provider || "gemini",
                    eval_mode: modeSelect ? modeSelect.value : "similarity",
                    gemini: apiKeysState.gemini,
                    openai: apiKeysState.openai,
                    openrouter: apiKeysState.openrouter,
                    chat_models: apiKeysState.chat_models,
                    eval_models: apiKeysState.eval_models
                },
                tool_params: {
                    max_tool_rounds: parseInt(document.getElementById("tool-max-rounds").value) || 8
                },
                model_params: {
                    temperature: parseFloat(document.getElementById("model-temperature").value) || 0.7,
                    top_k: parseInt(document.getElementById("model-top-k").value) || 40,
                    top_p: parseFloat(document.getElementById("model-top-p").value) || 0.9
                },
                system_prompt: document.getElementById("model-system-prompt").value || ""
            };
            try {
                await fetch("/api/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                alert("✅ Settings saved!");
                if (typeof settingsModalOverlay !== 'undefined' && settingsModalOverlay) {
                    settingsModalOverlay.classList.add("hidden");
                }
            } catch (e) {
                alert("Save failed: " + e.message);
            }
        });
    }
});
