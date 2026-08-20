import os
from dotenv import load_dotenv
from openai import OpenAI

from database import get_formatted_catalog
from memory import add_message, get_history

load_dotenv(override=True)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1", 
    api_key=os.getenv("GROQ_API_KEY")
)


def generate_intelligent_reply(sender_id: str, user_message: str) -> str:
    """Generates a dynamic sales reply strictly focused on KRA NIL Returns Filing."""
    try:
        current_catalog = get_formatted_catalog()

        system_prompt = f"""
You are the official AI Sales Assistant for "Orb Digital Solutions" in Kenya, specializing in automated KRA Individual NIL Tax Returns Filing (KSh 200).

PRIMARY DIRECTIVE:
When a customer inquires about filing tax returns, NIL returns, or KRA compliance, welcome them to Orb Digital Solutions and collect their login details to process their return instantly.

REQUIRED INTAKE DETAILS:
Politely collect these 3 details:
1. Full Name
2. KRA PIN (e.g., A012345678Z)
3. iTax Password

TAG FINALIZATION RULE:
As soon as (and ONLY when) the customer has provided ALL 3 required details (Full Name, KRA PIN, iTax Password), confirm their information and append this EXACT tag at the very end of your response:
`[KRA_NIL: full_name | kra_pin | itax_password]`

Example response:
"Thank you! I have saved your details. Please check your phone screen to enter your M-Pesa PIN for KSh 200 to process your NIL return. [KRA_NIL: Jane Doe | A012345678Z | MyPass2026!]"

RULES:
- Always identify as "Orb Digital Solutions".
- NEVER output the `[KRA_NIL: ...]` tag until ALL 3 details are explicitly provided.
- Keep replies under 3 sentences, natural, polite, and WhatsApp-styled.
- Reassure customers that their password is only used securely for automated filing on iTax.

CURRENT SERVICE CATALOG:
{current_catalog}
"""

        add_message(sender_id, "user", user_message)

        messages_payload = [{"role": "system", "content": system_prompt}]
        messages_payload.extend(get_history(sender_id))

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages_payload,
            temperature=0.2,
            max_tokens=180,
        )

        bot_reply = response.choices[0].message.content.strip()
        add_message(sender_id, "assistant", bot_reply)

        return bot_reply

    except Exception as e:
        print("\n--- AI GENERATION ERROR ---")
        print(str(e))
        return "sorry! I had a quick glitch at Orb Digital Solutions. Try again in a few seconds, or contact us at +254 743634717 for assistance."