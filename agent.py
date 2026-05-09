from google import genai
import os

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
history = []

def devmind_agent(user_input):
    history.append(f"User: {user_input}")
    context = "\n".join(history[-6:])
    
    prompt = f"""You are DevMind Agent for student developers.
Help with assignments, jobs, GitHub, and Google Cloud.
Always show reasoning step by step.

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

print("Welcome to DevMind Agent! 🚀")
print("Type 'quit' to exit")
print("-" * 40)

while True:
    user_input = input("You: ").strip()
    if user_input.lower() in ["quit", "exit"]:
        print("Goodbye! 👋")
        break
    if not user_input:
        continue
    print(devmind_agent(user_input))
    print("-" * 40)