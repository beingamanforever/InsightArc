// background.js

let currentTabId = null;
let startTime = null;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "PAGE_VIEW") {
    chrome.storage.local.get({ visits: [] }, (data) => {
      const visits = data.visits;
      visits.push(msg);
      chrome.storage.local.set({ visits });
      console.log("Visit logged:", msg);
    });
  }
  sendResponse({ status: "ok" });
});

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
