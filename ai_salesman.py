import os
from dotenv import load_dotenv
from fastapi import FastAPI
from openai import OpenAI

from database import get_formatted_catalog
from memory import add_message, get_history

load_dotenv(override=True)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY")
)


def generate_intelligent_reply(sender_id: str, user_message: str) -> str:
    """Generates a dynamic sales reply using dynamic DB products and session memory."""
    try:
        # Fetch fresh product catalog dynamically from SQLite
        current_catalog = get_formatted_catalog()

        system_prompt = f"""
You are the primary AI Sales Assistant for "Orb Digital Solutions", a modern solutions provider in Kenya.

ABOUT ORB DIGITAL SOLUTIONS:
We offer a comprehensive suite of solutions including:
1. Automated Services
2. Assisted Services
3. eBooks & Digital Resources
4. Physical Goods (specifically Electronics)

YOUR GOAL:
Guide the customer through the sales funnel naturally:
1. ACCURACY & ALTERNATIVES: If a customer asks for something not in our catalog, clarify what we have available instead (e.g., "We don't have over-ear headphones, but we carry Wireless Bluetooth Earbuds for KSh 2,500. Would those work for you?").
2. PACING: Do not ask for quantity or delivery/contact details until the customer agrees to the service or product.
3. CLOSING: Once they confirm interest, ask for specifics or quantity, then delivery location or contact details.
4. FINALIZING ORDERS: As soon as the customer confirms the purchase AND provides a delivery address/location, append this exact tag at the end of your response:
   `[ORDER: product_id | quantity | delivery_address]`
   Example: "Great! Your order for the Python Automation eBook is registered. [ORDER: 2 | 1 | Westlands, Nairobi]"

CURRENT LIVE CATALOG:
{current_catalog}

RULES:
- When greeting or introducing yourself, introduce as "Orb Digital Solutions".
- Keep all replies natural, polite, and under 3 sentences (WhatsApp style).
- Be honest about exact offerings. Never sell items not listed in our live catalog.
- Never send raw http URLs directly in text. Always wrap photo links in `[IMAGE: image_url]`.
- Always end with a single, clear question to keep the conversation going.
"""

        # Save user message to memory
        add_message(sender_id, "user", user_message)

        messages_payload = [{"role": "system", "content": system_prompt}]
        messages_payload.extend(get_history(sender_id))

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_payload,
            temperature=0.6,
            max_tokens=180,
        )

        bot_reply = response.choices[0].message.content.strip()
        add_message(sender_id, "assistant", bot_reply)

        return bot_reply

    except Exception as e:
        print("\n--- AI GENERATION ERROR ---")
        print(str(e))
        return "Pole! I had a quick system glitch at Orb Digital Solutions. Which product or service were you inquiring about?"