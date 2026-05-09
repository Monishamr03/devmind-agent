from google import genai
import os
import json
from datetime import datetime

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
    user_lower = user_input.lower()

    if "show" in user_lower and "assignment" in user_lower:
        return show_assignments()

    if "show" in user_lower and ("job" in user_lower or "application" in user_lower):
        return show_jobs()

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
        return f"Got it! Added '{name}' due {due}.\nType 'show assignments' to see all."

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
        return f"Got it! Saved application for '{role}' at {company}.\nType 'show jobs' to see all."

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

    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    reply = response.text
    history.append(f"Agent: {reply[:150]}")
    return reply

print("=" * 50)
print("Welcome to DevMind Agent! 🚀")
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