const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json());

let visitLogs = [];

app.post("/log-visit", (req, res) => {
  const data = req.body;

  console.log("📩 Received metadata:", data);
  visitLogs.push(data);

  res.json({ status: "saved", total: visitLogs.length });
});

// Optional: view all logs via browser
app.get("/logs", (req, res) => {
  res.json(visitLogs);
});

app.listen(3000, () => {
  console.log("✅ Server running at http://localhost:3000");
});
