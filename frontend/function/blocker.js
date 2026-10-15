document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("blocker-form");
    const inputUrl = document.getElementById("blocker-url");
    const inputDuration = document.getElementById("blocker-duration");
    const durationDisplay = document.getElementById("duration-display");
    const inputReason = document.getElementById("blocker-reason");
    const presetPills = document.querySelectorAll(".preset-pill");
    const sitePills = document.querySelectorAll(".site-preset-pill");

    // 1. Duration Preset Pill clicks
    if (presetPills.length > 0 && inputDuration) {
        presetPills.forEach(pill => {
            pill.addEventListener("click", () => {
                const mins = parseInt(pill.getAttribute("data-mins"), 10);
                if (mins) {
                    inputDuration.value = mins;
                    updateDurationDisplay(mins);
                    presetPills.forEach(p => p.classList.remove("active"));
                    pill.classList.add("active");
                }
            });
        });
    }

    if (inputDuration) {
        inputDuration.addEventListener("input", (e) => {
            const mins = parseInt(e.target.value, 10);
            updateDurationDisplay(mins);
            presetPills.forEach(p => {
                const pMins = parseInt(p.getAttribute("data-mins"), 10);
                if (pMins === mins) p.classList.add("active");
                else p.classList.remove("active");
            });
        });
    }

    function updateDurationDisplay(mins) {
        if (!durationDisplay) return;
        const h = Math.floor(mins / 60);
        const m = mins % 60;
        let text = "";
        if (h > 0) text += `${h} giờ `;
        if (m > 0 || h === 0) text += `${m} phút`;
        durationDisplay.textContent = text.trim();
    }

    // 2. Quick Distraction Site Pills
    if (sitePills.length > 0 && inputUrl) {
        sitePills.forEach(pill => {
            pill.addEventListener("click", () => {
                const target = pill.getAttribute("data-site");
                const matchType = pill.getAttribute("data-match") || "domain";
                if (target) {
                    inputUrl.value = target;
                    const radio = document.querySelector(`input[name="match_type"][value="${matchType}"]`);
                    if (radio) radio.checked = true;
                    inputUrl.focus();
                }
            });
        });
    }

    // 3. Form Submit (Hard Lock Creation)
    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const rawUrl = inputUrl.value.trim();
            if (!rawUrl) {
                if (window.showToast) window.showToast("Vui lòng nhập đường dẫn hoặc tên miền muốn chặn.", "warning");
                return;
            }

            const mins = parseInt(inputDuration.value, 10) || 60;
            if (mins <= 0 || mins > 360) {
                if (window.showToast) window.showToast("Thời gian chặn tối đa là 6 tiếng (360 phút).", "danger");
                return;
            }

            const matchTypeRadio = document.querySelector('input[name="match_type"]:checked');
            const matchType = matchTypeRadio ? matchTypeRadio.value : "domain";
            const reason = inputReason ? inputReason.value.trim() : "";

            // Confirm prompt to reinforce strict commitment
            const confirmMsg = `⚠️ BẠN ĐANG KÍCH HOẠT KHÓA CỨNG!\n\n` +
                `Quy tắc: Chặn '${rawUrl}' trong ${mins} phút.\n\n` +
                `CAM KẾT: Một khi đã bấm OK, hệ thống sẽ KHÓA TUYỆT ĐỐI và KHÔNG THỂ HỦY BỎ hay xóa trước khi hết giờ!\n\n` +
                `Bạn đã sẵn sàng tập trung chưa?`;

            if (!confirm(confirmMsg)) {
                return;
            }

            try {
                const res = await fetch("/api/blocker/rules", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        url: rawUrl,
                        duration_minutes: mins,
                        match_type: matchType,
                        reason: reason
                    })
                });

                const data = await res.json();
                if (res.status === 201) {
                    if (window.showToast) window.showToast(data.message || "Đã kích hoạt khóa cứng!", "success");
                    setTimeout(() => {
                        window.location.reload();
                    }, 800);
                } else {
                    if (window.showToast) window.showToast(data.message || "Không thể tạo quy tắc khóa", "danger");
                    else alert(data.message);
                }
            } catch (err) {
                if (window.showToast) window.showToast("Lỗi kết nối server: " + err.message, "danger");
            }
        });
    }

    // 4. Delete Handler with Hard Lock Alert
    window.handleDeleteRule = async (ruleId, isLocked) => {
        if (isLocked) {
            alert("🔒 KHÓA CỨNG ĐANG HOẠT ĐỘNG!\n\nBạn đã cam kết không xóa liên kết này khi chưa hết thời gian. Hãy giữ vững kỷ luật và tiếp tục học tập!");
            return;
        }

        if (!confirm("Bạn có chắc chắn muốn xóa quy tắc đã hết hạn này khỏi lịch sử?")) {
            return;
        }

        try {
            const res = await fetch(`/api/blocker/rules/${ruleId}`, {
                method: "DELETE"
            });
            const data = await res.json();
            if (res.status === 200) {
                if (window.showToast) window.showToast(data.message, "success");
                setTimeout(() => window.location.reload(), 500);
            } else if (res.status === 403) {
                alert("🔒 " + data.message);
            } else {
                if (window.showToast) window.showToast(data.message, "danger");
            }
        } catch (err) {
            if (window.showToast) window.showToast("Lỗi xóa: " + err.message, "danger");
        }
    };

    // 5. Dynamic Countdown Clock for All Active Cards
    function tickCountdowns() {
        const now = Math.floor(Date.now() / 1000);
        const timerEls = document.querySelectorAll("[data-blocked-until]");

        timerEls.forEach(el => {
            const until = parseInt(el.getAttribute("data-blocked-until"), 10);
            const remaining = Math.max(0, until - now);

            const hours = Math.floor(remaining / 3600);
            const minutes = Math.floor((remaining % 3600) / 60);
            const seconds = remaining % 60;

            const formatted = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
            el.textContent = formatted;

            if (remaining <= 0) {
                const card = el.closest(".lock-card");
                if (card && !card.classList.contains("expired-updated")) {
                    card.classList.add("expired-updated");
                    card.classList.remove("active-lock");
                    const badge = card.querySelector(".lock-badge.locked");
                    if (badge) {
                        badge.className = "lock-badge expired";
                        badge.textContent = "HẾT GIỜ";
                    }
                    const delBtn = card.querySelector(".btn-delete-rule");
                    if (delBtn) {
                        delBtn.removeAttribute("disabled");
                        delBtn.setAttribute("title", "Xóa lịch sử");
                        delBtn.style.opacity = "1";
                        delBtn.style.cursor = "pointer";
                    }
                }
            }
        });
    }

    // Run countdown loop
    tickCountdowns();
    setInterval(tickCountdowns, 1000);
});

