console.log("✅ Background script running");

chrome.runtime.onMessage.addListener((data, sender, sendResponse) => {
  console.log("📨 Received data from content script:", data);

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
});
