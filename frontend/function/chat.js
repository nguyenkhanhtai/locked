document.addEventListener("DOMContentLoaded", () => {
    const chatInput = document.getElementById("chat-input");
    const btnSend = document.getElementById("btn-send-chat");
    const chatMessages = document.getElementById("chat-messages");
    
    // Unified Settings Elements
    const btnChatOpenSettings = document.getElementById("btn-chat-open-settings");
    const aiSettingsDrawer = document.getElementById("ai-settings-drawer");
    const btnCloseAiSettings = document.getElementById("btn-close-ai-settings");
    const btnAiSettingsDone = document.getElementById("btn-ai-settings-done");
    const aiProviderOptions = document.querySelectorAll(".ai-provider-option");
    const aiModelListContainer = document.getElementById("ai-model-list-container");
    const aiCustomModelInput = document.getElementById("ai-custom-model-input");
    const btnAiApplyCustom = document.getElementById("btn-ai-apply-custom");

    const chatCurrentProviderBadge = document.getElementById("chat-current-provider-badge");
    const chatCurrentModelDisplay = document.getElementById("chat-current-model-display");

    const btnNewChat = document.getElementById("btn-new-chat");
    const chatTemporaryTab = document.getElementById("chat-temporary-tab");
    const chatSessionList = document.getElementById("chat-session-list");
    const chatCurrentLabel = document.getElementById("chat-current-label");
    const btnDeleteChatSession = document.getElementById("btn-delete-chat-session");
    const btnSelectProvider = document.getElementById("btn-select-provider");
    const providerSelectOverlay = document.getElementById("provider-select-overlay");

    if (
        !chatInput ||
        !btnSend ||
        !chatMessages ||
        !btnNewChat ||
        !chatTemporaryTab ||
        !chatSessionList ||
        !chatCurrentLabel
    ) {
        return;
    }

    const DEFAULT_BOT_MESSAGE = "Hi! I'm your AI assistant. Have you configured your API key in Settings? What can I help you with today?";
    const NEW_CHAT_ID = "new";
    const MODELS_DATA = {
        gemini: [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash"
        ],
        openai: [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ],
        openrouter: [
            "google/gemini-2.5-pro",
            "anthropic/claude-3.5-sonnet",
            "deepseek/deepseek-chat",
            "deepseek/deepseek-r1"
        ]
    };

    const CHAT_PROVIDER_KEY = 'locked_chat_page_provider';
    const CHAT_MODELS_KEY = 'locked_chat_page_saved_models';

    let sessions = [];
    let currentView = NEW_CHAT_ID;
    
    let chatSelectedProvider = localStorage.getItem(CHAT_PROVIDER_KEY) || 'gemini';
    let chatSavedModels = JSON.parse(localStorage.getItem(CHAT_MODELS_KEY) || '{}');
    if (!chatSavedModels.gemini) {
        chatSavedModels = { 
            gemini: "gemini-2.5-flash", 
            openai: "gpt-4o-mini", 
            openrouter: "google/gemini-2.5-pro" 
        };
    }
    
    let currentOffset = 0;
    let hasMoreMessages = true;
    let isLoadingHistory = false;
    let currentSessionMessages = [];

    // Unified Drawer Functions
    const syncChatModelDisplay = () => {
        const currentModel = chatSavedModels[chatSelectedProvider] || "Select Model...";
        if (chatCurrentModelDisplay) chatCurrentModelDisplay.innerText = currentModel;
        if (chatCurrentProviderBadge) {
            chatCurrentProviderBadge.innerText = chatSelectedProvider.toUpperCase();
            const colors = { gemini: '#007bff', openai: '#10a37f', openrouter: '#7c3aed' };
            chatCurrentProviderBadge.style.background = colors[chatSelectedProvider] || 'var(--primary)';
        }
    };

    const openDrawer = (id) => {
        document.getElementById('overlay')?.classList.remove('hidden');
        document.getElementById(id)?.classList.remove('hidden');
    };
    const closeDrawer = (id) => {
        document.getElementById('overlay')?.classList.add('hidden');
        document.getElementById(id)?.classList.add('hidden');
    };

    const renderChatModelList = () => {
        if (!aiModelListContainer) return;
        aiModelListContainer.innerHTML = "";
        const options = MODELS_DATA[chatSelectedProvider] || [];
        
        options.forEach(model => {
            const btn = document.createElement("button");
            btn.className = "btn outline";
            btn.style.textAlign = "left";
            btn.style.padding = "10px 12px";
            btn.style.fontSize = "13px";
            btn.style.justifyContent = "flex-start";
            btn.style.border = "1px solid var(--border)";
            btn.innerText = model;
            
            if (chatSavedModels[chatSelectedProvider] === model) {
                btn.style.borderColor = "var(--primary)";
                btn.style.background = "#f0f7ff";
                btn.style.fontWeight = "bold";
            }
            
            btn.addEventListener("click", () => {
                chatSavedModels[chatSelectedProvider] = model;
                localStorage.setItem(CHAT_MODELS_KEY, JSON.stringify(chatSavedModels));
                syncChatModelDisplay();
                renderChatModelList();
            });
            aiModelListContainer.appendChild(btn);
        });
    };

    const updateChatProviderUI = () => {
        aiProviderOptions.forEach(opt => {
            if (opt.dataset.provider === chatSelectedProvider) {
                opt.style.borderColor = "var(--primary)";
                opt.style.background = "#f0f7ff";
                opt.style.fontWeight = "bold";
            } else {
                opt.style.borderColor = "var(--border)";
                opt.style.background = "#fff";
                opt.style.fontWeight = "normal";
            }
        });
    };

    // Chat Settings Handlers
    if (btnChatOpenSettings) {
        btnChatOpenSettings.addEventListener('click', () => {
            // Hijack the global drawer for Chat Page
            window._ai_config_mode = 'chat'; 
            updateChatProviderUI();
            renderChatModelList();
            if (aiCustomModelInput) aiCustomModelInput.value = chatSavedModels[chatSelectedProvider] || "";
            openDrawer('ai-settings-drawer');
        });
    }

    // Global Drawer Handlers (Listening to clicks on provider options)
    aiProviderOptions.forEach(btn => {
        btn.addEventListener('click', () => {
            if (window._ai_config_mode !== 'chat') return;
            chatSelectedProvider = btn.dataset.provider;
            localStorage.setItem(CHAT_PROVIDER_KEY, chatSelectedProvider);
            updateChatProviderUI();
            renderChatModelList();
            syncChatModelDisplay();
        });
    });

    if (btnAiApplyCustom && aiCustomModelInput) {
        btnAiApplyCustom.addEventListener('click', () => {
            if (window._ai_config_mode !== 'chat') return;
            const val = aiCustomModelInput.value.trim();
            if (val) {
                chatSavedModels[chatSelectedProvider] = val;
                localStorage.setItem(CHAT_MODELS_KEY, JSON.stringify(chatSavedModels));
                syncChatModelDisplay();
                renderChatModelList();
            }
        });
    }

    if (btnCloseAiSettings) btnCloseAiSettings.addEventListener('click', () => closeDrawer('ai-settings-drawer'));
    if (btnAiSettingsDone) btnAiSettingsDone.addEventListener('click', () => closeDrawer('ai-settings-drawer'));

    syncChatModelDisplay();

    // Ensure core marked config is applied first
    if (typeof window.initMarked === 'function') window.initMarked();
    const escapeHtml = (value) => value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll("\"", "&quot;");

    const createMessageElement = (text, sender) => {
        const msgWrapper = document.createElement("div");
        msgWrapper.className = `chat-message ${sender}`;
        msgWrapper.style.alignSelf = sender === "user" ? "flex-end" : "flex-start";
        msgWrapper.style.background = sender === "user" ? "var(--primary)" : "#f0f0f0";
        msgWrapper.style.color = sender === "user" ? "#fff" : "var(--text)";
        msgWrapper.style.padding = "12px 16px";
        msgWrapper.style.borderRadius = sender === "user" ? "12px 12px 0 12px" : "12px 12px 12px 0";
        msgWrapper.style.maxWidth = sender === "user" ? "80%" : "100%"; // Cho phép bot mở rộng 100%
        msgWrapper.style.minWidth = "0"; 
        msgWrapper.style.wordBreak = "break-word";
        msgWrapper.style.lineHeight = "1.5";
        
        const contentDiv = document.createElement("div");
        contentDiv.classList.add("content-md");
        contentDiv.innerHTML = typeof marked !== 'undefined' ? marked.parse(text) : escapeHtml(text);
        
        msgWrapper.appendChild(contentDiv);
        return { msgWrapper, contentDiv };
    };

    const appendMessage = (text, sender, scrollToBottom = true, animate = false) => {
        let reasoningContent = "";
        let mainText = text;
        
        if (sender === "bot") {
            const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
            mainText = text.replace(thinkRegex, (match, p1) => {
                reasoningContent += p1.trim() + "\n\n";
                return "";
            }).trim();
            if (!mainText) mainText = "✅ Done.";
        }

        const { msgWrapper, contentDiv } = createMessageElement(animate ? "" : mainText, sender);
        
        if (reasoningContent && sender === "bot") {
            const btn = document.createElement("button");
            btn.className = "btn outline";
            btn.innerHTML = "💡 View Reasoning";
            btn.style.cssText = "padding: 4px 12px; font-size: 12px; border-radius: 20px; margin-bottom: 10px; background: #fff; cursor: pointer; border: 1px solid var(--primary); color: var(--primary); font-weight: bold;";
            btn.addEventListener("click", () => {
                const modal = document.getElementById("reasoning-modal-overlay");
                const content = document.getElementById("reasoning-modal-content");
                if (modal && content) {
                    content.innerHTML = typeof marked !== 'undefined' ? marked.parse(reasoningContent) : escapeHtml(reasoningContent);
                    modal.classList.remove("hidden");
                }
            });
            msgWrapper.insertBefore(btn, contentDiv);
        }

        chatMessages.appendChild(msgWrapper);

        if (animate && sender === "bot") {
            let i = 0;
            let rawText = "";
            const speed = 15; // Tốc độ hiển thị chữ
            const interval = setInterval(() => {
                if (i < mainText.length) {
                    rawText += mainText.charAt(i);
                    contentDiv.innerHTML = typeof marked !== 'undefined' ? marked.parse(rawText) : escapeHtml(rawText);
                    i++;
                    if (scrollToBottom) chatMessages.scrollTop = chatMessages.scrollHeight;
                } else {
                    clearInterval(interval);
                }
            }, speed);
        } else {
            if (scrollToBottom) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        }
    };

    const prependMessages = (messages) => {
        if (!messages.length) return;
        const oldScrollHeight = chatMessages.scrollHeight;
        const fragment = document.createDocumentFragment();
        
        messages.forEach((msg) => {
            let reasoningContent = "";
            let mainText = msg.content;
            if (msg.role === "bot") {
                const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
                mainText = mainText.replace(thinkRegex, (match, p1) => {
                    reasoningContent += p1.trim() + "\n\n";
                    return "";
                }).trim();
            }

            const { msgWrapper, contentDiv } = createMessageElement(mainText, msg.role === "user" ? "user" : "bot");
            
            if (reasoningContent && msg.role === "bot") {
                const btn = document.createElement("button");
                btn.className = "btn outline";
                btn.innerHTML = "💡 View Reasoning";
                btn.style.cssText = "padding: 4px 12px; font-size: 12px; border-radius: 20px; margin-bottom: 10px; background: #fff; cursor: pointer; border: 1px solid var(--primary); color: var(--primary); font-weight: bold;";
                btn.addEventListener("click", () => {
                    const modal = document.getElementById("reasoning-modal-overlay");
                    const content = document.getElementById("reasoning-modal-content");
                    if (modal && content) {
                        content.innerHTML = typeof marked !== 'undefined' ? marked.parse(reasoningContent) : escapeHtml(reasoningContent);
                        modal.classList.remove("hidden");
                    }
                });
                msgWrapper.insertBefore(btn, contentDiv);
            }
            
            fragment.appendChild(msgWrapper);
        });
        
        chatMessages.insertBefore(fragment, chatMessages.firstChild);
        chatMessages.scrollTop = chatMessages.scrollHeight - oldScrollHeight;
    };

    const renderDefaultGreeting = () => {
        appendMessage(DEFAULT_BOT_MESSAGE, "bot", false);
    };

    const renderMessages = (messages) => {
        chatMessages.innerHTML = "";
        if (!messages.length && currentOffset === 0) {
            renderDefaultGreeting();
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return;
        }

        messages.forEach((msg) => {
            appendMessage(msg.content, msg.role === "user" ? "user" : "bot", false);
        });
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    const setActiveSidebar = () => {
        const isNewChat = currentView === NEW_CHAT_ID;
        chatTemporaryTab.style.background = isNewChat ? "#e9f2ff" : "#ffffff";
        chatTemporaryTab.style.borderColor = isNewChat ? "var(--primary)" : "var(--border)";
        chatCurrentLabel.innerText = isNewChat
            ? "New Chat"
            : (sessions.find((session) => String(session.id) === String(currentView))?.title || "Chat");

        if (isNewChat) {
            if(btnDeleteChatSession) btnDeleteChatSession.classList.add("hidden");
        } else {
            if(btnDeleteChatSession) btnDeleteChatSession.classList.remove("hidden");                                                                                                                                                                                                                                
        }                                                     

        chatSessionList.querySelectorAll("[data-session-id]").forEach((item) => {
            const isActive = item.getAttribute("data-session-id") === String(currentView);
            item.style.background = isActive ? "#e9f2ff" : "#fff";
            item.style.borderColor = isActive ? "var(--primary)" : "var(--border)";
        });
    };

    const renderSessionList = () => {
        chatSessionList.innerHTML = "";

        if (!sessions.length) {
            const empty = document.createElement("div");
            empty.style.padding = "10px 12px";
            empty.style.fontSize = "12px";
            empty.style.color = "#777";
            empty.innerText = "No saved chats";
            chatSessionList.appendChild(empty);
            setActiveSidebar();
            return;
        }

        sessions.forEach((session) => {
            const item = document.createElement("div");
            item.classList.add('chat-session-item', 'hover-parent');
            item.setAttribute("data-session-id", String(session.id));
            item.style.padding = "12px";
            item.style.border = "1px solid var(--border)";
            item.style.borderRadius = "10px";
            item.style.background = "#fff";
            item.style.cursor = "pointer";
            item.style.textAlign = "left";
            item.style.display = "flex";
            item.style.justifyContent = "space-between";
            item.style.alignItems = "center";
            item.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 4px; overflow: hidden; flex: 1;">
                    <strong style="font-size: 13px; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(session.title)}</strong>
                    <span style="font-size: 11px; color: #777;">${session.message_count || 0} messages • ${session.tokens_used || 0} tokens</span>
                </div>
                <button class="btn-delete-session-item btn-del-badge hover-only" title="Delete chat">✖</button>
            `;
            
            item.addEventListener("click", async (e) => {
                if (e.target.closest('.btn-delete-session-item')) {
                    if (confirm("Are you sure you want to delete this chat session?")) {
                        await fetch("/api/chat/sessions", {
                            method: "DELETE",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ session_id: session.id })
                        });
                        if (currentView === String(session.id)) {
                            loadTemporaryChat();
                        }
                        await loadSessions();
                    }
                    return;
                }
                
                currentView = String(session.id);
                localStorage.setItem("locked_active_chat_session", currentView);
                setActiveSidebar();
                currentOffset = 0;
                hasMoreMessages = true;
                await loadHistory(session.id);
            });
            chatSessionList.appendChild(item);
        });

        setActiveSidebar();
    };

    const loadHistory = async (sessionId, loadMore = false) => {
        if (isLoadingHistory || (!hasMoreMessages && loadMore)) return;
        isLoadingHistory = true;
        
        try {
            if (!loadMore) {
                const res = await fetch(`/api/chat/history?session_id=${sessionId}&limit=1000`);
                const json = await res.json();
                if (!res.ok) {
                    console.error("Failed to fetch chat history:", json.message);
                    renderMessages([]);
                    isLoadingHistory = false;
                    return;
                }
                currentSessionMessages = json.data || [];
                currentOffset = 0;
                hasMoreMessages = true;
            }
            
            const total = currentSessionMessages.length;
            if (currentOffset >= total && loadMore) {
                hasMoreMessages = false;
                isLoadingHistory = false;
                return;
            }
            
            const chunkSize = 10;
            const startIndex = Math.max(0, total - currentOffset - chunkSize);
            const endIndex = total - currentOffset;
            const chunk = currentSessionMessages.slice(startIndex, endIndex);

            if (!loadMore) {
                renderMessages(chunk);
            } else {
                prependMessages(chunk);
            }
            
            currentOffset += chunk.length;
            if (currentOffset >= total) {
                hasMoreMessages = false;
            }
        } catch (e) {
            console.error("Error in loadHistory:", e);
            if (!loadMore) renderMessages([]);
        }
        isLoadingHistory = false;
    };

    const loadTemporaryChat = () => {
        try {
            currentView = NEW_CHAT_ID;
            localStorage.setItem("locked_active_chat_session", currentView);
            currentOffset = 0;
            hasMoreMessages = false;
            currentSessionMessages = [];
            renderMessages([]);
            setActiveSidebar();
        } catch (err) {
            console.error("Error in loadTemporaryChat:", err);
        }
    };

    const createSession = async (title) => {
        try {
            const res = await fetch("/api/chat/sessions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title })
            });
            const json = await res.json();
            if (!res.ok || !json.data) {
                throw new Error(json.message || "Failed to create a new chat.");
            }
            return json.data;
        } catch (err) {
            console.error("Error in createSession:", err);
            throw err;
        }
    };

    const loadSessions = async () => {
        try {
            const res = await fetch("/api/chat/sessions");
            const json = await res.json();
            sessions = json.data || [];
            renderSessionList();
        } catch (err) {
            console.error("Error in loadSessions:", err);
        }
    };

    if (btnDeleteChatSession) {
        btnDeleteChatSession.addEventListener("click", async () => {
            try {
                if (currentView === NEW_CHAT_ID) return;
                if (confirm("Are you sure you want to delete this chat session?")) {
                    const res = await fetch("/api/chat/sessions", {
                        method: "DELETE",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ session_id: currentView })
                    });
                    if (!res.ok) throw new Error("Delete failed");
                    await loadSessions();
                    loadTemporaryChat();
                }
            } catch (err) {
                console.error("Error deleting session:", err);
                alert("Failed to delete chat session.");
            }
        });
    }

    const loadChatSettings = async () => {
        try {
            const res = await fetch("/api/settings");
            const json = await res.json();
            const apiKeys = json.data?.api_keys || {};
            
            if (!localStorage.getItem(CHAT_MODELS_KEY)) {
                chatSavedModels = {
                    gemini: apiKeys.chat_models?.gemini || "gemini-2.5-flash",
                    openai: apiKeys.chat_models?.openai || "gpt-4o-mini",
                    openrouter: apiKeys.chat_models?.openrouter || "google/gemini-2.5-pro"
                };
                localStorage.setItem(CHAT_MODELS_KEY, JSON.stringify(chatSavedModels));
            }
            
            if (!localStorage.getItem(CHAT_PROVIDER_KEY)) {
                chatSelectedProvider = apiKeys.provider || 'gemini';
                localStorage.setItem(CHAT_PROVIDER_KEY, chatSelectedProvider);
            }
        } catch (e) {
            console.error("Failed to load settings in chat.js:", e);
        }
        syncChatModelDisplay();
    };

    const buildSessionTitle = (message) => {
        const compact = message.replace(/\s+/g, " ").trim();
        if (!compact) {
            return "New Chat";
        }
        return compact.length > 40 ? `${compact.slice(0, 40)}...` : compact;
    };

    btnNewChat.addEventListener("click", () => {
        loadTemporaryChat();
        chatInput.focus();
    });

    chatTemporaryTab.addEventListener("click", () => {
        loadTemporaryChat();
    });

    chatMessages.addEventListener("scroll", async () => {
        if (chatMessages.scrollTop === 0 && hasMoreMessages && !isLoadingHistory && currentView !== NEW_CHAT_ID) {
            await loadHistory(currentView, true);
        }
    });

    const sendMessage = async () => {
        const text = chatInput.value.trim();
        if (!text) return;

        const provider = chatSelectedProvider;
        const model = (chatSavedModels[provider] || "").trim();
        if (!model) {
            appendMessage("Error: model name is required. Please select a model in AI Configuration.", "bot");
            return;
        }

        appendMessage(text, "user");
        currentOffset += 1;
        currentSessionMessages.push({role: "user", content: text});
        chatInput.value = "";
        chatInput.style.height = "45px";

        const loadingId = `loading-${Date.now()}`;
        const loadingDiv = document.createElement("div");
        loadingDiv.id = loadingId;
        loadingDiv.style.alignSelf = "flex-start";
        loadingDiv.style.padding = "12px 16px";
        loadingDiv.style.color = "#888";
        loadingDiv.innerText = "Thinking...";
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        let sessionId = currentView === NEW_CHAT_ID ? null : Number(currentView);

        try {
            if (!sessionId) {
                const newSession = await createSession(buildSessionTitle(text));
                sessionId = newSession.id;
            }

            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: sessionId,
                    message: text,
                    provider: provider,
                    model: model
                })
            });
            const json = await res.json();
            document.getElementById(loadingId)?.remove();

            if (!res.ok || !json.reply) {
                appendMessage(`Error: ${json.message || "Unable to reach the AI service."}`, "bot");
                return;
            }

            chatSavedModels[provider] = model;
            renderChatModelList();

            appendMessage(json.reply, "bot", true, true);
            currentOffset += 1;
            currentSessionMessages.push({role: "bot", content: json.reply});
            currentView = String(sessionId);
            localStorage.setItem("locked_active_chat_session", currentView);
            setActiveSidebar();
            await loadSessions();
        } catch (e) {
            document.getElementById(loadingId)?.remove();
            appendMessage(`Connection error: ${e.message}`, "bot");
        }
    };

    btnSend.addEventListener("click", sendMessage);

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    document.getElementById("btn-close-reasoning-modal")?.addEventListener("click", () => {
        document.getElementById("reasoning-modal-overlay")?.classList.add("hidden");
    });
    
    document.getElementById("reasoning-modal-overlay")?.addEventListener("click", (e) => {
        if (e.target.id === "reasoning-modal-overlay") {
            e.target.classList.add("hidden");
        }
    });

    chatInput.addEventListener("input", function() {
        this.style.height = "45px";
        this.style.height = `${this.scrollHeight}px`;
        this.style.overflowY = this.scrollHeight > 150 ? "auto" : "hidden";
    });

    Promise.all([loadChatSettings(), loadSessions()])
        .then(async () => {
            const savedSession = localStorage.getItem("locked_active_chat_session");
            if (savedSession && savedSession !== NEW_CHAT_ID && sessions.some(s => String(s.id) === savedSession)) {
                currentView = savedSession;
                setActiveSidebar();
                await loadHistory(savedSession);
            } else {
                loadTemporaryChat();
            }
        })
        .catch(() => {
            loadTemporaryChat();
        });
});
