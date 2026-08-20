import re
import os
from dotenv import load_dotenv
from openai import OpenAI
from memory import add_message, get_history

load_dotenv(override=True)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1", 
    api_key=os.getenv("GROQ_API_KEY")
)

def generate_intelligent_reply(sender_id: str, user_message: str) -> str:
    """Generates dynamic sales replies and strips out internal model reasoning tags."""
    try:
        system_prompt = """
You are the official AI Sales Assistant for "Orb Digital Solutions" in Kenya.

SERVICES OFFERED:
1. KRA Individual NIL Tax Returns Filing (KSh 200)
2. KRA PIN Certificate Download / Reprint (KSh 150)
3. KRA New PIN Registration (KSh 300)

RULES FOR DATA COLLECTION:
- If customer wants a KRA PIN CERTIFICATE, ask for their: KRA PIN and iTax Password.
  Once BOTH are provided, output EXACT tag at the end: `[KRA_CERT: kra_pin | itax_password]`

- If customer wants a NIL RETURN, ask for their: Full Name, KRA PIN, and iTax Password.
  Once ALL 3 are provided, output EXACT tag at the end: `[KRA_NIL: full_name | kra_pin | itax_password]`

- Keep replies brief (1-3 sentences), professional, and WhatsApp-friendly.
"""

        add_message(sender_id, "user", user_message)

        messages_payload = [{"role": "system", "content": system_prompt}]
        messages_payload.extend(get_history(sender_id))

        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=messages_payload,
            temperature=0.2,
            max_tokens=180,
        )

        raw_reply = response.choices[0].message.content.strip()

        # Strip out <think>...</think> blocks if present
        cleaned_reply = re.sub(r'<think>.*?</think>', '', raw_reply, flags=re.DOTALL).strip()

        add_message(sender_id, "assistant", cleaned_reply)
        return cleaned_reply

    except Exception as e:
        print(f"\n--- AI GENERATION ERROR ---: {e}")
        return "Welcome to Orb Digital Solutions! How can we assist you with your KRA services today?"