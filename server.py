from flask import Flask, render_template, request, jsonify
import os
import json
from datetime import datetime
from google import genai
from opentelemetry import trace
from arize.otel import register

app = Flask(__name__)

register(
    space_id=os.environ.get("ARIZE_SPACE_KEY"),
    api_key=os.environ.get("ARIZE_API_KEY"),
    project_name="devmind-agent",
)
tracer = trace.get_tracer(__name__)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
DATA_FILE = "devmind_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"assignments": [], "jobs": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def get_data():
    return jsonify(load_data())

@app.route("/api/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    with tracer.start_as_current_span("devmind-agent-response") as span:
        span.set_attribute("user.input", user_input)
        user_lower = user_input.lower()
        data = load_data()

        if "show" in user_lower and "assignment" in user_lower:
            span.set_attribute("action.taken", "show_assignments")
            return jsonify({"type": "data", "content": data["assignments"], "category": "assignments"})

        if "show" in user_lower and ("job" in user_lower or "application" in user_lower):
            span.set_attribute("action.taken", "show_jobs")
            return jsonify({"type": "data", "content": data["jobs"], "category": "jobs"})

        if "add assignment" in user_lower:
            r = client.models.generate_content(model="gemini-2.5-flash",
                contents=f'Extract from: "{user_input}"\nReturn ONLY:\nNAME: <name>\nDUE: <date>')
            name, due = "Unknown", "Unknown"
            for line in r.text.strip().split("\n"):
                if line.startswith("NAME:"): name = line.replace("NAME:", "").strip()
                elif line.startswith("DUE:"): due = line.replace("DUE:", "").strip()
            data["assignments"].append({"name": name, "due": due, "status": "pending", "added": datetime.now().strftime("%Y-%m-%d")})
            save_data(data)
            span.set_attribute("action.taken", "add_assignment")
            return jsonify({"type": "saved", "content": f"Assignment saved: {name} due {due}"})

        if "add job" in user_lower or "applied" in user_lower:
            r = client.models.generate_content(model="gemini-2.5-flash",
                contents=f'Extract from: "{user_input}"\nReturn ONLY:\nCOMPANY: <company>\nROLE: <role>')
            company, role = "Unknown", "Unknown"
            for line in r.text.strip().split("\n"):
                if line.startswith("COMPANY:"): company = line.replace("COMPANY:", "").strip()
                elif line.startswith("ROLE:"): role = line.replace("ROLE:", "").strip()
            data["jobs"].append({"company": company, "role": role, "status": "applied", "date": datetime.now().strftime("%Y-%m-%d")})
            save_data(data)
            span.set_attribute("action.taken", "add_job")
            return jsonify({"type": "saved", "content": f"Job saved: {role} at {company}"})

        all_data = f"Assignments: {json.dumps(data['assignments'])}\nJobs: {json.dumps(data['jobs'])}"
        prompt = f"""You are DevMind Agent for student developers.
{all_data}
User: {user_input}

Respond with EXACTLY these 4 sections separated by blank lines:

🧠 UNDERSTANDING: what you understood

📋 MY PLAN: step by step plan

✅ ANSWER: your actual response

💡 NEXT STEPS: what to do next"""

        span.set_attribute("action.taken", "ai_response")
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        span.set_attribute("agent.response", response.text[:300])
        return jsonify({"type": "reasoning", "content": response.text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)