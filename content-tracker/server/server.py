from flask import Flask, request, jsonify
from llama_cpp import Llama
import json
import re

app = Flask(__name__)

# Init model
# llm = Llama(
#     model_path="BitNet/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf", 
#     chat_format="chatml"
# )
llm = Llama.from_pretrained(
    repo_id="ggml-org/gemma-3-1b-it-GGUF",
    filename="*Q8_0.gguf",
    n_ctx=4096,
    verbose=False
)

# Initialize visit logs
visit_logs = []

def call_inference(prompt_text):
    """Call LLaMA using llama-cpp with JSON schema"""

    try:
        response = llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that only responds in strict JSON format.",
                },
                {"role": "user", "content": prompt_text},
            ],
            response_format={
                "type": "json_object",
                "schema": {
                    "type": "object",
                    "properties": {
                        "should_add": {"type": "boolean"},
                        "type": {
                            "type": "string",
                            "enum": ["article", "blog", "video", "other", "none"]
                        },
                        "clean_title": {"type": ["string", "null"]},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["should_add", "type", "clean_title", "reasoning"]
                },
            },
            temperature=0.7,
            max_tokens=1024,
        )
        return response["choices"][0]["message"]["content"]
    
    except Exception as e:
        print(f"❌ llama-cpp inference failed: {e}")
        raise


def create_analysis_prompt(page_data):
    prompt = f"""
You are a JSON-only assistant.

Your job is to decide if a web page is meaningful standalone content like an article, blog or video.

Only say `should_add: true` if the URL clearly shows it's a specific article, post, tutorial, or video.

Reject it if it's a homepage, profile, feed, or if the URL does not clearly show specific content.

If you're not sure, reject it.

Respond only with valid JSON in this format:
{{
  "should_add": <true|false>,
  "type": <"article"|"blog"|"video"|"other"|"none">,
  "clean_title": <string|null>,
  "reasoning": <string>
}}

Here is the input:
{json.dumps(page_data, indent=2)}


"""
    return prompt.strip()

    
    return prompt.strip()
# def extract_json_from_response(response_text):
#     """Extract the first valid JSON object from the response text."""
#     try:
#         # Try to load the entire response
#         return json.loads(response_text)
#     except json.JSONDecodeError:
#         # Find the first JSON-like object
#         match = re.search(r"\{.*?\}", response_text, re.DOTALL)
#         if match:
#             try:
#                 return json.loads(match.group(0))
#             except json.JSONDecodeError:
#                 pass  # Fall through to fallback

#     # Fallback if nothing could be parsed
#     return {
#         "should_add": False,
#         "type": "none",
#         "clean_title": None,
#         "reasoning": "Failed to parse LLM response"
#     }
def extract_json_from_response(response_text):
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
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
        response = call_inference(prompt)
        print("Raw LLM response:")
        try:
            parsed = json.loads(response)
            print(json.dumps(parsed, indent=2))
        except:
            print(response)

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