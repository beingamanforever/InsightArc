// background.js

let currentTabId = null;
let startTime = null;

fetch("http://localhost:3000/log-visit", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify(data),
})
  .then((res) => res.json())
  .then((res) => console.log("✅ Sent to server:", res))
  .catch((err) => console.error("❌ Error sending visit", err));

chrome.tabs.onActivated.addListener(({ tabId }) => {
  if (currentTabId !== null && startTime) {
    const duration = Date.now() - startTime;
    chrome.tabs.get(currentTabId, (tab) => {
      if (chrome.runtime.lastError || !tab) return;
      const domain = new URL(tab.url).hostname;
      chrome.storage.local.get({ durations: [] }, (data) => {
        const durations = data.durations;
        durations.push({
          url: tab.url,
          domain,
          duration,
          timestamp: Date.now(),
        });
        chrome.storage.local.set({ durations });
      });
    });
  }

  currentTabId = tabId;
  startTime = Date.now();
});
