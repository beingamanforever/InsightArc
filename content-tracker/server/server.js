const express = require("express");
const cors = require("cors");
const app = express();
const port = 3000;

let visits = [];

app.use(cors());
app.use(express.json());

// Receives visit logs from the extension
app.post("/log-visit", (req, res) => {
  const data = req.body;
  console.log("📥 Received visit:", data);
  visits.push(data);
  res.json({ success: true });
});

// See all visits in browser at http://localhost:3000/visits
app.get("/visits", (req, res) => {
  res.json(visits);
});

app.listen(port, () => {
  console.log(`🚀 Server running at http://localhost:${port}`);
});
