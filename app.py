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
    if not data["assignments"]: return "No assignments yet."
    return "\n".join([f"{i}. {a['name']} — due {a['due']} [{a['status']}]" for i, a in enumerate(data["assignments"], 1)])

def show_jobs():
    data = load_data()
    if not data["jobs"]: return "No applications yet."
    return "\n".join([f"{i}. {j['role']} @ {j['company']} [{j['status']}]" for i, j in enumerate(data["jobs"], 1)])

def devmind_agent(user_input):
    with tracer.start_as_current_span("devmind-agent-response") as span:
        span.set_attribute("user.input", user_input)
        user_lower = user_input.lower()

        if "show" in user_lower and "assignment" in user_lower:
            span.set_attribute("action.taken", "show_assignments")
            return "📚 **Your Assignments:**\n\n" + show_assignments()

        if "show" in user_lower and ("job" in user_lower or "application" in user_lower):
            span.set_attribute("action.taken", "show_jobs")
            return "💼 **Your Job Applications:**\n\n" + show_jobs()

        if "add assignment" in user_lower:
            r = client.models.generate_content(model="gemini-2.5-flash", contents=f'Extract from: "{user_input}"\nReturn ONLY:\nNAME: <name>\nDUE: <date>')
            name, due = "Unknown", "Unknown"
            for line in r.text.strip().split("\n"):
                if line.startswith("NAME:"): name = line.replace("NAME:", "").strip()
                elif line.startswith("DUE:"): due = line.replace("DUE:", "").strip()
            d = load_data()
            d["assignments"].append({"name": name, "due": due, "status": "pending", "added": datetime.now().strftime("%Y-%m-%d")})
            save_data(d)
            span.set_attribute("action.taken", "add_assignment")
            return f"✅ **Assignment saved!**\n\n**{name}** — due {due}"

        if "add job" in user_lower or "applied" in user_lower:
            r = client.models.generate_content(model="gemini-2.5-flash", contents=f'Extract from: "{user_input}"\nReturn ONLY:\nCOMPANY: <company>\nROLE: <role>')
            company, role = "Unknown", "Unknown"
            for line in r.text.strip().split("\n"):
                if line.startswith("COMPANY:"): company = line.replace("COMPANY:", "").strip()
                elif line.startswith("ROLE:"): role = line.replace("ROLE:", "").strip()
            d = load_data()
            d["jobs"].append({"company": company, "role": role, "status": "applied", "date": datetime.now().strftime("%Y-%m-%d")})
            save_data(d)
            span.set_attribute("action.taken", "add_job")
            return f"✅ **Job application saved!**\n\n**{role}** at {company}"

        all_data = f"Assignments:\n{show_assignments()}\nJobs:\n{show_jobs()}"
        prompt = f"""You are DevMind Agent for student developers.
{all_data}
User: {user_input}

Respond with EXACTLY these 4 sections:

🧠 UNDERSTANDING: what you understood

📋 MY PLAN: step by step plan

✅ ANSWER: your response

💡 NEXT STEPS: what to do next"""
        span.set_attribute("action.taken", "ai_response")
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        span.set_attribute("agent.response", response.text[:300])
        return response.text

def render_response(response):
    if "🧠 UNDERSTANDING" not in response:
        st.markdown(f'<div class="msg-text">{response}</div>', unsafe_allow_html=True)
        return

    sections = {"🧠 UNDERSTANDING": None, "📋 MY PLAN": None, "✅ ANSWER": None, "💡 NEXT STEPS": None}
    current_key, current_content = None, []
    for line in response.split("\n"):
        matched = False
        for key in sections:
            if line.startswith(key):
                if current_key: sections[current_key] = "\n".join(current_content).strip()
                current_key, current_content = key, [line.replace(key + ":", "").strip()]
                matched = True
                break
        if not matched and current_key:
            current_content.append(line)
    if current_key: sections[current_key] = "\n".join(current_content).strip()

    cards = [
        ("🧠 UNDERSTANDING", sections["🧠 UNDERSTANDING"], "#6366f1", "#6366f122"),
        ("📋 MY PLAN", sections["📋 MY PLAN"], "#f59e0b", "#f59e0b22"),
        ("✅ ANSWER", sections["✅ ANSWER"], "#10b981", "#10b98122"),
        ("💡 NEXT STEPS", sections["💡 NEXT STEPS"], "#ec4899", "#ec489922"),
    ]
    for label, content, color, bg in cards:
        if content:
            st.markdown(f"""
<div style="background:{bg};border:1px solid {color}44;border-left:3px solid {color};
border-radius:12px;padding:16px 20px;margin:10px 0;backdrop-filter:blur(10px);">
<div style="color:{color};font-size:11px;font-weight:700;letter-spacing:1.5px;margin-bottom:8px;text-transform:uppercase;">{label}</div>
<div style="color:#e2e8f0;font-size:14px;line-height:1.8;white-space:pre-wrap;">{content}</div>
</div>""", unsafe_allow_html=True)

# ─── PAGE CONFIG ───
st.set_page_config(page_title="DevMind Agent", page_icon="🧠", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
* { font-family: 'Inter', sans-serif !important; }

.stApp {
    background: radial-gradient(ellipse at top left, #1e1b4b 0%, #0f0e17 40%, #0d1117 100%) !important;
}

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: rgba(15,14,23,0.8) !important;
    border-right: 1px solid rgba(99,102,241,0.2) !important;
    backdrop-filter: blur(20px) !important;
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stMetric { background: rgba(99,102,241,0.1); border-radius: 10px; padding: 8px; border: 1px solid rgba(99,102,241,0.2); }

/* Chat messages */
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 16px !important;
    padding: 8px 16px !important;
    margin: 12px 0 !important;
    backdrop-filter: blur(10px) !important;
}

/* Chat input */
[data-testid="stChatInput"] {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(99,102,241,0.4) !important;
    border-radius: 16px !important;
}
[data-testid="stChatInput"] textarea {
    color: #e2e8f0 !important;
    background: transparent !important;
    font-size: 15px !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 8px 16px !important;
    transition: all 0.2s !important;
    width: 100% !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(99,102,241,0.5) !important;
}

/* All text */
p, li, span, label, div { color: #cbd5e1 !important; }
h1, h2, h3 { color: #f1f5f9 !important; }
.stMarkdown p { color: #cbd5e1 !important; line-height: 1.7 !important; }

/* Metric */
[data-testid="stMetricValue"] { color: #a78bfa !important; font-size: 1.8rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 12px !important; }

/* Spinner */
.stSpinner > div { border-top-color: #6366f1 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #6366f1; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ─── HEADER ───
st.markdown("""
<div style="text-align:center;padding:48px 0 32px;position:relative;">
  <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);
  width:300px;height:200px;background:radial-gradient(circle,rgba(99,102,241,0.15) 0%,transparent 70%);
  pointer-events:none;"></div>

  <div style="display:inline-flex;align-items:center;gap:8px;
  background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);
  border-radius:20px;padding:6px 16px;margin-bottom:20px;">
    <div style="width:8px;height:8px;background:#10b981;border-radius:50%;animation:pulse 2s infinite;"></div>
    <span style="color:#a78bfa;font-size:12px;font-weight:600;letter-spacing:1px;">POWERED BY GEMINI + ARIZE</span>
  </div>

  <h1 style="font-size:3.2rem;font-weight:800;margin:0;
  background:linear-gradient(135deg,#e0e7ff,#a78bfa,#6366f1);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  letter-spacing:-1px;line-height:1.1;">
    DevMind Agent
  </h1>
  <p style="color:#64748b;font-size:1rem;margin-top:12px;font-weight:400;">
    AI assistant for student developers · White-box reasoning · Real-time observability
  </p>
</div>
""", unsafe_allow_html=True)

# ─── SIDEBAR ───
with st.sidebar:
    st.markdown("""
    <div style="padding:20px 8px 8px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px;">
        <div style="width:36px;height:36px;background:linear-gradient(135deg,#6366f1,#8b5cf6);
        border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;">🧠</div>
        <div>
          <div style="color:#f1f5f9;font-weight:700;font-size:15px;">DevMind</div>
          <div style="color:#64748b;font-size:11px;">Command Center</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    data = load_data()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📚 Tasks", len(data["assignments"]))
    with col2:
        st.metric("💼 Jobs", len(data["jobs"]))

    st.markdown('<div style="margin:16px 0 8px;color:#64748b;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;">Assignments</div>', unsafe_allow_html=True)
    assignments_text = show_assignments()
    for line in assignments_text.strip().split("\n"):
        if line and line != "No assignments yet.":
            st.markdown(f"""<div style="background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.2);
            border-radius:8px;padding:10px 12px;margin:4px 0;font-size:13px;color:#c7d2fe;">
            {line}</div>""", unsafe_allow_html=True)
        elif line == "No assignments yet.":
            st.markdown(f'<div style="color:#475569;font-size:13px;padding:4px 0;">{line}</div>', unsafe_allow_html=True)

    st.markdown('<div style="margin:16px 0 8px;color:#64748b;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;">Job Applications</div>', unsafe_allow_html=True)
    jobs_text = show_jobs()
    for line in jobs_text.strip().split("\n"):
        if line and line != "No applications yet.":
            st.markdown(f"""<div style="background:rgba(236,72,153,0.1);border:1px solid rgba(236,72,153,0.2);
            border-radius:8px;padding:10px 12px;margin:4px 0;font-size:13px;color:#f9a8d4;">
            {line}</div>""", unsafe_allow_html=True)
        elif line == "No applications yet.":
            st.markdown(f'<div style="color:#475569;font-size:13px;padding:4px 0;">{line}</div>', unsafe_allow_html=True)

    st.markdown('<div style="margin:20px 0 8px;color:#64748b;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;">Quick Commands</div>', unsafe_allow_html=True)
    commands = ["add assignment X due Y", "show assignments", "add job Google SWE applied", "show jobs", "help me plan my week", "prepare for interview"]
    for cmd in commands:
        st.markdown(f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:6px 10px;margin:3px 0;font-size:12px;color:#64748b;font-family:monospace;">/{cmd}</div>', unsafe_allow_html=True)

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    if st.button("⟳  Refresh Dashboard"):
        st.rerun()

# ─── CHAT ───
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "intro"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["content"] == "intro":
            st.markdown("""
<div style="padding:4px 0;">
  <p style="font-size:15px;color:#e2e8f0;margin:0 0 16px;">
    👋 Hey! I'm <strong style="color:#a78bfa;">DevMind Agent</strong> — your AI-powered student developer companion.
  </p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px;">
    <div style="background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.2);border-radius:10px;padding:12px;">
      <div style="font-size:18px;margin-bottom:4px;">📚</div>
      <div style="color:#c7d2fe;font-weight:600;font-size:13px;">Track Assignments</div>
      <div style="color:#64748b;font-size:12px;">Never miss a deadline</div>
    </div>
    <div style="background:rgba(236,72,153,0.1);border:1px solid rgba(236,72,153,0.2);border-radius:10px;padding:12px;">
      <div style="font-size:18px;margin-bottom:4px;">💼</div>
      <div style="color:#f9a8d4;font-weight:600;font-size:13px;">Job Applications</div>
      <div style="color:#64748b;font-size:12px;">Track your career journey</div>
    </div>
    <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.2);border-radius:10px;padding:12px;">
      <div style="font-size:18px;margin-bottom:4px;">🧑‍💻</div>
      <div style="color:#fde68a;font-weight:600;font-size:13px;">Interview Prep</div>
      <div style="color:#64748b;font-size:12px;">DSA, system design & more</div>
    </div>
    <div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.2);border-radius:10px;padding:12px;">
      <div style="font-size:18px;margin-bottom:4px;">🧠</div>
      <div style="color:#6ee7b7;font-weight:600;font-size:13px;">White Box AI</div>
      <div style="color:#64748b;font-size:12px;">See every reasoning step</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
        elif msg["role"] == "assistant" and "🧠 UNDERSTANDING" in msg["content"]:
            render_response(msg["content"])
        else:
            st.markdown(msg["content"])

if prompt := st.chat_input("Ask me anything — assignments, jobs, coding, career..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("🧠 Thinking..."):
            response = devmind_agent(prompt)
        render_response(response)
        st.session_state.messages.append({"role": "assistant", "content": response})