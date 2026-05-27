document.addEventListener("DOMContentLoaded", () => {
    // 1. Logic chuyển đổi Tab (Memorize <-> Thinking)
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Đổi giao diện nút tab
            tabBtns.forEach(b => {
                b.classList.remove('primary');
                b.classList.add('outline');
            });
            const currentBtn = e.currentTarget;
            currentBtn.classList.remove('outline');
            currentBtn.classList.add('primary');

            // Lưu trạng thái tab hiện tại vào LocalStorage
            const targetTab = currentBtn.getAttribute('data-tab');
            localStorage.setItem('locked_active_study_tab', targetTab);

            // Ẩn/Hiện nội dung bên dưới
            document.querySelectorAll('.study-tab-content').forEach(tab => tab.style.display = 'none');
            const targetId = `tab-${targetTab}`;
            document.getElementById(targetId).style.display = 'block';

            // Show/Hide AI toggle button based on tab
            const btnToggleAi = document.getElementById('btn-toggle-ai-assistant');
            if (btnToggleAi) {
                // Show AI button only for flashcards tab (memorize)
                btnToggleAi.style.display = (targetTab === 'memorize') ? 'inline-flex' : 'none';
            }

            // Tự động load lại dữ liệu tuỳ vào tab
            if (targetTab === 'thinking') {
                loadThinkingProjects();
            } else if (targetTab === 'knowledge') {
                loadAllKnowledge();
            } else {
                const projTab = document.querySelector('.mem-subtab-btn[data-target="projects"]');
                if (projTab) {
                    projTab.click();
                } else {
                    loadStudyProjects();
                }
            }
        });
    });

    // AI Assistant Toggle Logic
    const btnToggleAi = document.getElementById('btn-toggle-ai-assistant');
    const btnCloseAi = document.getElementById('btn-close-flashcard-assistant');
    
    if (btnToggleAi) {
        btnToggleAi.addEventListener('click', () => {
            btnToggleAi.style.display = 'none';
            openDrawer('flashcard-assistant');
        });
    }

    if (btnCloseAi) {
        btnCloseAi.addEventListener('click', () => {
            closeDrawer('flashcard-assistant');
            if (btnToggleAi) btnToggleAi.style.display = 'inline-flex';
        });
    }

    // 2. Logic Mở/Đóng Drawer (Pop-up slide bên phải) chung
    function openDrawer(id) {
        document.getElementById('overlay').classList.remove('hidden');
        document.getElementById(id).classList.remove('hidden');
    }
    function closeDrawer(id) {
        document.getElementById('overlay').classList.add('hidden');
        document.getElementById(id).classList.add('hidden');
    }

    // Đóng drawer/modal khi bấm ra ngoài nền đen (Overlay)
    document.getElementById('overlay')?.addEventListener('click', (e) => {
        if (e.target.id === 'overlay') {
            ['study-project-drawer', 'thinking-project-drawer', 'thinking-item-drawer', 'flashcard-drawer', 'flashcard-assistant']
                .forEach(id => {
                    if (!document.getElementById(id).classList.contains('hidden')) {
                        closeDrawer(id);
                        if (id === 'flashcard-assistant' && btnToggleAi) {
                            btnToggleAi.style.display = 'inline-flex';
                        }
                    }
                });
        }
    });
    document.getElementById('inference-modal-overlay')?.addEventListener('click', (e) => {
        if (e.target.id === 'inference-modal-overlay') {
            e.target.classList.add('hidden');
        }
    });

    // --- PHẦN KNOWLEDGE BASE ---
    let allKnowledgeCards = [];
    async function loadAllKnowledge() {
        try {
            const res = await fetch('/api/study/thinking/all-knowledge');
            const json = await res.json();
            if (res.ok && json.data) {
                allKnowledgeCards = json.data;
                renderAllKnowledge(allKnowledgeCards);
            }
        } catch (e) {
            console.error("Error loading knowledge base:", e);
        }
    }

    function renderAllKnowledge(cards) {
        const container = document.getElementById('knowledge-base-list');
        if (!container) return;
        container.innerHTML = '';
        if (cards.length === 0) {
            container.innerHTML = '<div style="color: #777; font-style: italic;">No knowledge cards found. Add some in your Thinking Projects!</div>';
            return;
        }

        cards.forEach(card => {
            let descHtml = card.description ? (typeof marked !== 'undefined' ? marked.parse(card.description) : card.description) : '<i>No description</i>';
            const div = document.createElement('div');
            div.style.cssText = 'padding: 15px; border: 1px solid var(--border); border-radius: 8px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.05); display: flex; flex-direction: column; gap: 8px; cursor: pointer; transition: 0.2s;';
            div.onmouseover = () => div.style.borderColor = 'var(--primary)';
            div.onmouseout = () => div.style.borderColor = 'var(--border)';
            div.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <strong style="color: var(--primary); font-size: 15px; word-break: break-word;">${card.name}</strong>
                    <span style="font-size: 11px; background: #eef2f5; padding: 3px 8px; border-radius: 12px; color: #666; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">Proj: ${card.project_name || 'N/A'}</span>
                </div>
                <div class="content-md" style="font-size: 13px; color: #444; flex: 1; word-break: break-word;">${descHtml}</div>
            `;

            div.addEventListener('click', async () => {
                const thinkingBtn = document.querySelector('.tab-btn[data-tab="thinking"]');
                if (thinkingBtn) thinkingBtn.click();

                if (!allThinkingProjects || allThinkingProjects.length === 0) {
                    await loadThinkingProjects();
                }

                const p = allThinkingProjects.find(x => x.id === card.project_id);
                if (p) {
                    openThinkingWorkspace(p);
                } else {
                    alert("Project not found!");
                }
            });

            container.appendChild(div);
        });
    }

    document.getElementById('knowledge-base-search')?.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const filtered = allKnowledgeCards.filter(c =>
            (c.name && c.name.toLowerCase().includes(query)) ||
            (c.description && c.description.toLowerCase().includes(query)) ||
            (c.project_name && c.project_name.toLowerCase().includes(query))
        );
        renderAllKnowledge(filtered);
    });

    // --- PHẦN MEMORIZE ---
    let currentStudyProject = null;
    // Tạo Project Flashcard
    const btnCreateStudyProject = document.getElementById('btn-create-project');
    const btnCreateCard = document.getElementById('btn-create-card');
    const btnStudyMode = document.getElementById('btn-study-mode');
    const btnBackStudyProjects = document.getElementById('btn-back-study-projects');
    const titleMemorize = document.getElementById('memorize-title');

    // Xử lý chuyển đổi Sub-tab trong Memorize
    const memSubtabs = document.querySelectorAll('.mem-subtab-btn');
    memSubtabs.forEach(btn => {
        btn.addEventListener('click', (e) => {
            memSubtabs.forEach(b => {
                b.classList.remove('primary');
                b.classList.add('outline');
            });
            const currentBtn = e.currentTarget;
            currentBtn.classList.remove('outline');
            currentBtn.classList.add('primary');

            const target = currentBtn.getAttribute('data-target');
            currentStudyProject = null;
            selectedCardIds.clear();
            currentLabelFilter = '';
            if (document.getElementById('flashcard-label-filter')) document.getElementById('flashcard-label-filter').value = '';

            if (target === 'projects') {
                if (btnCreateStudyProject) btnCreateStudyProject.style.display = 'inline-block';
                if (btnCreateCard) btnCreateCard.style.display = 'none';
                if (btnStudyMode) btnStudyMode.style.display = 'none';
                if (document.getElementById('flashcard-controls')) document.getElementById('flashcard-controls').style.display = 'none';
                if (titleMemorize) titleMemorize.style.display = 'none';
                loadStudyProjects();
            } else {
                if (btnCreateStudyProject) btnCreateStudyProject.style.display = 'none';
                if (btnCreateCard) btnCreateCard.style.display = 'inline-block';
                if (btnStudyMode) btnStudyMode.style.display = 'inline-block';
                if (document.getElementById('flashcard-controls')) document.getElementById('flashcard-controls').style.display = 'flex';
                if (titleMemorize) titleMemorize.style.display = 'none';
                loadFlashcards(null);
            }
        });
    });

    if (btnCreateStudyProject) btnCreateStudyProject.addEventListener('click', () => openDrawer('study-project-drawer'));
    document.getElementById('btn-close-study-project')?.addEventListener('click', () => closeDrawer('study-project-drawer'));

    document.getElementById('study-project-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        await fetch('/api/study/memorize/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: formData.get('name'), description: formData.get('description') })
        });
        closeDrawer('study-project-drawer');
        e.target.reset();
        if (!currentStudyProject) loadStudyProjects();
    });

    // Tạo Card Mới
    if (btnCreateCard) btnCreateCard.addEventListener('click', () => openDrawer('flashcard-drawer'));
    document.getElementById('btn-close-flashcard-drawer')?.addEventListener('click', () => closeDrawer('flashcard-drawer'));

    document.getElementById('flashcard-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const projId = currentStudyProject ? currentStudyProject.id : null;
        await fetch('/api/study/memorize/flashcards', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: projId,
                word: formData.get('word'),
                meaning: formData.get('meaning'),
                label: formData.get('label')
            })
        });
        closeDrawer('flashcard-drawer');
        e.target.reset();
        loadFlashcards(projId);
    });

    // Nút quay lại danh sách Project
    if (btnBackStudyProjects) btnBackStudyProjects.addEventListener('click', () => {
        if (document.getElementById('memorize-subtabs')) document.getElementById('memorize-subtabs').style.display = 'flex';
        if (btnBackStudyProjects) btnBackStudyProjects.style.display = 'none';
        document.querySelector('.mem-subtab-btn[data-target="projects"]')?.click();
    });

    function openStudyProject(project) {
        currentStudyProject = project;
        selectedCardIds.clear();
        currentLabelFilter = '';
        if (document.getElementById('memorize-subtabs')) document.getElementById('memorize-subtabs').style.display = 'none';
        if (document.getElementById('flashcard-label-filter')) document.getElementById('flashcard-label-filter').value = '';
        if (document.getElementById('flashcard-controls')) document.getElementById('flashcard-controls').style.display = 'flex';
        if (btnCreateStudyProject) btnCreateStudyProject.style.display = 'none';
        if (btnCreateCard) btnCreateCard.style.display = 'inline-block';
        if (btnStudyMode) btnStudyMode.style.display = 'inline-block';
        if (btnBackStudyProjects) btnBackStudyProjects.style.display = 'inline-block';
        if (titleMemorize) {
            titleMemorize.style.display = 'block';
            titleMemorize.innerText = `Project: ${project.name}`;
        }
        loadFlashcards(project.id);
    }

    let currentFlashcards = [];
    let selectedCardIds = new Set();
    let currentLabelFilter = '';

    async function loadFlashcards(projectId) {
        try {
            const res = await fetch('/api/study/memorize/flashcards');
            const json = await res.json();

            if (projectId === null) {
                let uniqueCards = [];
                let map = new Map();
                (json.data || []).forEach(c => {
                    if (!map.has(c.id)) { map.set(c.id, c); uniqueCards.push(c); }
                });
                currentFlashcards = uniqueCards;
            } else {
                currentFlashcards = (json.data || []).filter(c => c.project_id === projectId);
            }

            renderFlashcards();
        } catch (e) { }
    }

    function renderFlashcards() {
        const container = document.getElementById('flashcard-list');
        if (!container) return;
        container.innerHTML = '';

        let visibleCards = currentFlashcards;
        if (currentLabelFilter) {
            visibleCards = currentFlashcards.filter(c => c.label && c.label.toLowerCase().includes(currentLabelFilter.toLowerCase()));
        }

        if (currentFlashcards.length === 0) {
            container.innerHTML = '<div class="empty-state" style="text-align: center; color: #777; padding: 20px;">No flashcards found. Click \"Tạo Card Mới\" to add one.</div>';
            return;
        }

        if (visibleCards.length === 0) {
            container.innerHTML = '<div class="empty-state" style="text-align: center; color: #777; padding: 20px;">No flashcards match this label.</div>';
            return;
        }

        visibleCards.forEach(c => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.style.cursor = 'pointer';

            const isChecked = selectedCardIds.has(c.id);

            div.innerHTML = `
                <div style="display: flex; align-items: center; gap: 15px; flex: 1;">
                    <input type="checkbox" class="flashcard-checkbox" data-id="${c.id}" ${isChecked ? 'checked' : ''} style="transform: scale(1.3); cursor: pointer;">
                    <div style="flex: 1;">
                        <strong style="color: var(--primary); font-size: 15px;">${c.word}</strong>
                        <div style="font-size: 13px; color: #555; margin-top: 4px;">${c.meaning}</div>
                        ${c.label ? `<div style="font-size: 11px; margin-top: 6px; display: inline-block; padding: 2px 6px; background: #e3f2fd; color: #007bff; border-radius: 4px;">#${c.label}</div>` : ''}
                    </div>
                    <button class="btn danger btn-delete-card" style="padding: 4px 10px; font-size: 12px; background: transparent; border: 1px solid #dc3545;">Delete</button>
                </div>
            `;

            div.addEventListener('click', (e) => {
                if (e.target.tagName.toLowerCase() !== 'input' && !e.target.classList.contains('btn-delete-card')) {
                    const cb = div.querySelector('.flashcard-checkbox');
                    cb.checked = !cb.checked;
                    const event = new Event('change', { bubbles: true });
                    cb.dispatchEvent(event);
                }
            });

            div.querySelector('.btn-delete-card').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Are you sure you want to delete the flashcard \"${c.word}\"?`)) {
                    await fetch('/api/study/memorize/flashcards', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: c.id }) });
                    loadFlashcards(currentStudyProject ? currentStudyProject.id : null);
                }
            });

            div.querySelector('.flashcard-checkbox').addEventListener('change', (e) => {
                if (e.target.checked) {
                    selectedCardIds.add(c.id);
                } else {
                    selectedCardIds.delete(c.id);
                }
                updateSelectAllState(visibleCards);
            });

            container.appendChild(div);
        });
        updateSelectAllState(visibleCards);
    }

    document.getElementById('flashcard-label-filter')?.addEventListener('input', (e) => {
        currentLabelFilter = e.target.value;
        renderFlashcards();
    });

    document.getElementById('flashcard-select-all')?.addEventListener('change', (e) => {
        let visibleCards = currentFlashcards;
        if (currentLabelFilter) {
            visibleCards = currentFlashcards.filter(c => c.label && c.label.toLowerCase().includes(currentLabelFilter.toLowerCase()));
        }
        if (e.target.checked) {
            visibleCards.forEach(c => selectedCardIds.add(c.id));
        } else {
            visibleCards.forEach(c => selectedCardIds.delete(c.id));
        }
        renderFlashcards();
    });

    function updateSelectAllState(visibleCards) {
        const selectAllCb = document.getElementById('flashcard-select-all');
        if (!selectAllCb || visibleCards.length === 0) return;
        const allSelected = visibleCards.every(c => selectedCardIds.has(c.id));
        selectAllCb.checked = allSelected;
    }

    // --- CHẾ ĐỘ HỌC FLASHCARD ---
    let studyCards = [];
    let currentStudyIndex = 0;
    let studyMode = 'skim'; // 'skim' or 'test'

    const studyOverlay = document.getElementById('study-session-overlay');
    const viewSetup = document.getElementById('study-setup-view');
    const viewActive = document.getElementById('study-active-view');
    const viewSummary = document.getElementById('study-summary-view');

    btnStudyMode?.addEventListener('click', () => {
        if (selectedCardIds.size === 0) {
            alert("Please select at least 1 card to start.");
            return;
        }
        studyCards = currentFlashcards.filter(c => selectedCardIds.has(c.id));
        document.getElementById('study-selected-count').innerText = studyCards.length;

        viewSetup.style.display = 'block';
        viewActive.style.display = 'none';
        viewSummary.style.display = 'none';
        studyOverlay.classList.remove('hidden');
    });

    document.getElementById('btn-close-study-session')?.addEventListener('click', () => {
        studyOverlay.classList.add('hidden');
    });

    function startStudySession(mode) {
        studyMode = mode;
        currentStudyIndex = 0;

        studyCards.sort(() => Math.random() - 0.5); // Xáo trộn thẻ bài

        viewSetup.style.display = 'none';
        viewActive.style.display = 'flex';

        if (studyMode === 'skim') {
            document.getElementById('study-test-controls').style.display = 'none';
        } else {
            document.getElementById('study-test-controls').style.display = 'flex';
        }

        renderStudyCard();
    }

    document.getElementById('btn-start-skim')?.addEventListener('click', () => startStudySession('skim'));
    document.getElementById('btn-start-test')?.addEventListener('click', () => startStudySession('test'));

    function renderStudyCard() {
        if (currentStudyIndex >= studyCards.length) {
            viewActive.style.display = 'none';
            viewSummary.style.display = 'flex';
            return;
        }

        document.getElementById('study-progress').innerText = `Card ${currentStudyIndex + 1} / ${studyCards.length}`;
        const card = studyCards[currentStudyIndex];

        const elWord = document.getElementById('study-word');
        const elMeaning = document.getElementById('study-meaning');
        const flipContainer = document.getElementById('study-card-container');

        elWord.innerText = card.word;
        elMeaning.innerText = card.meaning;

        // Reset mặt thẻ về phía trước mỗi khi qua từ mới
        flipContainer.classList.remove('flipped');

        if (studyMode === 'test') {
            document.getElementById('study-test-input').value = '';
            document.getElementById('study-test-feedback').style.display = 'none';
            document.getElementById('study-test-input').disabled = false;
            document.getElementById('btn-submit-answer').disabled = false;
            document.getElementById('btn-submit-answer').style.display = 'block';
            document.getElementById('btn-submit-answer').innerText = 'Submit';
        }

        document.getElementById('btn-study-prev').disabled = (currentStudyIndex === 0);
        document.getElementById('btn-study-next').innerText = (currentStudyIndex === studyCards.length - 1 && studyMode === 'skim') ? "Finish →" : "Next →";
        if (studyMode === 'test') {
            document.getElementById('btn-study-next').style.display = 'none';
        } else {
            document.getElementById('btn-study-next').style.display = 'block';
        }
    }

    document.getElementById('study-card-container')?.addEventListener('click', () => {
        if (studyMode === 'skim') {
            document.getElementById('study-card-container').classList.toggle('flipped');
        }
    });

    // Press Space to reveal/hide the answer (instead of clicking the card).
    // Active while the study session modal is open (both "skim" and "test").
    document.addEventListener('keydown', (e) => {
        if (e.code !== 'Space') return;
        if (!studyOverlay || studyOverlay.classList.contains('hidden')) return;

        // Don't hijack Space when user is typing in an input/textarea.
        const activeEl = document.activeElement;
        const tag = activeEl ? activeEl.tagName : '';
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;

        const container = document.getElementById('study-card-container');
        if (!container) return;

        e.preventDefault();
        container.classList.toggle('flipped');
    });

    document.getElementById('btn-study-next')?.addEventListener('click', () => {
        currentStudyIndex++;
        renderStudyCard();
    });

    document.getElementById('btn-study-prev')?.addEventListener('click', () => {
        if (currentStudyIndex > 0) {
            currentStudyIndex--;
            renderStudyCard();
        }
    });

    document.getElementById('btn-submit-answer')?.addEventListener('click', async () => {
        const answer = document.getElementById('study-test-input').value.trim();
        if (!answer) {
            alert("Please enter an answer!");
            return;
        }

        const btnSubmit = document.getElementById('btn-submit-answer');
        btnSubmit.disabled = true;
        btnSubmit.innerText = "Grading...";

        const card = studyCards[currentStudyIndex];
        const evalMode = document.getElementById('ai-eval-mode')?.value || 'similarity';

        // Read provider + key from backend settings (UI no longer has a single provider selector).
        let provider = 'gemini';
        let apiKey = '';
        try {
            const settingsRes = await fetch('/api/settings');
            const settingsJson = await settingsRes.json();
            const keys = settingsJson?.data?.api_keys || {};
            provider = keys.provider || provider;
            apiKey = keys[provider] || '';
        } catch (e) {
            // Ignore; backend will handle missing/invalid API key.
        }

        let json;
        try {
            const res = await fetch('/api/study/memorize/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ground_truth: card.meaning,
                    user_answer: answer,
                    eval_mode: evalMode,
                    provider: provider,
                    api_key: apiKey
                })
            });
            json = await res.json();
            if (!res.ok) json.status = "500";

            const sim = json.similarity || 0;
            // Chuyển Hue từ 0 (Đỏ) sang 120 (Xanh lá) dựa trên mức độ Similarity
            const hue = Math.max(0, Math.min(120, Math.round(sim * 120)));

            const feedback = document.getElementById('study-test-feedback');
            feedback.style.display = 'block';
            feedback.style.backgroundColor = `hsl(${hue}, 80%, 90%)`;
            feedback.style.color = `hsl(${hue}, 80%, 25%)`;

            if (json.status && json.status.includes('500')) {
                feedback.innerHTML = `⚠️ <strong>AI Error:</strong> ${json.message || 'Language processing error. Please check the backend logic.'}`;
            } else {
                feedback.innerHTML = `🎯 <strong>Match: ${Math.round((json.similarity || 0) * 100)}%</strong><br><span style="font-weight:normal; font-size:14px; margin-top:8px; display:block;">Reference: ${card.meaning}</span>`;
            }

            document.getElementById('study-test-input').disabled = true;
            document.getElementById('study-card-container').classList.add('flipped');

            const btnNext = document.getElementById('btn-study-next');
            btnNext.style.display = 'block';
            btnNext.innerText = (currentStudyIndex === studyCards.length - 1) ? "Finish →" : "Next →";

            btnSubmit.style.display = 'none';
        } catch (e) {
            alert("Connection error: " + e.message);
            btnSubmit.disabled = false;
            btnSubmit.innerText = "Submit";
        }
    });

    document.getElementById('btn-study-finish')?.addEventListener('click', () => {
        studyOverlay.classList.add('hidden');
    });

    async function loadStudyProjects() {
        try {
            const res = await fetch(`/api/study/memorize/projects?_t=${Date.now()}`);
            const json = await res.json();
            const container = document.getElementById('flashcard-list');
            if (!container) return;
            container.innerHTML = '';
            if (json.data.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: #777; padding: 20px;">No projects yet. Create a new project to start using flashcards.</div>';
            }
            json.data.forEach(p => {
                const div = document.createElement('div');
                div.className = 'list-item';
                div.style.cursor = 'pointer';
                div.innerHTML = `
                    <div style="flex: 1;"><strong>${p.name}</strong><div style="font-size: 12px; color: #666; margin-top: 4px;">${p.description || 'No description'}</div></div>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn danger btn-delete-project" style="padding: 6px 12px; font-size: 12px; background: transparent; border: 1px solid #dc3545;">Delete</button>
                    </div>`;
                div.addEventListener('click', () => openStudyProject(p));
                div.querySelector('.btn-delete-project').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (confirm("Are you sure you want to delete this project and all flashcards inside it?")) {
                        await fetch('/api/study/memorize/projects', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id }) });
                        loadStudyProjects();
                    }
                });
                container.appendChild(div);
            });
        } catch (e) { }
    }

    // --- PHẦN THINKING ROOM ---
    // Tạo Project Problem
    const btnCreateThinkingProject = document.getElementById('btn-create-thinking-project');
    if (btnCreateThinkingProject) btnCreateThinkingProject.addEventListener('click', () => openDrawer('thinking-project-drawer'));
    document.getElementById('btn-close-thinking-project')?.addEventListener('click', () => closeDrawer('thinking-project-drawer'));

    document.getElementById('thinking-project-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        await fetch('/api/study/thinking/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: formData.get('name'), problem_statement: formData.get('problem_statement') })
        });
        closeDrawer('thinking-project-drawer');
        e.target.reset();
        loadThinkingProjects();
    });

    let currentThinkingProject = null;
    let allThinkingProjects = [];
    let currentProjectItems = []; // Lưu trữ dữ liệu cột để dùng cho nạp suy luận

    // Tự động mở rộng textarea
    const resizeTextarea = (el) => {
        el.style.height = 'auto';
        el.style.height = el.scrollHeight + 'px';
    };
    const problemTa = document.getElementById('thinking-problem-statement');
    if (problemTa) { problemTa.addEventListener('input', () => resizeTextarea(problemTa)); }

    const btnPreviewProblem = document.getElementById('btn-preview-problem');
    const previewProblem = document.getElementById('thinking-problem-preview');
    if (btnPreviewProblem) {
        btnPreviewProblem.addEventListener('click', () => {
            if (problemTa.style.display === 'none') {
                problemTa.style.display = 'block'; previewProblem.style.display = 'none'; btnPreviewProblem.innerText = 'Preview Markdown';
            } else {
                problemTa.style.display = 'none'; previewProblem.style.display = 'block';
                previewProblem.innerHTML = typeof marked !== 'undefined' ? marked.parse(problemTa.value) : problemTa.value;
                btnPreviewProblem.innerText = 'Edit Text';
            }
        });
    }

    const btnPreviewDesc = document.getElementById('btn-toggle-thinking-preview');
    const taDesc = document.getElementById('thinking-desc-input');
    const previewDesc = document.getElementById('thinking-desc-preview');
    if (btnPreviewDesc) {
        btnPreviewDesc.addEventListener('click', () => {
            if (taDesc.style.display === 'none') {
                taDesc.style.display = 'block'; previewDesc.style.display = 'none'; btnPreviewDesc.innerText = 'Preview Markdown';
            } else {
                taDesc.style.display = 'none'; previewDesc.style.display = 'block';
                previewDesc.innerHTML = typeof marked !== 'undefined' ? marked.parse(taDesc.value) : taDesc.value;
                btnPreviewDesc.innerText = 'Edit Text';
            }
        });
    }

    document.getElementById('thinking-project-search')?.addEventListener('input', (e) => { renderThinkingProjects(e.target.value); });

    function renderThinkingProjects(filter = "") {
        const list = document.getElementById('thinking-project-list');
        if (!list) return;
        list.innerHTML = "";
        const filtered = allThinkingProjects.filter(p => p.name.toLowerCase().includes(filter.toLowerCase()));
        if (filtered.length === 0) { list.innerHTML = '<div class="empty-state" style="padding: 20px; text-align: center; color: #777;">No projects found.</div>'; return; }
        filtered.forEach(p => {
            const item = document.createElement('div');
            item.className = 'list-item'; item.style.cursor = 'pointer';
            item.innerHTML = `<div style="flex: 1;"><strong>${p.name}</strong></div><div style="display: flex; gap: 8px;"><button class="btn danger btn-delete-project" style="padding: 4px 10px; font-size: 12px; background: transparent; border: 1px solid #dc3545;">Delete</button></div>`;
            item.addEventListener('click', () => openThinkingWorkspace(p));
            item.querySelector('.btn-delete-project').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm("Are you sure you want to delete this project and all data inside it?")) {
                    await fetch('/api/study/thinking/projects', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id }) });
                    loadThinkingProjects();
                }
            });
            list.appendChild(item);
        });
    }

    async function loadThinkingProjects() {
        try {
            const res = await fetch(`/api/study/thinking/projects?_t=${Date.now()}`);
            const json = await res.json();
            allThinkingProjects = json.data || [];
            const searchInput = document.getElementById('thinking-project-search');
            renderThinkingProjects(searchInput ? searchInput.value : "");
        } catch (e) { }
    }

    document.getElementById('btn-save-problem')?.addEventListener('click', async () => {
        if (!currentThinkingProject) return;
        const stmt = document.getElementById('thinking-problem-statement').value;
        await fetch('/api/study/thinking/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: currentThinkingProject, problem_statement: stmt }) });
        loadThinkingProjects(); alert('✅ Saved!');
    });

    function openThinkingWorkspace(project) {
        currentThinkingProject = project.id;
        document.getElementById('thinking-project-view').style.display = 'none';
        document.getElementById('thinking-workspace').style.display = 'block';
        const ta = document.getElementById('thinking-problem-statement'); ta.value = project.problem_statement || '';
        setTimeout(() => resizeTextarea(ta), 50);
        const btnPreviewProblem = document.getElementById('btn-preview-problem');
        const previewProblem = document.getElementById('thinking-problem-preview');
        if (ta && previewProblem && btnPreviewProblem) { ta.style.display = 'block'; previewProblem.style.display = 'none'; btnPreviewProblem.innerText = 'Preview Markdown'; }
        loadThinkingItems(project.id);
    }

    document.getElementById('btn-back-thinking-projects')?.addEventListener('click', () => { currentThinkingProject = null; document.getElementById('thinking-workspace').style.display = 'none'; document.getElementById('thinking-project-view').style.display = 'block'; loadThinkingProjects(); });

    window.loadThinkingItems = async function (projectId) {
        try {
            const res = await fetch(`/api/study/thinking/items?project_id=${projectId}&_t=${Date.now()}`);
            const json = await res.json();
            if (json.status.includes("200")) {
                currentProjectItems = [...json.data.knowledge, ...json.data.inferences, ...json.data.questions];
                currentProjectItems.sort((a, b) => a.id - b.id);
                const idToDisplay = {};
                currentProjectItems.forEach((item, index) => { item.display_id = index + 1; idToDisplay[item.id] = item.display_id; });
                const renderCol = (containerId, items, type) => {
                    const container = document.getElementById(containerId); if (!container) return; container.innerHTML = '';
                    items.forEach(item => {
                        let descHtml = '<i style="color:#aaa">No description</i>';
                        if (item.description) {
                            let words = item.description.trim().split(/\s+/);
                            let rawDesc = words.length > 500 ? words.slice(0, 500).join(' ') + '...' : item.description;
                            descHtml = typeof marked !== 'undefined' ? marked.parse(rawDesc) : rawDesc;
                        }
                        let nameHtml = typeof marked !== 'undefined' && marked.parseInline ? marked.parseInline(item.name) : item.name;
                        const mappedSourceIds = item.source_ids ? item.source_ids.split(',').map(id => idToDisplay[id.trim()]).filter(v => v).join(', ') : '';
                        const sourceBadge = mappedSourceIds ? `<div style="font-size:10px; color:#888; margin-top:4px; padding: 2px 4px; background: #eef2f5; border-radius: 4px;">[Source: ${mappedSourceIds}]</div>` : '';
                        const isGlobal = item.is_global ? 1 : 0;
                        const globalIcon = isGlobal ? '🌟' : '☆';
                        const globalTitle = isGlobal ? 'Remove from knowledge base' : 'Add to knowledge base';
                        const globalBtn = `<button class="btn-toggle-global" data-global="${isGlobal}" title="${globalTitle}" style="background: none; border: none; cursor: pointer; font-size: 16px; padding: 2px;">${globalIcon}</button>`;
                        const div = document.createElement('div');
                        div.className = 'thinking-item-card';
                        div.style.cssText = `padding: 10px; border: 1px solid var(--border); border-radius: 6px; background: #fff; cursor: pointer; display: flex; flex-direction: column; gap: 4px; transition: 0.2s; position: relative;`;
                        div.innerHTML = `<div style="display: flex; justify-content: space-between; align-items: flex-start;"><strong style="font-size: 13px; color: var(--primary); word-break: break-word; margin: 0; display: block;" class="content-md">${nameHtml} <span style="color:#999; font-size:11px; display: inline-block;">(#${item.display_id})</span></strong>${globalBtn}</div><div class="content-md" style="font-size: 12px; color: #555; word-break: break-word; margin: 0;">${descHtml}</div>${sourceBadge}`;
                        div.onmouseover = () => div.style.borderColor = 'var(--primary)';
                        div.onmouseout = () => div.style.borderColor = 'var(--border)';
                        div.addEventListener('click', (e) => {
                            if (e.target.closest('.btn-toggle-global')) {
                                e.stopPropagation();
                                const newStatus = isGlobal ? 0 : 1;
                                fetch('/api/study/thinking/global', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: item.id, type: type, is_global: newStatus }) }).then(() => loadThinkingItems(projectId));
                            } else {
                                editThinkingItem(item, type);
                            }
                        });
                        container.appendChild(div);
                    });
                };
                renderCol('col-knowledge', json.data.knowledge, 'knowledge'); renderCol('col-inference', json.data.inferences, 'inference'); renderCol('col-question', json.data.questions, 'question');
            }
        } catch (e) { console.error("Failed to load items:", e); }
    };

    window.editThinkingItem = function (item, type) {
        document.getElementById('thinking-item-id').value = item.id; document.getElementById('thinking-item-type').value = type;
        let title = type === 'knowledge' ? 'Edit Knowledge' : (type === 'question' ? 'Edit Question/Hypothesis' : 'Edit Inference');
        document.getElementById('thinking-item-title').innerText = title;
        document.querySelector('#thinking-item-form [name="name"]').value = item.name;
        document.querySelector('#thinking-item-form [name="description"]').value = item.description || '';
        const taDesc = document.getElementById('thinking-desc-input'); const previewDesc = document.getElementById('thinking-desc-preview'); const btnPreviewDesc = document.getElementById('btn-toggle-thinking-preview');
        if (taDesc && previewDesc && btnPreviewDesc) { taDesc.style.display = 'block'; previewDesc.style.display = 'none'; btnPreviewDesc.innerText = 'Preview Markdown'; }
        const btnDelete = document.getElementById('btn-delete-thinking-item'); if (btnDelete) { btnDelete.classList.remove('hidden'); btnDelete.onclick = () => window.deleteThinkingItem(item.id, type); }
        openDrawer('thinking-item-drawer');
    };

    const setupAddItemBtn = (btnId, itemType, titleText) => {
        document.getElementById(btnId)?.addEventListener('click', () => {
            document.getElementById('thinking-item-id').value = ''; document.getElementById('thinking-item-type').value = itemType; document.getElementById('thinking-item-title').innerText = titleText; document.getElementById('thinking-item-form').reset();
            const taDesc = document.getElementById('thinking-desc-input'); const previewDesc = document.getElementById('thinking-desc-preview'); const btnPreviewDesc = document.getElementById('btn-toggle-thinking-preview');
            if (taDesc && previewDesc && btnPreviewDesc) { taDesc.style.display = 'block'; previewDesc.style.display = 'none'; btnPreviewDesc.innerText = 'Preview Markdown'; }
            document.getElementById('btn-delete-thinking-item')?.classList.add('hidden'); openDrawer('thinking-item-drawer');
        });
    };
    setupAddItemBtn('btn-add-knowledge', 'knowledge', 'Add Knowledge'); setupAddItemBtn('btn-add-question', 'question', 'Add Question / Hypothesis'); setupAddItemBtn('btn-add-inference-manual', 'inference', 'Add Inference');

    window.deleteThinkingItem = async (id, type) => { if (confirm(`Are you sure you want to delete this item?`)) { await fetch('/api/study/thinking/items', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, type }) }); closeDrawer('thinking-item-drawer'); loadThinkingItems(currentThinkingProject); } };
    document.getElementById('btn-close-thinking-drawer')?.addEventListener('click', () => closeDrawer('thinking-item-drawer'));

    const inferenceModal = document.getElementById('inference-modal-overlay'); const colContainer = document.getElementById('inference-columns-container'); const btnAddCol = document.getElementById('btn-add-inference-column'); let inferenceColsCount = 0;
    document.getElementById('btn-add-inference')?.addEventListener('click', () => { inferenceModal.classList.remove('hidden'); colContainer.innerHTML = ''; colContainer.appendChild(btnAddCol); inferenceColsCount = 0; document.getElementById('inference-result-name').value = ''; document.getElementById('inference-result-desc').value = ''; });
    document.getElementById('btn-close-inference-modal')?.addEventListener('click', () => { inferenceModal.classList.add('hidden'); });
    btnAddCol?.addEventListener('click', () => {
        if (inferenceColsCount >= 5) { alert("You can add up to 5 sources."); return; }
        inferenceColsCount++; const colDiv = document.createElement('div'); colDiv.style.cssText = 'flex: 1; min-width: 250px; border: 1px solid var(--border); border-radius: 8px; padding: 15px; background: #fff; display: flex; flex-direction: column; gap: 10px;';
        let optionsHtml = '<option value="">@-- Chọn dữ liệu nguồn --</option><optgroup label="This Project Items">';
        currentProjectItems.forEach(item => { optionsHtml += `<option value="${item.id}">#${item.display_id} - ${item.name}</option>`; });
        optionsHtml += '</optgroup><optgroup label="Other Problems">';
        allThinkingProjects.forEach(p => { if (p.id !== currentThinkingProject) { optionsHtml += `<option value="prob_${p.id}">Problem: ${p.name}</option>`; } });
        optionsHtml += '</optgroup>';
        colDiv.innerHTML = `<h5 style="margin:0; display:flex; justify-content:space-between;">Nguồn ${inferenceColsCount} <button type="button" class="btn-remove-col" style="background:none; border:none; color:#dc3545; cursor:pointer; font-weight:bold;">✕</button></h5><select class="inference-source-select" style="padding: 8px; border-radius: 6px; border: 1px solid var(--border); width: 100%;">${optionsHtml}</select><div class="inference-source-preview content-md" style="flex: 1; margin-top: 10px; font-size: 13px; color: #555; overflow-y: auto; background: #fafafa; padding: 10px; border-radius: 6px; border: 1px solid var(--border); display: none;"></div>`;
        const selectEl = colDiv.querySelector('.inference-source-select'); const previewEl = colDiv.querySelector('.inference-source-preview');
        selectEl.addEventListener('change', () => {
            const selectedVal = selectEl.value; if (!selectedVal) { previewEl.style.display = 'none'; return; }
            if (selectedVal.startsWith('prob_')) {
                const p = allThinkingProjects.find(x => x.id == selectedVal.split('_')[1]);
                if (p) { previewEl.style.display = 'block'; previewEl.innerHTML = '<strong style="color: var(--primary);">' + p.name + '</strong><hr style="margin:8px 0; border:0; border-top:1px solid var(--border);">' + (p.problem_statement ? (typeof marked !== 'undefined' ? marked.parse(p.problem_statement) : p.problem_statement) : '<i>No problem statement</i>'); }
            } else {
                const item = currentProjectItems.find(i => i.id == selectedVal);
                if (item) { previewEl.style.display = 'block'; previewEl.innerHTML = '<strong style="color: var(--primary);">' + item.name + '</strong><hr style="margin:8px 0; border:0; border-top:1px solid var(--border);">' + (item.description ? (typeof marked !== 'undefined' ? marked.parse(item.description) : item.description) : '<i>No description</i>'); }
            }
        });
        colDiv.querySelector('.btn-remove-col').addEventListener('click', () => { colDiv.remove(); inferenceColsCount--; });
        colContainer.insertBefore(colDiv, btnAddCol);
    });
    document.getElementById('btn-save-inference')?.addEventListener('click', async () => {
        if (!currentThinkingProject) return;
        const name = document.getElementById('inference-result-name').value; const desc = document.getElementById('inference-result-desc').value; if (!name) { alert("Please enter a name for the inference result!"); return; }
        const sourceIds = Array.from(document.querySelectorAll('.inference-source-select')).map(s => s.value).filter(v => v).join(',');
        await fetch('/api/study/thinking/items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: currentThinkingProject, type: 'inference', name: name, description: desc, source_ids: sourceIds }) });
        inferenceModal.classList.add('hidden'); loadThinkingItems(currentThinkingProject);
    });

    document.getElementById('thinking-item-form')?.addEventListener('submit', async (e) => {
        e.preventDefault(); if (!currentThinkingProject) { alert("Please select a project first!"); return; }
        const formData = new FormData(e.target);
        const payload = { project_id: currentThinkingProject, type: formData.get('type'), name: formData.get('name'), description: formData.get('description') };
        const itemId = formData.get('id'); if (itemId) payload.id = itemId;
        await fetch('/api/study/thinking/items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        closeDrawer('thinking-item-drawer'); e.target.reset(); loadThinkingItems(currentThinkingProject);
    });

    const savedStudyTab = localStorage.getItem('locked_active_study_tab');
    const savedMainTab = localStorage.getItem('locked_active_main_tab');
    const btnToggleAiInit = document.getElementById('btn-toggle-ai-assistant');
    
    const shouldShowAiInit = (savedMainTab === 'study' || !savedMainTab) && (savedStudyTab === 'memorize' || !savedStudyTab);

    if (savedStudyTab) {
        const targetBtn = Array.from(tabBtns).find(b => b.getAttribute('data-tab') === savedStudyTab);
        if (targetBtn) {
            if (!targetBtn.classList.contains('primary')) {
                targetBtn.click();
            } else {
                if (btnToggleAiInit) {
                    btnToggleAiInit.style.display = shouldShowAiInit ? 'inline-flex' : 'none';
                }
                if (savedStudyTab === 'thinking') loadThinkingProjects();
                else if (savedStudyTab === 'knowledge') loadAllKnowledge();
                else {
                    const projTab = document.querySelector('.mem-subtab-btn[data-target="projects"]');
                    if (projTab) projTab.click(); else loadStudyProjects();
                }
            }
        } else {
            if (btnToggleAiInit) btnToggleAiInit.style.display = 'inline-flex'; // Default is memorize
            document.querySelector('.mem-subtab-btn[data-target="projects"]')?.click() || loadStudyProjects();
        }
    } else { 
        if (btnToggleAiInit) btnToggleAiInit.style.display = 'inline-flex'; // Default is memorize
        document.querySelector('.mem-subtab-btn[data-target="projects"]')?.click() || loadStudyProjects(); 
    }

    // --- Flashcards Assistant (mini chat sidebar) ---
    const assistantMessages = document.getElementById('flashcard-assistant-messages');
    const assistantInput = document.getElementById('flashcard-assistant-input');
    const assistantSend = document.getElementById('btn-flashcard-assistant-send');
    const assistantNew = document.getElementById('btn-flashcard-assistant-new');

    // --- Thinking Assistant (mini chat sidebar) ---
    const thinkingAssistantMessages = document.getElementById('thinking-assistant-messages');
    const thinkingAssistantInput = document.getElementById('thinking-assistant-input');
    const thinkingAssistantSend = document.getElementById('btn-thinking-assistant-send');
    const thinkingAssistantNew = document.getElementById('btn-thinking-assistant-new');
    const btnThinkingThink = document.getElementById('btn-thinking-think');
    
    // Generic Settings Drawer Elements (Shared)
    const btnAssistantOpenSettings = document.getElementById('btn-assistant-open-settings');
    const btnThinkingOpenSettings = document.getElementById('btn-thinking-open-settings');
    const aiSettingsDrawer = document.getElementById('ai-settings-drawer');
    const btnCloseAiSettings = document.getElementById('btn-close-ai-settings');
    const btnAiSettingsDone = document.getElementById('btn-ai-settings-done');
    const aiProviderOptions = document.querySelectorAll('.ai-provider-option');
    const aiModelListContainer = document.getElementById('ai-model-list-container');
    const aiCustomModelInput = document.getElementById('ai-custom-model-input');
    const btnAiApplyCustom = document.getElementById('btn-ai-apply-custom');
    
    const assistantCurrentProviderBadge = document.getElementById('assistant-current-provider-badge');
    const assistantCurrentModelDisplay = document.getElementById('assistant-current-model-display');
    const thinkingCurrentProviderBadge = document.getElementById('thinking-current-provider-badge');
    const thinkingCurrentModelDisplay = document.getElementById('thinking-current-model-display');

    const ASSISTANT_SESSION_KEY = 'locked_flashcard_assistant_session_id';
    const ASSISTANT_PROVIDER_KEY = 'locked_flashcard_assistant_provider';
    const ASSISTANT_MODELS_KEY = 'locked_flashcard_assistant_saved_models';

    const THINKING_SESSION_KEY = 'locked_thinking_assistant_session_id';
    const THINKING_PROVIDER_KEY = 'locked_thinking_assistant_provider';
    const THINKING_MODELS_KEY = 'locked_thinking_assistant_saved_models';
    
    const MODELS_DATA = {
        gemini: [ "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash" ],
        openai: [ "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo" ],
        openrouter: [ "google/gemini-2.5-pro", "anthropic/claude-3.5-sonnet", "deepseek/deepseek-chat", "deepseek/deepseek-r1" ]
    };

    let assistantSessionId = Number(localStorage.getItem(ASSISTANT_SESSION_KEY) || '') || null;
    let assistantSelectedProvider = localStorage.getItem(ASSISTANT_PROVIDER_KEY) || 'gemini';
    let assistantSavedModels = JSON.parse(localStorage.getItem(ASSISTANT_MODELS_KEY) || '{}');
    if (!assistantSavedModels.gemini) assistantSavedModels = { gemini: "gemini-2.5-flash", openai: "gpt-4o-mini", openrouter: "google/gemini-2.5-pro" };

    let thinkingSessionId = Number(localStorage.getItem(THINKING_SESSION_KEY) || '') || null;
    let thinkingSelectedProvider = localStorage.getItem(THINKING_PROVIDER_KEY) || 'gemini';
    let thinkingSavedModels = JSON.parse(localStorage.getItem(THINKING_MODELS_KEY) || '{}');
    if (!thinkingSavedModels.gemini) thinkingSavedModels = { gemini: "gemini-2.5-flash", openai: "gpt-4o-mini", openrouter: "google/gemini-2.5-pro" };
    
    let assistantSending = false;
    let thinkingSending = false;

    const syncAssistantModelDisplay = () => {
        const currentModel = assistantSavedModels[assistantSelectedProvider] || "Select Model...";
        if (assistantCurrentModelDisplay) assistantCurrentModelDisplay.innerText = currentModel;
        if (assistantCurrentProviderBadge) {
            assistantCurrentProviderBadge.innerText = assistantSelectedProvider.toUpperCase();
            const colors = { gemini: '#007bff', openai: '#10a37f', openrouter: '#7c3aed' };
            assistantCurrentProviderBadge.style.background = colors[assistantSelectedProvider] || 'var(--primary)';
        }
    };

    const syncThinkingModelDisplay = () => {
        const currentModel = thinkingSavedModels[thinkingSelectedProvider] || "Select Model...";
        if (thinkingCurrentModelDisplay) thinkingCurrentModelDisplay.innerText = currentModel;
        if (thinkingCurrentProviderBadge) {
            thinkingCurrentProviderBadge.innerText = thinkingSelectedProvider.toUpperCase();
            const colors = { gemini: '#007bff', openai: '#10a37f', openrouter: '#7c3aed' };
            thinkingCurrentProviderBadge.style.background = colors[thinkingSelectedProvider] || 'var(--primary)';
        }
    };

    const renderModelListForSettings = (mode) => {
        if (!aiModelListContainer) return;
        aiModelListContainer.innerHTML = "";
        const provider = (mode === 'assistant') ? assistantSelectedProvider : thinkingSelectedProvider;
        const savedModels = (mode === 'assistant') ? assistantSavedModels : thinkingSavedModels;
        const modelsKey = (mode === 'assistant') ? ASSISTANT_MODELS_KEY : THINKING_MODELS_KEY;
        const options = MODELS_DATA[provider] || [];
        
        options.forEach(model => {
            const btn = document.createElement("button");
            btn.className = "btn outline";
            btn.style.cssText = "text-align: left; padding: 10px 12px; font-size: 13px; justify-content: flex-start; border: 1px solid var(--border);";
            btn.innerText = model;
            if (savedModels[provider] === model) {
                btn.style.borderColor = "var(--primary)";
                btn.style.background = "#f0f7ff";
                btn.style.fontWeight = "bold";
            }
            btn.addEventListener("click", () => {
                if (window._ai_config_mode !== mode) return;
                savedModels[provider] = model;
                localStorage.setItem(modelsKey, JSON.stringify(savedModels));
                if (mode === 'assistant') syncAssistantModelDisplay(); else syncThinkingModelDisplay();
                renderModelListForSettings(mode);
            });
            aiModelListContainer.appendChild(btn);
        });
    };

    const updateProviderUIForMode = (mode) => {
        const selected = (mode === 'assistant') ? assistantSelectedProvider : thinkingSelectedProvider;
        aiProviderOptions.forEach(opt => {
            if (opt.dataset.provider === selected) {
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

    // Shared Settings Drawer Listeners
    if (btnAssistantOpenSettings) btnAssistantOpenSettings.addEventListener('click', () => { window._ai_config_mode = 'assistant'; updateProviderUIForMode('assistant'); renderModelListForSettings('assistant'); openDrawer('ai-settings-drawer'); });
    if (btnThinkingOpenSettings) btnThinkingOpenSettings.addEventListener('click', () => { window._ai_config_mode = 'thinking_assistant'; updateProviderUIForMode('thinking_assistant'); renderModelListForSettings('thinking_assistant'); openDrawer('ai-settings-drawer'); });
    if (btnCloseAiSettings) btnCloseAiSettings.addEventListener('click', () => closeDrawer('ai-settings-drawer'));
    if (btnAiSettingsDone) btnAiSettingsDone.addEventListener('click', () => closeDrawer('ai-settings-drawer'));

    aiProviderOptions.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = window._ai_config_mode;
            if (mode === 'assistant') { assistantSelectedProvider = btn.dataset.provider; localStorage.setItem(ASSISTANT_PROVIDER_KEY, assistantSelectedProvider); syncAssistantModelDisplay(); }
            else if (mode === 'thinking_assistant') { thinkingSelectedProvider = btn.dataset.provider; localStorage.setItem(THINKING_PROVIDER_KEY, thinkingSelectedProvider); syncThinkingModelDisplay(); }
            else return;
            updateProviderUIForMode(mode); renderModelListForSettings(mode);
        });
    });

    if (btnAiApplyCustom) btnAiApplyCustom.addEventListener('click', () => {
        const mode = window._ai_config_mode; const val = aiCustomModelInput?.value.trim(); if (!val) return;
        if (mode === 'assistant') { assistantSavedModels[assistantSelectedProvider] = val; localStorage.setItem(ASSISTANT_MODELS_KEY, JSON.stringify(assistantSavedModels)); syncAssistantModelDisplay(); }
        else if (mode === 'thinking_assistant') { thinkingSavedModels[thinkingSelectedProvider] = val; localStorage.setItem(THINKING_MODELS_KEY, JSON.stringify(thinkingSavedModels)); syncThinkingModelDisplay(); }
        renderModelListForSettings(mode);
    });

    // Chat Helpers
    const escapeHtml = (value) => String(value || '').replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll("\"", "&quot;");
    const stripThinkTag = (text) => String(text || '').replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
    const renderAssistantMessage = (text, sender) => {
        const wrapper = document.createElement('div'); wrapper.style.cssText = `display: flex; justify-content: ${sender === 'user' ? 'flex-end' : 'flex-start'};`;
        const bubble = document.createElement('div'); bubble.style.cssText = `max-width: 92%; padding: 10px 12px; border-radius: ${sender === 'user' ? '12px 12px 0 12px' : '12px 12px 12px 0'}; background: ${sender === 'user' ? 'var(--primary)' : '#f0f0f0'}; color: ${sender === 'user' ? '#fff' : 'var(--text)'}; word-break: break-word; lineHeight: 1.45;`;
        const content = document.createElement('div'); content.classList.add('content-md'); const cleaned = stripThinkTag(text);
        content.innerHTML = (typeof marked !== 'undefined') ? marked.parse(cleaned) : escapeHtml(cleaned);
        bubble.appendChild(content); wrapper.appendChild(bubble); return wrapper;
    };
    const appendAssistantMessageTo = (container, text, sender) => { if (container) { container.appendChild(renderAssistantMessage(text, sender)); container.scrollTop = container.scrollHeight; } };

    // --- Flashcards Assistant Logic ---
    const resetAssistant = async () => {
        assistantSessionId = null; localStorage.removeItem(ASSISTANT_SESSION_KEY); if (assistantMessages) assistantMessages.innerHTML = '';
        appendAssistantMessageTo(assistantMessages, "Hi! Ask me to manage your flashcards. I can create flashcards and projects for you.", 'bot');
    };
    const sendAssistantMessage = async () => {
        if (!assistantInput || !assistantMessages || assistantSending) return;
        const text = assistantInput.value.trim(); if (!text) return;
        assistantSending = true; assistantSend.disabled = true; assistantSend.textContent = '...';
        appendAssistantMessageTo(assistantMessages, text, 'user');
        assistantInput.value = ''; assistantInput.style.height = '38px';
        try {
            const provider = assistantSelectedProvider; const model = assistantSavedModels[provider];
            if (!assistantSessionId) {
                const res = await fetch('/api/chat/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: 'Flashcards Assistant' }) });
                const json = await res.json(); assistantSessionId = json.data.id; localStorage.setItem(ASSISTANT_SESSION_KEY, assistantSessionId);
            }
            const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: assistantSessionId, message: text, provider, model }) });
            const json = await res.json(); appendAssistantMessageTo(assistantMessages, json.reply, 'bot');
        } catch (e) { appendAssistantMessageTo(assistantMessages, `Error: ${e.message}`, 'bot'); }
        finally { assistantSending = false; assistantSend.disabled = false; assistantSend.textContent = 'Send'; }
    };

    // --- Thinking Assistant Logic ---
    const resetThinkingAssistant = async () => {
        thinkingSessionId = null; localStorage.removeItem(THINKING_SESSION_KEY); if (thinkingAssistantMessages) thinkingAssistantMessages.innerHTML = '';
        appendAssistantMessageTo(thinkingAssistantMessages, "Hi! I am your Thinking Assistant. I have full context of your current project. How can I help?", 'bot');
    };
    const buildProjectContext = () => {
        const problem = document.getElementById('thinking-problem-statement')?.value || "";
        let ctx = `PROJECT CONTEXT (Current Project ID: ${currentThinkingProject}):\n\nPROBLEM STATEMENT:\n${problem}\n\n`;
        const k = currentProjectItems.filter(i => i.type === 'knowledge');
        const inf = currentProjectItems.filter(i => i.type === 'inference');
        const q = currentProjectItems.filter(i => i.type === 'question');
        if (k.length) { ctx += "KNOWLEDGE:\n"; k.forEach(i => ctx += `- [ID: ${i.id}] ${i.name}: ${i.description}\n`); }
        if (inf.length) { ctx += "\nINFERENCES:\n"; inf.forEach(i => ctx += `- [ID: ${i.id}] ${i.name}: ${i.description}\n`); }
        if (q.length) { ctx += "\nQUESTIONS:\n"; q.forEach(i => ctx += `- [ID: ${i.id}] ${i.name}: ${i.description}\n`); }
        
        ctx += "\n\nINSTRUCTION: Use the provided tools (create_thinking_item, update_thinking_item) to directly record your analysis, new knowledge, or inferences into the project. Preference tool usage over just text replies when adding value to the knowledge base.";
        return ctx;
    };
    const sendThinkingAssistantMessage = async () => {
        if (!thinkingAssistantInput || !thinkingAssistantMessages || thinkingSending) return;
        const text = thinkingAssistantInput.value.trim(); if (!text) return;
        thinkingSending = true; thinkingAssistantSend.disabled = true; thinkingAssistantSend.textContent = '...';
        appendAssistantMessageTo(thinkingAssistantMessages, text, 'user');
        thinkingAssistantInput.value = ''; thinkingAssistantInput.style.height = '38px';
        try {
            const provider = thinkingSelectedProvider; const model = thinkingSavedModels[provider];
            if (!thinkingSessionId) {
                const res = await fetch('/api/chat/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: 'Thinking Assistant' }) });
                const json = await res.json(); thinkingSessionId = json.data.id; localStorage.setItem(THINKING_SESSION_KEY, thinkingSessionId);
            }
            const context = buildProjectContext();
            const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: thinkingSessionId, message: `${context}\n\nUSER: ${text}`, provider, model }) });
            const json = await res.json(); appendAssistantMessageTo(thinkingAssistantMessages, json.reply, 'bot');
        } catch (e) { appendAssistantMessageTo(thinkingAssistantMessages, `Error: ${e.message}`, 'bot'); }
        finally { thinkingSending = false; thinkingAssistantSend.disabled = false; thinkingAssistantSend.textContent = 'Send'; }
    };

    // --- Final Listeners and Initialization ---
    syncAssistantModelDisplay(); syncThinkingModelDisplay();
    if (assistantSend) {
        assistantSend.addEventListener('click', sendAssistantMessage); assistantNew?.addEventListener('click', resetAssistant);
        assistantInput?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAssistantMessage(); } });
        assistantInput?.addEventListener('input', function() { this.style.height = '38px'; this.style.height = this.scrollHeight + 'px'; this.style.overflowY = this.scrollHeight > 120 ? 'auto' : 'hidden'; });
        if (!assistantSessionId) resetAssistant();
    }
    if (thinkingAssistantSend) {
        thinkingAssistantSend.addEventListener('click', sendThinkingAssistantMessage); thinkingAssistantNew?.addEventListener('click', resetThinkingAssistant);
        thinkingAssistantInput?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendThinkingAssistantMessage(); } });
        thinkingAssistantInput?.addEventListener('input', function() { this.style.height = '38px'; this.style.height = this.scrollHeight + 'px'; this.style.overflowY = this.scrollHeight > 120 ? 'auto' : 'hidden'; });
    }
    if (btnThinkingThink) {
        btnThinkingThink.addEventListener('click', () => { if (!currentThinkingProject) { alert("Please select a project first!"); return; } btnThinkingThink.style.display = 'none'; openDrawer('thinking-assistant'); if (!thinkingSessionId) resetThinkingAssistant(); });
    }
    document.getElementById('btn-close-thinking-assistant')?.addEventListener('click', () => { closeDrawer('thinking-assistant'); if (btnThinkingThink) btnThinkingThink.style.display = 'inline-flex'; });

    // Cập nhật Overlay Click để đóng cả Thinking Assistant
    document.getElementById('overlay')?.addEventListener('click', (e) => {
        if (e.target.id === 'overlay') {
            ['study-project-drawer', 'thinking-project-drawer', 'thinking-item-drawer', 'flashcard-drawer', 'flashcard-assistant', 'thinking-assistant', 'ai-settings-drawer']
                .forEach(id => {
                    const el = document.getElementById(id);
                    if (el && !el.classList.contains('hidden')) {
                        closeDrawer(id);
                        if (id === 'flashcard-assistant' && btnToggleAi) btnToggleAi.style.display = 'inline-flex';
                        if (id === 'thinking-assistant' && btnThinkingThink) btnThinkingThink.style.display = 'inline-flex';
                    }
                });
        }
    });

    if (typeof marked !== 'undefined') {
        marked.use({ gfm: true, breaks: true });
        if (typeof markedKatex !== 'undefined') marked.use(markedKatex({ throwOnError: false }));
    }
});
