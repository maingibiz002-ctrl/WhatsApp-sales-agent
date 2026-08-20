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
    Generates structured sales and support replies for Orb Digital Solutions across:
    1. Software & Tech Development
    2. Bureau & Cyber Services
    3. Electronics & Computer Store
    """
    try:
        system_prompt = """
You are the primary AI Sales & Customer Support Assistant for "Orb Digital Solutions" in Kenya.
Your role is to handle customer inquiries across our four main business divisions clearly and professionally.

---

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

### COMMUNICATION STYLE:
- **Professional & Helpfully Articulate**: Maintain a warm, business-ready, polite tone.
- **WhatsApp Optimized**: Use clean spacing, concise bullet points (`•`), and **bolding** for high scannability.
- **Direct & Helpful**: Respond directly without internal reasoning markers.

---

### DATA COLLECTION PROTOCOLS & ACTION TAGS:
- **KRA PIN Certificate**:
  - Ask for: **KRA PIN** and **iTax Password**.
  - Append tag once provided: `[KRA_CERT: kra_pin | itax_password]`

- **KRA NIL Tax Return**:
  - Ask for: **Full Name**, **KRA PIN**, and **iTax Password**.
  - Append tag once provided: `[KRA_NIL: full_name | kra_pin | itax_password]`

- **Software / Custom Tech Development**:
  - Ask for: **Client Name**, **Project/Service details**, and **Email or Phone Number**.
  - Append tag once provided: `[TECH_LEAD: name | contact | requirements]`

- **Computer & Electronics Purchase**:
  - Ask for: **Item/Specs interested in** and **Preferred Budget or Delivery Location**.
  - Append tag once provided: `[STORE_INQUIRY: item | budget_or_location]`

- **General Greetings**:
  - Welcomingly introduce **Orb Digital Solutions**, briefly outline our core categories (Software, Cyber/Bureau, Computer Store), and ask how you can assist.
"""

        # Save user message
        add_message(sender_id, "user", user_message)

        # Build payload
        messages_payload = [{"role": "system", "content": system_prompt}]
        messages_payload.extend(get_history(sender_id))

        # API Call
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=messages_payload,
            temperature=0.3,
            max_tokens=650,
        )

        raw_reply = response.choices[0].message.content.strip()

        # Clean reasoning blocks if generated
        cleaned_reply = re.sub(r'<think>.*?(?:</think>|$)', '', raw_reply, flags=re.DOTALL).strip()
        cleaned_reply = re.sub(r'<thought>.*?(?:</thought>|$)', '', cleaned_reply, flags=re.DOTALL).strip()

        if not cleaned_reply:
            cleaned_reply = "Welcome to **Orb Digital Solutions**! We specialize in Software Development, Cyber & Bureau Services, and Computers & Electronics. How can we assist you today?"

        add_message(sender_id, "assistant", cleaned_reply)
        return cleaned_reply

    except Exception as e:
        print(f"\n--- AI GENERATION ERROR ---: {e}")
        return "Welcome to **Orb Digital Solutions**! How can we assist you with our services today?"