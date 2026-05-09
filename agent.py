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
    data["assignments"].append({
        "name": name,
        "due": due,
        "status": status,
        "added": datetime.now().strftime("%Y-%m-%d")
    })
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

def devmind_agent(user_input):
    user_lower = user_input.lower()

    # Handle commands directly without AI
    if "show" in user_lower and "assignment" in user_lower:
        return show_assignments()

    if "add assignment" in user_lower or "save assignment" in user_lower:
        history.append(f"User: {user_input}")
        context = "\n".join(history[-6:])
        prompt = f"""Extract assignment details from this request: "{user_input}"
Return ONLY this format, nothing else:
NAME: <assignment name>
DUE: <due date>
STATUS: pending"""
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt)
        lines = response.text.strip().split("\n")
        name, due, status = "Unknown", "Unknown", "pending"
        for line in lines:
            if line.startswith("NAME:"):
                name = line.replace("NAME:", "").strip()
            elif line.startswith("DUE:"):
                due = line.replace("DUE:", "").strip()
        add_assignment(name, due, status)
        return f"Got it! Added '{name}' due {due} to your list.\nType 'show assignments' to see all your assignments."

    # General questions
    history.append(f"User: {user_input}")
    context = "\n".join(history[-6:])
    assignments = show_assignments()

    prompt = f"""You are DevMind Agent for student developers.
Help with assignments, jobs, GitHub, and Google Cloud.
Always show reasoning step by step.

{assignments}

Recent conversation:
{context}

Respond with:
UNDERSTANDING: what you understood
MY PLAN: step by step plan
ANSWER: your response
NEXT STEPS: what to do next"""

    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt)
    reply = response.text
    history.append(f"Agent: {reply[:150]}")
    return reply

print("=" * 50)
print("Welcome to DevMind Agent! 🚀")
print("Commands:")
print("  'add assignment X due Y'")
print("  'show assignments'")
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