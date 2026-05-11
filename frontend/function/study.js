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
            
            // Tự động load lại dữ liệu tuỳ vào tab
            if (targetTab === 'thinking') {
                loadThinkingProjects();
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
            ['study-project-drawer', 'thinking-project-drawer', 'thinking-item-drawer', 'flashcard-drawer']
                .forEach(id => closeDrawer(id));
        }
    });
    document.getElementById('inference-modal-overlay')?.addEventListener('click', (e) => {
        if (e.target.id === 'inference-modal-overlay') {
            e.target.classList.add('hidden');
        }
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
            if(document.getElementById('flashcard-label-filter')) document.getElementById('flashcard-label-filter').value = '';

            if (target === 'projects') {
                if(btnCreateStudyProject) btnCreateStudyProject.style.display = 'inline-block';
                if(btnCreateCard) btnCreateCard.style.display = 'none';
                if(btnStudyMode) btnStudyMode.style.display = 'none';
                if(document.getElementById('flashcard-controls')) document.getElementById('flashcard-controls').style.display = 'none';
                if(titleMemorize) titleMemorize.style.display = 'none';
                loadStudyProjects();
            } else {
                if(btnCreateStudyProject) btnCreateStudyProject.style.display = 'none';
                if(btnCreateCard) btnCreateCard.style.display = 'inline-block';
                if(btnStudyMode) btnStudyMode.style.display = 'inline-block';
                if(document.getElementById('flashcard-controls')) document.getElementById('flashcard-controls').style.display = 'flex';
                if(titleMemorize) titleMemorize.style.display = 'none';
                loadFlashcards(null);
            }
        });
    });

    if(btnCreateStudyProject) btnCreateStudyProject.addEventListener('click', () => openDrawer('study-project-drawer'));
    document.getElementById('btn-close-study-project')?.addEventListener('click', () => closeDrawer('study-project-drawer'));
    
    document.getElementById('study-project-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        await fetch('/api/study/memorize/projects', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name: formData.get('name'), description: formData.get('description') })
        });
        closeDrawer('study-project-drawer');
        e.target.reset();
        if (!currentStudyProject) loadStudyProjects();
    });

    // Tạo Card Mới
    if(btnCreateCard) btnCreateCard.addEventListener('click', () => openDrawer('flashcard-drawer'));
    document.getElementById('btn-close-flashcard-drawer')?.addEventListener('click', () => closeDrawer('flashcard-drawer'));

    document.getElementById('flashcard-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const projId = currentStudyProject ? currentStudyProject.id : null;
        await fetch('/api/study/memorize/flashcards', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
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
    if(btnBackStudyProjects) btnBackStudyProjects.addEventListener('click', () => {
        if(document.getElementById('memorize-subtabs')) document.getElementById('memorize-subtabs').style.display = 'flex';
        if(btnBackStudyProjects) btnBackStudyProjects.style.display = 'none';
        document.querySelector('.mem-subtab-btn[data-target="projects"]')?.click();
    });

    function openStudyProject(project) {
        currentStudyProject = project;
        selectedCardIds.clear();
        currentLabelFilter = '';
        if(document.getElementById('memorize-subtabs')) document.getElementById('memorize-subtabs').style.display = 'none';
        if(document.getElementById('flashcard-label-filter')) document.getElementById('flashcard-label-filter').value = '';
        if(document.getElementById('flashcard-controls')) document.getElementById('flashcard-controls').style.display = 'flex';
        if(btnCreateStudyProject) btnCreateStudyProject.style.display = 'none';
        if(btnCreateCard) btnCreateCard.style.display = 'inline-block';
        if(btnStudyMode) btnStudyMode.style.display = 'inline-block';
        if(btnBackStudyProjects) btnBackStudyProjects.style.display = 'inline-block';
        if(titleMemorize) {
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
        } catch(e) {}
    }

    function renderFlashcards() {
        const container = document.getElementById('flashcard-list');
        if(!container) return;
        container.innerHTML = '';
        
        let visibleCards = currentFlashcards;
        if (currentLabelFilter) {
            visibleCards = currentFlashcards.filter(c => c.label && c.label.toLowerCase().includes(currentLabelFilter.toLowerCase()));
        }
        
        if(currentFlashcards.length === 0) {
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
                    await fetch('/api/study/memorize/flashcards', { method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id: c.id }) });
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
        const provider = document.getElementById('ai-provider')?.value || 'gemini';
        const evalMode = document.getElementById('ai-eval-mode')?.value || 'similarity';
        const apiKey = document.getElementById('ai-api-key')?.value || '';
        
        let json;
        try {
            const res = await fetch('/api/study/memorize/check', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
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
            if(!container) return;
            container.innerHTML = '';
            if(json.data.length === 0) {
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
                        await fetch('/api/study/memorize/projects', { method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id: p.id }) });
                        loadStudyProjects();
                    }
                });
                container.appendChild(div);
            });
        } catch(e) {}
    }

    // --- PHẦN THINKING ROOM ---
    // Tạo Project Problem
    const btnCreateThinkingProject = document.getElementById('btn-create-thinking-project');
    if(btnCreateThinkingProject) btnCreateThinkingProject.addEventListener('click', () => openDrawer('thinking-project-drawer'));
    document.getElementById('btn-close-thinking-project')?.addEventListener('click', () => closeDrawer('thinking-project-drawer'));

    document.getElementById('thinking-project-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        await fetch('/api/study/thinking/projects', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
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
    if (problemTa) {
        problemTa.addEventListener('input', () => resizeTextarea(problemTa));
    }

    const btnPreviewProblem = document.getElementById('btn-preview-problem');
    const previewProblem = document.getElementById('thinking-problem-preview');
    if (btnPreviewProblem) {
        btnPreviewProblem.addEventListener('click', () => {
            if (problemTa.style.display === 'none') {
                problemTa.style.display = 'block';
                previewProblem.style.display = 'none';
                btnPreviewProblem.innerText = 'Preview Markdown';
            } else {
                problemTa.style.display = 'none';
                previewProblem.style.display = 'block';
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
                taDesc.style.display = 'block';
                previewDesc.style.display = 'none';
                btnPreviewDesc.innerText = 'Preview Markdown';
            } else {
                taDesc.style.display = 'none';
                previewDesc.style.display = 'block';
                previewDesc.innerHTML = typeof marked !== 'undefined' ? marked.parse(taDesc.value) : taDesc.value;
                btnPreviewDesc.innerText = 'Edit Text';
            }
        });
    }

    document.getElementById('thinking-project-search')?.addEventListener('input', (e) => {
        renderThinkingProjects(e.target.value);
    });

    function renderThinkingProjects(filter = "") {
        const list = document.getElementById('thinking-project-list');
        if (!list) return;
        list.innerHTML = "";
        const filtered = allThinkingProjects.filter(p => p.name.toLowerCase().includes(filter.toLowerCase()));
        
        if (filtered.length === 0) {
            list.innerHTML = '<div class="empty-state" style="padding: 20px; text-align: center; color: #777;">No projects found.</div>';
            return;
        }

        filtered.forEach(p => {
            const item = document.createElement('div');
            item.className = 'list-item';
            item.style.cursor = 'pointer';
            item.innerHTML = `
                <div style="flex: 1;"><strong>${p.name}</strong></div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn danger btn-delete-project" style="padding: 4px 10px; font-size: 12px; background: transparent; border: 1px solid #dc3545;">Delete</button>
                </div>
            `;
            
            item.addEventListener('click', () => openThinkingWorkspace(p));
            item.querySelector('.btn-delete-project').addEventListener('click', async (e) => { 
                e.stopPropagation(); 
                if (confirm("Are you sure you want to delete this project and all data inside it?")) {
                    await fetch('/api/study/thinking/projects', { method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id: p.id }) });
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
            // Giữ lại input search đang gõ
            const searchInput = document.getElementById('thinking-project-search');
            const filterVal = searchInput ? searchInput.value : "";
            renderThinkingProjects(filterVal);
        } catch(e) {}
    }

    document.getElementById('btn-save-problem')?.addEventListener('click', async () => {
        if (!currentThinkingProject) return;
        const stmt = document.getElementById('thinking-problem-statement').value;
        await fetch('/api/study/thinking/projects', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: currentThinkingProject, problem_statement: stmt })
        });
        loadThinkingProjects();
        alert('✅ Saved!');
    });

    function openThinkingWorkspace(project) {
        currentThinkingProject = project.id;
        document.getElementById('thinking-project-view').style.display = 'none';
        document.getElementById('thinking-workspace').style.display = 'block';
        
        const ta = document.getElementById('thinking-problem-statement');
        ta.value = project.problem_statement || '';
        // Đợi UI render một chút rồi trigger resize
        setTimeout(() => resizeTextarea(ta), 50);
        
        const btnPreviewProblem = document.getElementById('btn-preview-problem');
        const previewProblem = document.getElementById('thinking-problem-preview');
        if (ta && previewProblem && btnPreviewProblem) {
            ta.style.display = 'block';
            previewProblem.style.display = 'none';
            btnPreviewProblem.innerText = 'Preview Markdown';
        }
        
        loadThinkingItems(project.id);
    }

    document.getElementById('btn-back-thinking-projects')?.addEventListener('click', () => {
        currentThinkingProject = null;
        document.getElementById('thinking-workspace').style.display = 'none';
        document.getElementById('thinking-project-view').style.display = 'block';
        loadThinkingProjects();
    });

    // Tải items cho 3 cột của Thinking Workspace
    window.loadThinkingItems = async function(projectId) {
        try {
            const res = await fetch(`/api/study/thinking/items?project_id=${projectId}&_t=${Date.now()}`);
            const json = await res.json();
            if (json.status.includes("200")) {
                currentProjectItems = [...json.data.knowledge, ...json.data.inferences, ...json.data.questions];
                
                // Đánh số ID hiển thị dựa trên thứ tự tạo (ID DB gốc)
                currentProjectItems.sort((a, b) => a.id - b.id);
                const idToDisplay = {};
                currentProjectItems.forEach((item, index) => {
                    item.display_id = index + 1;
                    idToDisplay[item.id] = item.display_id;
                });
                
                const renderCol = (containerId, items, type) => {
                    const container = document.getElementById(containerId);
                    if (!container) return;
                    container.innerHTML = '';
                    items.forEach(item => {
                        let descHtml = '<i style="color:#aaa">No description</i>';
                        if (item.description) {
                            let words = item.description.trim().split(/\s+/);
                            let rawDesc = words.length > 500 ? words.slice(0, 500).join(' ') + '...' : item.description;
                            descHtml = typeof marked !== 'undefined' ? marked.parse(rawDesc) : rawDesc;
                        }
                        
                        let nameHtml = item.name;
                        if (typeof marked !== 'undefined' && marked.parseInline) {
                            nameHtml = marked.parseInline(item.name);
                        }
                        
                        const mappedSourceIds = item.source_ids ? item.source_ids.split(',').map(id => idToDisplay[id.trim()]).filter(v => v).join(', ') : '';
                        const sourceBadge = mappedSourceIds ? `<div style="font-size:10px; color:#888; margin-top:4px;">[Từ nguồn: #${mappedSourceIds}]</div>` : '';
                        const div = document.createElement('div');
                        div.style.cssText = 'padding: 10px; border: 1px solid var(--border); border-radius: 6px; background: #fff; cursor: pointer; display: flex; flex-direction: column; gap: 4px; transition: 0.2s;';
                        div.innerHTML = `
                            <strong style="font-size: 13px; color: var(--primary); word-break: break-word; margin: 0; display: block;" class="content-md">${nameHtml} <span style="color:#999; font-size:11px; display: inline-block;">(#${item.display_id})</span></strong>
                            <div class="content-md" style="font-size: 12px; color: #555; word-break: break-word; margin: 0;">${descHtml}</div>
                            ${sourceBadge}
                        `;
                        // Thêm hiệu ứng hover CSS bằng JS
                        div.onmouseover = () => div.style.borderColor = 'var(--primary)';
                        div.onmouseout = () => div.style.borderColor = 'var(--border)';
                        div.addEventListener('click', () => editThinkingItem(item, type));
                        container.appendChild(div);
                    });
                };
                renderCol('col-knowledge', json.data.knowledge, 'knowledge');
                renderCol('col-inference', json.data.inferences, 'inference');
                renderCol('col-question', json.data.questions, 'question');
            }
        } catch(e) {
            console.error("Failed to load items:", e);
        }
    };

    window.editThinkingItem = function(item, type) {
        document.getElementById('thinking-item-id').value = item.id;
        document.getElementById('thinking-item-type').value = type;
        
        let title = "Sửa mục";
        if (type === 'knowledge') title = 'Sửa Kiến Thức';
        if (type === 'question') title = 'Sửa Câu Hỏi/Giả Thuyết';
        if (type === 'inference') title = 'Sửa Suy Luận';
        
        document.getElementById('thinking-item-title').innerText = title;
        document.querySelector('#thinking-item-form [name="name"]').value = item.name;
        document.querySelector('#thinking-item-form [name="description"]').value = item.description || '';
        
        const taDesc = document.getElementById('thinking-desc-input');
        const previewDesc = document.getElementById('thinking-desc-preview');
        const btnPreviewDesc = document.getElementById('btn-toggle-thinking-preview');
        if (taDesc && previewDesc && btnPreviewDesc) {
            taDesc.style.display = 'block';
            previewDesc.style.display = 'none';
            btnPreviewDesc.innerText = 'Preview Markdown';
        }
        
        const btnDelete = document.getElementById('btn-delete-thinking-item');
        if (btnDelete) {
            btnDelete.classList.remove('hidden');
            btnDelete.onclick = () => window.deleteThinkingItem(item.id, type);
        }
        
        openDrawer('thinking-item-drawer');
    };

    // Thêm các thẻ Kiến thức / Câu hỏi vào cột
    const setupAddItemBtn = (btnId, itemType, titleText) => {
        document.getElementById(btnId)?.addEventListener('click', () => {
            document.getElementById('thinking-item-id').value = '';
            document.getElementById('thinking-item-type').value = itemType;
            document.getElementById('thinking-item-title').innerText = titleText;
            document.getElementById('thinking-item-form').reset();
            
            const taDesc = document.getElementById('thinking-desc-input');
            const previewDesc = document.getElementById('thinking-desc-preview');
            const btnPreviewDesc = document.getElementById('btn-toggle-thinking-preview');
            if (taDesc && previewDesc && btnPreviewDesc) {
                taDesc.style.display = 'block';
                previewDesc.style.display = 'none';
                btnPreviewDesc.innerText = 'Preview Markdown';
            }
            
            document.getElementById('btn-delete-thinking-item')?.classList.add('hidden');
            openDrawer('thinking-item-drawer');
        });
    };
    setupAddItemBtn('btn-add-knowledge', 'knowledge', 'Add Knowledge');
    setupAddItemBtn('btn-add-question', 'question', 'Add Question / Hypothesis');
    setupAddItemBtn('btn-add-inference-manual', 'inference', 'Add Inference');
    
    window.deleteThinkingItem = async (id, type) => {
        if (confirm(`Are you sure you want to delete this item?`)) {
            await fetch('/api/study/thinking/items', { method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id, type }) });
            closeDrawer('thinking-item-drawer');
            loadThinkingItems(currentThinkingProject);
        }
    };
    document.getElementById('btn-close-thinking-drawer')?.addEventListener('click', () => closeDrawer('thinking-item-drawer'));

    // --- LOGIC NẠP SUY LUẬN (5 CỘT MODAL) ---
    const inferenceModal = document.getElementById('inference-modal-overlay');
    const colContainer = document.getElementById('inference-columns-container');
    const btnAddCol = document.getElementById('btn-add-inference-column');
    let inferenceColsCount = 0;

    document.getElementById('btn-add-inference')?.addEventListener('click', () => {
        inferenceModal.classList.remove('hidden');
        colContainer.innerHTML = '';
        colContainer.appendChild(btnAddCol);
        inferenceColsCount = 0;
        document.getElementById('inference-result-name').value = '';
        document.getElementById('inference-result-desc').value = '';
    });

    document.getElementById('btn-close-inference-modal')?.addEventListener('click', () => {
        inferenceModal.classList.add('hidden');
    });

    btnAddCol?.addEventListener('click', () => {
        if (inferenceColsCount >= 5) {
            alert("You can add up to 5 sources.");
            return;
        }
        inferenceColsCount++;
        const colDiv = document.createElement('div');
        colDiv.style.cssText = 'min-width: 250px; border: 1px solid var(--border); border-radius: 8px; padding: 15px; background: #fff; display: flex; flex-direction: column; gap: 10px;';
        
        let optionsHtml = '<option value="">-- Chọn dữ liệu nguồn --</option>';
        currentProjectItems.forEach(item => {
            optionsHtml += `<option value="${item.id}">#${item.display_id} - ${item.name}</option>`;
        });

        colDiv.innerHTML = `
            <h5 style="margin:0; display:flex; justify-content:space-between;">Nguồn ${inferenceColsCount} <button type="button" class="btn-remove-col" style="background:none; border:none; color:#dc3545; cursor:pointer; font-weight:bold;">✕</button></h5>
            <select class="inference-source-select" style="padding: 8px; border-radius: 6px; border: 1px solid var(--border); width: 100%;">
                ${optionsHtml}
            </select>
        `;
        
        colDiv.querySelector('.btn-remove-col').addEventListener('click', () => {
            colDiv.remove();
            inferenceColsCount--;
        });
        
        colContainer.insertBefore(colDiv, btnAddCol);
    });

    document.getElementById('btn-save-inference')?.addEventListener('click', async () => {
        if (!currentThinkingProject) return;
        const name = document.getElementById('inference-result-name').value;
        const desc = document.getElementById('inference-result-desc').value;
        if (!name) { alert("Please enter a name for the inference result!"); return; }

        const selects = document.querySelectorAll('.inference-source-select');
        const sourceIds = Array.from(selects).map(s => s.value).filter(v => v).join(',');

        await fetch('/api/study/thinking/items', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ project_id: currentThinkingProject, type: 'inference', name: name, description: desc, source_ids: sourceIds }) });
        inferenceModal.classList.add('hidden');
        loadThinkingItems(currentThinkingProject);
    });

    document.getElementById('thinking-item-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!currentThinkingProject) { alert("Please select a project first!"); return; }
        const formData = new FormData(e.target);
        
        const payload = { 
            project_id: currentThinkingProject, 
            type: formData.get('type'), 
            name: formData.get('name'), 
            description: formData.get('description') 
        };
        const itemId = formData.get('id');
        if (itemId) payload.id = itemId;

        await fetch('/api/study/thinking/items', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        closeDrawer('thinking-item-drawer');
        e.target.reset();
        loadThinkingItems(currentThinkingProject);
    });

    // Khôi phục trạng thái tab study hoặc tải mặc định
    const savedStudyTab = localStorage.getItem('locked_active_study_tab');
    if (savedStudyTab) {
        const targetBtn = Array.from(tabBtns).find(b => b.getAttribute('data-tab') === savedStudyTab);
        if (targetBtn && !targetBtn.classList.contains('primary')) {
            targetBtn.click();
        } else if (targetBtn && targetBtn.classList.contains('primary')) {
            savedStudyTab === 'thinking' ? loadThinkingProjects() : (document.querySelector('.mem-subtab-btn[data-target="projects"]')?.click() || loadStudyProjects());
        }
    } else {
        document.querySelector('.mem-subtab-btn[data-target="projects"]')?.click() || loadStudyProjects();
    }
});
