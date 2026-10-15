const LOCKED_API_URL = "http://127.0.0.1:8765/api/blocker/rules";
const LOCKED_BLOCKED_PAGE = "http://127.0.0.1:8765/blocked";

// In-memory cache of active rules
let cachedRules = [];

async function syncRules() {
    try {
        const response = await fetch(LOCKED_API_URL, { cache: "no-store" });
        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }
        const data = await response.json();
        const activeRules = data.data || [];
        cachedRules = activeRules;

        await chrome.storage.local.set({
            activeRules: activeRules,
            lastSync: Date.now(),
            isConnected: true
        });

        await updateDeclarativeRules(activeRules);
    } catch (err) {
        console.warn("[Locked Blocker] Could not fetch rules from app backend:", err.message);
        // Fallback to locally cached rules
        const stored = await chrome.storage.local.get("activeRules");
        if (stored && stored.activeRules) {
            const now = Math.floor(Date.now() / 1000);
            // Filter out any locally expired rules
            cachedRules = stored.activeRules.filter(r => r.blocked_until > now);
            await updateDeclarativeRules(cachedRules);
        }
        await chrome.storage.local.set({ isConnected: false });
    }
}

async function updateDeclarativeRules(rules) {
    if (!chrome.declarativeNetRequest) return;

    try {
        const existingRules = await chrome.declarativeNetRequest.getDynamicRules();
        const removeRuleIds = existingRules.map(r => r.id);

        const now = Math.floor(Date.now() / 1000);
        const addRules = [];

        rules.forEach((rule, idx) => {
            if (rule.blocked_until <= now) return;

            const ruleId = idx + 1;
            const redirectUrl = `${LOCKED_BLOCKED_PAGE}?target=${encodeURIComponent(rule.url_pattern)}`;

            let urlFilter = "";
            if (rule.match_type === "domain") {
                urlFilter = `||${rule.domain}`;
            } else {
                urlFilter = `*${rule.url_pattern}*`;
            }

            addRules.push({
                id: ruleId,
                priority: 1,
                action: {
                    type: "redirect",
                    redirect: { url: redirectUrl }
                },
                condition: {
                    urlFilter: urlFilter,
                    resourceTypes: ["main_frame"]
                }
            });
        });

        await chrome.declarativeNetRequest.updateDynamicRules({
            removeRuleIds: removeRuleIds,
            addRules: addRules
        });
    } catch (e) {
        console.error("[Locked Blocker] Failed to update declarativeNetRequest rules:", e);
    }
}

function checkUrlMatchesRule(url, rule) {
    if (!url) return false;
    try {
        const parsed = new URL(url);
        let domain = parsed.hostname.toLowerCase();
        if (domain.startsWith("www.")) domain = domain.substring(4);

        if (rule.match_type === "domain") {
            return domain === rule.domain || domain.endsWith("." + rule.domain);
        } else {
            const fullWithoutScheme = (parsed.hostname + parsed.pathname + parsed.search).toLowerCase();
            return fullWithoutScheme.includes(rule.url_pattern.toLowerCase());
        }
    } catch (e) {
        return false;
    }
}

// Fallback listener for SPA transitions and tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    const url = changeInfo.url || tab.url;
    if (!url) return;

    // Do not block local Locked app
    if (url.startsWith("http://127.0.0.1:8765") || url.startsWith("http://localhost:8765")) {
        return;
    }

    const now = Math.floor(Date.now() / 1000);
    for (const rule of cachedRules) {
        if (rule.blocked_until > now && checkUrlMatchesRule(url, rule)) {
            const redirectUrl = `${LOCKED_BLOCKED_PAGE}?target=${encodeURIComponent(url)}`;
            chrome.tabs.update(tabId, { url: redirectUrl });
            break;
        }
    }
});

// Alarm for periodic rule syncing
chrome.alarms.create("sync_locked_rules", { periodInMinutes: 0.1 });
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "sync_locked_rules") {
        syncRules();
    }
});

// Run immediate sync on startup / install
chrome.runtime.onInstalled.addListener(() => {
    syncRules();
});

chrome.runtime.onStartup.addListener(() => {
    syncRules();
});

// Fast initial poll
syncRules();
setInterval(syncRules, 5000);

