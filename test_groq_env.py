import os
import requests
from dotenv import load_dotenv

# Load key from .env file
load_dotenv(override=True)

groq_key = os.getenv("GROQ_API_KEY")

if not groq_key:
    print("❌ GROQ_API_KEY is missing or empty in your .env file!")
    exit()

print(f"🔑 Found Key in .env: {groq_key[:6]}...{groq_key[-4:]}")

headers = {"Authorization": f"Bearer {groq_key.strip()}"}

# 1. Fetch available models
print("\n--- Testing API Key Authorization ---")
res = requests.get("https://api.groq.com/openai/v1/models", headers=headers)

if res.status_code != 200:
    print(f"❌ Key Authorization Failed! HTTP {res.status_code}: {res.text}")
    exit()

models = [m["id"] for m in res.json().get("data", [])]
print(f"✅ Authorization Successful! {len(models)} models available:")
for m in models:
    print(f"  - {m}")

# 2. Test completion with first model
working_model = models[0] if models else "llama-3.1-8b-instant"
print(f"\n--- Testing Chat Completion with '{working_model}' ---")

payload = {
    "model": working_model,
    "messages": [{"role": "user", "content": "Reply with 'GROQ WORKING' if successful."}],
    "max_tokens": 15
}

chat_res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)

if chat_res.status_code == 200:
    reply = chat_res.json()["choices"][0]["message"]["content"].strip()
    print(f"✅ Chat Success! Model replied: '{reply}'")
    print(f"\n👉 Set this exact model string in ai_salesman.py: '{working_model}'")
else:
    print(f"❌ Chat Completion Failed! HTTP {chat_res.status_code}: {chat_res.text}")