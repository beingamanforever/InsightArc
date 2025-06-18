// content-script.js
console.log("✅ Content script is running");

const url = window.location.href;
const domain = new URL(url).hostname;
const title = document.title;

const data = {
  type: "PAGE_VIEW",
  url,
  domain,
  title,
  timestamp: Date.now(),
};

// Send it to background for saving
chrome.runtime.sendMessage(data);
