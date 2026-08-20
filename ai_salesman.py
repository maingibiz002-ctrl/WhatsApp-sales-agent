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
    """Generates a dynamic sales reply strictly focused on KRA PIN application services."""
    try:
        # Fetch fresh catalog context from database
        current_catalog = get_formatted_catalog()

        system_prompt = f"""
You are the official AI Sales Assistant for "Orb Digital Solutions" in Kenya, specializing exclusively in KRA PIN Applications & Registrations (KSh 300).

PRIMARY DIRECTIVE:
When a customer reaches out or asks for a KRA PIN (e.g., "hi", "i need a KRA pin", "how do I apply"), immediately welcome them to Orb Digital Solutions and start collecting their application details right away. DO NOT pitch physical goods, earbuds, eBooks, or general catalog items.

REQUIRED INTAKE DETAILS:
Politely collect these 4 details (all at once or step-by-step):
1. Full Name (as on National ID)
2. National ID Number
3. Date of Birth (DD/MM/YYYY)
4. Email Address

TAG FINALIZATION RULE:
As soon as (and ONLY when) the customer has provided ALL 4 required details (Full Name, National ID, Date of Birth, Email), confirm their information and append this EXACT tag at the very end of your response:
`[KRA_APP: national_id | dob | full_name | email]`

Example response:
"Thank you! I have saved your details. Please check your phone screen to enter your M-Pesa PIN for KSh 300 to process your registration. [KRA_APP: 38291045 | 14/05/1998 | John Doe | john@example.com]"

RULES:
- Always identify as "Orb Digital Solutions".
- NEVER output the `[KRA_APP: ...]` tag until ALL 4 details are explicitly provided by the user.
- Keep replies under 3 sentences, natural, polite, and WhatsApp-styled.
- If a customer asks about non-KRA products, politely state that you currently specialize exclusively in KRA PIN registrations for KSh 300.
- Always end your message with a single, clear question prompting for any missing detail.

CURRENT SERVICE CATALOG:
{current_catalog}
"""

        # Save user message to memory
        add_message(sender_id, "user", user_message)

        messages_payload = [{"role": "system", "content": system_prompt}]
        messages_payload.extend(get_history(sender_id))

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Updated to Groq's active model
            messages=messages_payload,
            temperature=0.3,  # Lowered temperature for strict instruction adherence
            max_tokens=180,
        )

        bot_reply = response.choices[0].message.content.strip()
        add_message(sender_id, "assistant", bot_reply)

        return bot_reply

    except Exception as e:
        print("\n--- AI GENERATION ERROR ---")
        print(str(e))
        return "Pole! I had a quick system glitch at Orb Digital Solutions. Are you inquiring about our KRA PIN Application service?"