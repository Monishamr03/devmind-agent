import streamlit as st
import os
import json
from datetime import datetime
from google import genai
from opentelemetry import trace
from arize.otel import register

tracer_provider = register(
    space_id=os.environ.get("ARIZE_SPACE_KEY"),
    api_key=os.environ.get("ARIZE_API_KEY"),
    project_name="devmind-agent",
)
tracer = trace.get_tracer(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
DATA_FILE = "devmind_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"assignments": [], "jobs": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def show_assignments():
    data = load_data()
    if not data["assignments"]:
        return "No assignments yet."
    result = ""
    for i, a in enumerate(data["assignments"], 1):
        result += f"{i}. {a['name']} — due {a['due']} [{a['status']}]\n"
    return result

def show_jobs():
    data = load_data()
    if not data["jobs"]:
        return "No job applications yet."
    result = ""
    for i, j in enumerate(data["jobs"], 1):
        result += f"{i}. {j['role']} @ {j['company']} [{j['status']}]\n"
    return result

def devmind_agent(user_input):
    with tracer.start_as_current_span("devmind-agent-response") as span:
        span.set_attribute("user.input", user_input)
        user_lower = user_input.lower()

        if "show" in user_lower and "assignment" in user_lower:
            result = "📚 Your assignments:\n" + show_assignments()
            span.set_attribute("action.taken", "show_assignments")
            return result

        if "show" in user_lower and ("job" in user_lower or "application" in user_lower):
            result = "💼 Your job applications:\n" + show_jobs()
            span.set_attribute("action.taken", "show_jobs")
            return result

        if "add assignment" in user_lower:
            prompt = f'Extract from: "{user_input}"\nReturn ONLY:\nNAME: <name>\nDUE: <date>\nSTATUS: pending'
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            lines = response.text.strip().split("\n")
            name, due = "Unknown", "Unknown"
            for line in lines:
                if line.startswith("NAME:"): name = line.replace("NAME:", "").strip()
                elif line.startswith("DUE:"): due = line.replace("DUE:", "").strip()
            data = load_data()
            data["assignments"].append({"name": name, "due": due, "status": "pending", "added": datetime.now().strftime("%Y-%m-%d")})
            save_data(data)
            span.set_attribute("action.taken", "add_assignment")
            return f"✅ Assignment saved: **{name}** due {due}"

        if "add job" in user_lower or "applied" in user_lower:
            prompt = f'Extract from: "{user_input}"\nReturn ONLY:\nCOMPANY: <company>\nROLE: <role>\nSTATUS: applied'
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            lines = response.text.strip().split("\n")
            company, role = "Unknown", "Unknown"
            for line in lines:
                if line.startswith("COMPANY:"): company = line.replace("COMPANY:", "").strip()
                elif line.startswith("ROLE:"): role = line.replace("ROLE:", "").strip()
            data = load_data()
            data["jobs"].append({"company": company, "role": role, "status": "applied", "date": datetime.now().strftime("%Y-%m-%d")})
            save_data(data)
            span.set_attribute("action.taken", "add_job")
            return f"✅ Job saved: **{role}** at {company}"

        all_data = f"Assignments:\n{show_assignments()}\nJobs:\n{show_jobs()}"
        prompt = f"""You are DevMind Agent for student developers.
{all_data}
User: {user_input}

Respond with EXACTLY these 4 sections separated by blank lines:

🧠 UNDERSTANDING: what you understood from the request

📋 MY PLAN: your step by step plan to help

✅ ANSWER: your actual response and advice

💡 NEXT STEPS: what the user should do next"""

        span.set_attribute("action.taken", "ai_response")
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        span.set_attribute("agent.response", response.text[:300])
        return response.text

def render_whitebox_response(response):
    if "🧠 UNDERSTANDING" not in response:
        st.markdown(response)
        return

    sections = {
        "🧠 UNDERSTANDING": None,
        "📋 MY PLAN": None,
        "✅ ANSWER": None,
        "💡 NEXT STEPS": None,
    }

    current_key = None
    current_content = []

    for line in response.split("\n"):
        matched = False
        for key in sections:
            if line.startswith(key):
                if current_key:
                    sections[current_key] = "\n".join(current_content).strip()
                current_key = key
                current_content = [line.replace(key + ":", "").strip()]
                matched = True
                break
        if not matched and current_key:
            current_content.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_content).strip()

    if sections["🧠 UNDERSTANDING"]:
        st.info(f"🧠 **Understanding**\n\n{sections['🧠 UNDERSTANDING']}")
    if sections["📋 MY PLAN"]:
        st.warning(f"📋 **My Plan**\n\n{sections['📋 MY PLAN']}")
    if sections["✅ ANSWER"]:
        st.success(f"✅ **Answer**\n\n{sections['✅ ANSWER']}")
    if sections["💡 NEXT STEPS"]:
        st.info(f"💡 **Next Steps**\n\n{sections['💡 NEXT STEPS']}")

# --- Streamlit UI ---
st.set_page_config(page_title="DevMind Agent", page_icon="🚀", layout="centered")
st.title("🚀 DevMind Agent")
st.caption("AI assistant for student developers — Gemini + Arize white box observability")

with st.sidebar:
    st.header("📊 Dashboard")
    st.subheader("📚 Assignments")
    st.text(show_assignments())
    st.subheader("💼 Job Applications")
    st.text(show_jobs())
    if st.button("🔄 Refresh"):
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm DevMind Agent 🤖 I help with assignments, job applications, and developer tasks. Try: **'add assignment Python scraper due Friday'** or ask me anything!"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and "🧠 UNDERSTANDING" in msg["content"]:
            render_whitebox_response(msg["content"])
        else:
            st.markdown(msg["content"])

if prompt := st.chat_input("Ask me anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("DevMind thinking..."):
            response = devmind_agent(prompt)
        render_whitebox_response(response)
        st.session_state.messages.append({"role": "assistant", "content": response})