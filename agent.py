from google import genai
import os

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def devmind_agent(user_input):
    print("\n🤖 DevMind Agent thinking...\n")
    prompt = f"""You are DevMind Agent for student developers.
    Always explain reasoning step by step.
    User request: {user_input}
    Respond with:
    🧠 UNDERSTANDING: what you understood
    📋 MY PLAN: step by step plan
    ✅ ANSWER: your response
    💡 NEXT STEPS: what to do next"""
    
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt)
    print("=" * 50)
    print(response.text)
    print("=" * 50)

print("Welcome to DevMind Agent! 🚀\n")
devmind_agent("I have 3 assignments due this week, help me plan")
