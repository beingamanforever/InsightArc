from flask import Flask, request, jsonify
from transformers import pipeline
import torch

app = Flask(__name__)

# Initialize visit logs
visit_logs = []

# Load the LLM pipeline for text generation
text_generation_pipeline = pipeline("text-generation", model="google/gemma-3-1b-it", device="mps", torch_dtype=torch.bfloat16)


@app.route("/log-visit", methods=["POST"])
def log_visit():
    data = request.json

    print("📩 Received metadata:", data)
    visit_logs.append(data)

    return jsonify({"status": "saved", "total": len(visit_logs)})

@app.route("/logs", methods=["GET"])
def get_logs():
    return jsonify(visit_logs)

@app.route("/ingest-content", methods=["POST"])
def ingest_content():
    content = request.json.get("content")

    if not content:
        return jsonify({"error": "Content is required"}), 400

    try:
        # Process the content using the LLM
        result = text_generation_pipeline(content, max_length=100)

        print("🤖 Processed content:", result)

        return jsonify({"status": "processed", "result": result})
    except Exception as e:
        print("❌ Error processing content:", e)
        return jsonify({"error": "Failed to process content"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
