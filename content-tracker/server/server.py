from flask import Flask, request, jsonify
import subprocess
import json
import re

app = Flask(__name__)

# Initialize visit logs
visit_logs = []

def call_inference(prompt_text, max_length=100):
    """Call the LLM inference with proper error handling"""

    command = [
        "python", "run_inference.py",
        "-p", prompt_text,
        "-m", "models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf",
        "-n", "100",
        "-t", "4",
        "-c", "2048",
        "-temp", "0.7",
    ]
    
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print("Error:", e.stderr)
        raise Exception(f"LLM inference failed: {e.stderr}")

def create_analysis_prompt(page_data):
    """Create the analysis prompt for the LLM"""
    prompt = f"""Analyze the following webpage data. Based on its URL, domain, and title, decide if it is a meaningful piece of content worth saving. You must INCLUDE: Standalone articles, in-depth blog posts, specific videos (not channel pages), tutorials, and documentation. The content should be something a person would intentionally "read" or "watch." You must EXCLUDE: Homepages or Dashboards, Feeds or Listings, search Results Pages, User Profiles or Account Pages, Transactional Pages.
Output Format:
Respond ONLY with a valid JSON object matching this schema:
{{"should_add": <boolean>, "type": <"article" | "video" | "other" | "none">, "clean_title": <string | null>, "reasoning": <string>}}


Input Data:
{json.dumps(page_data, indent=2)}

Respond only once in JSON only output.
"""
    
    return prompt

def extract_json_from_response(response_text):
    """Extract the first valid JSON object from the response text."""
    try:
        # Try to load the entire response
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Find the first JSON-like object
        match = re.search(r"\{.*?\}", response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass  # Fall through to fallback

    # Fallback if nothing could be parsed
    return {
        "should_add": False,
        "type": "none",
        "clean_title": None,
        "reasoning": "Failed to parse LLM response"
    }

def analyze_content_with_llm(page_data):
    """Analyze page content using the LLM"""
    try:
        prompt = create_analysis_prompt(page_data)
        response = call_inference(prompt, max_length=80)
        print("Raw LLM response:", response)
        
        # Extract and validate JSON response
        analysis = extract_json_from_response(response)
        
        # Validate the response structure
        required_fields = ["should_add", "type", "clean_title", "reasoning"]
        if not all(field in analysis for field in required_fields):
            raise ValueError("Invalid response structure from LLM")
        
        # Validate field types and values
        if not isinstance(analysis["should_add"], bool):
            analysis["should_add"] = False
        
        valid_types = ["article", "video", "other", "none"]
        if analysis["type"] not in valid_types:
            analysis["type"] = "none"
        
        if not analysis["should_add"]:
            analysis["type"] = "none"
            analysis["clean_title"] = None
        
        return analysis
        
    except Exception as e:
        print(f"❌ Error in LLM analysis: {e}")
        # Return a safe fallback response
        return {
            "should_add": False,
            "type": "none", 
            "clean_title": None,
            "reasoning": f"Analysis failed: {str(e)}"
        }

@app.route("/log-visit", methods=["POST"])
def log_visit():
    """Log a page visit and analyze its content"""
    try:
        data = request.json
        print("📩 Received metadata:", data)
        
        # Validate required fields
        required_fields = ["url", "domain", "title", "timestamp"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Analyze the content using LLM
        analysis = analyze_content_with_llm(data)
        
        # Add analysis results to the data
        data["analysis"] = analysis
        
        # Only save if it's meaningful content or if analysis failed (for review)
        if analysis["should_add"] or "Analysis failed" in analysis["reasoning"]:
            visit_logs.append(data)
            print(f"✅ Content saved: {analysis['reasoning']}")
        else:
            print(f"⏭️  Content skipped: {analysis['reasoning']}")
        
        return jsonify({
            "status": "processed",
            "analysis": analysis,
            "saved": analysis["should_add"],
            "total_saved": len(visit_logs)
        })
        
    except Exception as e:
        print(f"❌ Error processing visit: {e}")
        return jsonify({"error": "Failed to process visit"}), 500

@app.route("/logs", methods=["GET"])
def get_logs():
    """Get all saved logs"""
    return jsonify(visit_logs)

@app.route("/ingest-content", methods=["POST"])
def ingest_content():
    """Process arbitrary content (legacy endpoint)"""
    content = request.json.get("content")
    if not content:
        return jsonify({"error": "Content is required"}), 400
    
    try:
        # Process the content using the LLM
        response = call_inference(content, max_length=100)
        return jsonify({"status": "processed", "response": response})
    except Exception as e:
        print("❌ Error processing content:", e)
        return jsonify({"error": "Failed to process content"}), 500

@app.route("/analyze-url", methods=["POST"])
def analyze_url():
    """Analyze a single URL without saving it"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ["url", "domain", "title"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields: url, domain, title"}), 400
        
        # Add timestamp if not provided
        if "timestamp" not in data:
            import time
            data["timestamp"] = int(time.time() * 1000)
        
        # Analyze the content
        analysis = analyze_content_with_llm(data)
        
        return jsonify({
            "analysis": analysis,
            "input": data
        })
        
    except Exception as e:
        print(f"❌ Error analyzing URL: {e}")
        return jsonify({"error": "Failed to analyze URL"}), 500

@app.route("/stats", methods=["GET"])
def get_stats():
    """Get statistics about saved content"""
    total_logs = len(visit_logs)
    
    if total_logs == 0:
        return jsonify({
            "total_saved": 0,
            "by_type": {},
            "recent_saves": []
        })
    
    # Count by type
    type_counts = {}
    recent_saves = []
    
    for log in visit_logs:
        if "analysis" in log:
            content_type = log["analysis"].get("type", "unknown")
            type_counts[content_type] = type_counts.get(content_type, 0) + 1
            
            # Add to recent saves (last 10)
            if len(recent_saves) < 10:
                recent_saves.append({
                    "url": log.get("url"),
                    "title": log["analysis"].get("clean_title") or log.get("title"),
                    "type": content_type,
                    "timestamp": log.get("timestamp")
                })
    
    return jsonify({
        "total_saved": total_logs,
        "by_type": type_counts,
        "recent_saves": recent_saves
    })

if __name__ == "__main__":
    print("🚀 Starting Content Analysis Server on port 3000...")
    app.run(host="0.0.0.0", port=3000, debug=True)