from google import genai
import os
import json
from datetime import datetime
from opentelemetry import trace
from arize.otel import register

# Setup Arize tracing
tracer_provider = register(
    space_id=os.environ.get("ARIZE_SPACE_KEY"),
    api_key=os.environ.get("ARIZE_API_KEY"),
    project_name="devmind-agent",
)
tracer = trace.get_tracer(__name__)

# Setup Gemini
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
history = []
DATA_FILE = "devmind_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"assignments": [], "jobs": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def add_assignment(name, due, status="pending"):
    data = load_data()
    data["assignments"].append({"name": name, "due": due, "status": status, "added": datetime.now().strftime("%Y-%m-%d")})
    save_data(data)
    print(f"\n✅ Assignment saved: {name} due {due}")

def show_assignments():
    data = load_data()
    if not data["assignments"]:
        return "No assignments saved yet."
    result = "\n📚 Your assignments:\n"
    for i, a in enumerate(data["assignments"], 1):
        result += f"{i}. {a['name']} — due {a['due']} [{a['status']}]\n"
    return result

def add_job(company, role, status="applied"):
    data = load_data()
    data["jobs"].append({"company": company, "role": role, "status": status, "date": datetime.now().strftime("%Y-%m-%d")})
    save_data(data)
    print(f"\n✅ Job saved: {role} at {company}")

def show_jobs():
    data = load_data()
    if not data["jobs"]:
        return "No job applications saved yet."
    result = "\n💼 Your job applications:\n"
    for i, j in enumerate(data["jobs"], 1):
        result += f"{i}. {j['role']} @ {j['company']} — [{j['status']}] applied {j['date']}\n"
    return result

def devmind_agent(user_input):
    with tracer.start_as_current_span("devmind-agent-response") as span:
        span.set_attribute("user.input", user_input)
        span.set_attribute("agent.name", "DevMind Agent")

        user_lower = user_input.lower()

        if "show" in user_lower and "assignment" in user_lower:
            result = show_assignments()
            span.set_attribute("action.taken", "show_assignments")
            span.set_attribute("agent.response", result)
            return result

        if "show" in user_lower and ("job" in user_lower or "application" in user_lower):
            result = show_jobs()
            span.set_attribute("action.taken", "show_jobs")
            span.set_attribute("agent.response", result)
            return result

        if "add assignment" in user_lower or "save assignment" in user_lower:
            history.append(f"User: {user_input}")
            prompt = f"""Extract assignment details from: "{user_input}"
Return ONLY:
NAME: <assignment name>
DUE: <due date>
STATUS: pending"""
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            lines = response.text.strip().split("\n")
            name, due = "Unknown", "Unknown"
            for line in lines:
                if line.startswith("NAME:"): name = line.replace("NAME:", "").strip()
                elif line.startswith("DUE:"): due = line.replace("DUE:", "").strip()
            add_assignment(name, due)
            span.set_attribute("action.taken", "add_assignment")
            span.set_attribute("assignment.name", name)
            span.set_attribute("assignment.due", due)
            result = f"Got it! Added '{name}' due {due}.\nType 'show assignments' to see all."
            span.set_attribute("agent.response", result)
            return result

        if "add job" in user_lower or "applied" in user_lower or "save job" in user_lower:
            history.append(f"User: {user_input}")
            prompt = f"""Extract job application details from: "{user_input}"
Return ONLY:
COMPANY: <company name>
ROLE: <job title or role>
STATUS: applied"""
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            lines = response.text.strip().split("\n")
            company, role = "Unknown", "Unknown"
            for line in lines:
                if line.startswith("COMPANY:"): company = line.replace("COMPANY:", "").strip()
                elif line.startswith("ROLE:"): role = line.replace("ROLE:", "").strip()
            add_job(company, role)
            span.set_attribute("action.taken", "add_job")
            span.set_attribute("job.company", company)
            span.set_attribute("job.role", role)
            result = f"Got it! Saved application for '{role}' at {company}.\nType 'show jobs' to see all."
            span.set_attribute("agent.response", result)
            return result

        history.append(f"User: {user_input}")
        context = "\n".join(history[-6:])
        all_data = f"{show_assignments()}\n{show_jobs()}"

        prompt = f"""You are DevMind Agent for student developers.
Help with assignments, jobs, GitHub, and Google Cloud.
Always show reasoning step by step.

{all_data}

Recent conversation:
{context}

Respond with:
UNDERSTANDING: what you understood
MY PLAN: step by step plan
ANSWER: your response
NEXT STEPS: what to do next"""

        span.set_attribute("action.taken", "ai_response")
        span.set_attribute("prompt.sent", prompt[:500])

        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        reply = response.text

        span.set_attribute("agent.response", reply[:500])
        span.set_attribute("reasoning.format", "UNDERSTANDING/PLAN/ANSWER/NEXT_STEPS")

        history.append(f"Agent: {reply[:150]}")
        return reply

print("=" * 50)
print("Welcome to DevMind Agent! 🚀")
print("Now with Arize observability!")
print("Commands:")
print("  'add assignment X due Y'")
print("  'show assignments'")
print("  'add job Google internship applied'")
print("  'show jobs'")
print("  Or ask anything!")
print("Type 'quit' to exit")
print("=" * 50)

while True:
    user_input = input("\nYou: ").strip()
    if user_input.lower() in ["quit", "exit"]:
        print("Goodbye! 👋")
        break
    if not user_input:
        continue
    print(devmind_agent(user_input))
    print("-" * 50)