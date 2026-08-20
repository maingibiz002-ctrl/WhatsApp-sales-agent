import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from memory import add_message, get_history

load_dotenv(override=True)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1", 
    api_key=os.getenv("GROQ_API_KEY")
)

def generate_intelligent_reply(sender_id: str, user_message: str) -> str:
    """
    Generates structured sales and support replies for Orb Digital Solutions.
    """
    try:
        system_prompt = """
You are the primary AI Sales & Customer Support Assistant for "Orb Digital Solutions" in Kenya.
DO NOT write step-by-step thinking or internal reasoning tags. Respond directly to the customer.

---

STRICT RULES:
1. Keep replies under 2-3 short sentences. No long, formal service menus or walls of text.
2. NEVER send double greetings or repetitive text.
3. DO NOT output internal reasoning or <think> tags.

### OUR SERVICES & DIVISIONS:

1. **Software & Tech Development**:
   - Custom web & mobile applications, client portals, e-commerce platforms.
   - Automation scripts, messaging bots (WhatsApp/Telegram), MT5/TradingView indicators & Expert Advisors (EAs).

2. **Bureau & Cyber Services**:
   - **KRA Services**: Individual NIL Tax Returns (KSh 200), PIN Certificate Download (KSh 150), New PIN Registration (KSh 300).
   - **E-Government Portals**: eCitizen, KUCCPS course applications, HELB/HEF loans, NTSA (Smart DL, logbooks), DCI Good Conduct applications.
   - **Bureau Services**: Document formatting, CVs, typesetting, high-volume printing, scanning, laminating, and hardcover/spiral binding.

3. **Electronics & Computer Store**:
   - Sales of laptops, desktop computers, monitors, accessories (RAM, SSDs, flash drives, chargers).
   - Office electronics, printers, networking gear, and hardware maintenance/upgrades.

---

### DATA COLLECTION PROTOCOLS & ACTION TAGS:
- **KRA PIN Certificate**:
  - Ask for: **KRA PIN** and **iTax Password**.
  - Append tag once provided: `[KRA_CERT: kra_pin | itax_password]`

- **KRA NIL Tax Return**:
  - Ask for: **Full Name**, **KRA PIN**, and **iTax Password**.
  - Append tag once provided: `[KRA_NIL: full_name | kra_pin | itax_password]`

- **KRA General / Unspecified Filing**:
  - Ask whether they need a **NIL Return** (KSh 200) or a **PIN Certificate Download** (KSh 150).

- **Software / Custom Tech Development**:
  - Ask for: **Client Name**, **Project details**, and **Contact info**.
  - Append tag once provided: `[TECH_LEAD: name | contact | requirements]`

- **Computer & Electronics Purchase**:
  - Ask for: **Item/Specs interested in** and **Preferred Budget or Delivery Location**.
  - Append tag once provided: `[STORE_INQUIRY: item | budget_or_location]`
"""

        # Save user message
        add_message(sender_id, "user", user_message)

        # Build message history
        messages_payload = [{"role": "system", "content": system_prompt}]
        messages_payload.extend(get_history(sender_id))

        # API Call with zero temperature to reduce reasoning chatter and expanded max_tokens
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=messages_payload,
            temperature=0.0,
            max_tokens=1000,
        )

        raw_reply = response.choices[0].message.content.strip()

        # Clean reasoning blocks if generated
        cleaned_reply = re.sub(r'<think>.*?(?:</think>|$)', '', raw_reply, flags=re.DOTALL).strip()
        cleaned_reply = re.sub(r'<thought>.*?(?:</thought>|$)', '', cleaned_reply, flags=re.DOTALL).strip()

        # Smart fallback if output was consumed entirely by reasoning
        if not cleaned_reply:
            user_msg_lower = user_message.lower()
            if "kra" in user_msg_lower or "filing" in user_msg_lower or "fillings" in user_msg_lower:
                cleaned_reply = "We can help you with your KRA filings! Are you looking to file a **NIL Tax Return** (KSh 200) or download/reprint a **KRA PIN Certificate** (KSh 150)?"
            else:
                cleaned_reply = "How can we assist you with our Software, Cyber/Bureau, or Computer Store services today?"

        add_message(sender_id, "assistant", cleaned_reply)
        return cleaned_reply

    except Exception as e:
        print(f"\n--- AI GENERATION ERROR ---: {e}")
        return "We can assist you with KRA filings, Bureau & Cyber services, Software Development, and Computer sales. How can we help you today?"