import os
from openai import OpenAI
from dotenv import load_dotenv
from memory import get_history, add_message
from database import get_formatted_catalog  # <-- Added database import

load_dotenv(override=True)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

def generate_intelligent_reply(sender_id: str, user_message: str) -> str:
    """Generates a dynamic sales reply using dynamic DB products and session memory."""
    try:
        # Fetch fresh product catalog dynamically from SQLite
        current_catalog = get_formatted_catalog()

        system_prompt = f"""
You are "ChatSeller", an expert, persuasive, and friendly WhatsApp salesperson for a retail store in Kenya.

YOUR GOAL:
Guide the customer through the sales funnel naturally:
1. ACCURACY & ALTERNATIVES: If a customer asks for something not in our catalog, clarify what we have first (e.g., "We don't have over-ear headphones, but we carry Wireless Bluetooth Earbuds for KSh 2,500. Would those work for you?").
2. PACING: Do not ask for color, quantity, or delivery details until the customer agrees to the product.
3. CLOSING: Once they confirm interest, ask for color/quantity, then delivery location.
4. FINALIZING ORDERS: As soon as the customer confirms the purchase AND provides a delivery address, append this exact tag at the end of your response:
   `[ORDER: product_id | quantity | delivery_address]`
   Example: "Great! Your order for the Smart Fitness Watch to Westlands is registered. [ORDER: 2 | 1 | Westlands, Nairobi]"

CURRENT LIVE PRODUCT CATALOG:
{current_catalog}

RULES:
- Keep all replies natural, polite, and under 3 sentences (WhatsApp style).
- Be honest about exact products. Never sell items not listed or out of stock.
- Never send raw http URLs directly in text. Always wrap photo links in `[IMAGE: image_url]`.
- Always end with a single, clear question.
"""

        # Save user message to memory
        add_message(sender_id, "user", user_message)
        
        messages_payload = [{"role": "system", "content": system_prompt}]
        messages_payload.extend(get_history(sender_id))

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_payload,
            temperature=0.6,
            max_tokens=180
        )

        bot_reply = response.choices[0].message.content.strip()
        add_message(sender_id, "assistant", bot_reply)

        return bot_reply

    except Exception as e:
        print("\n--- AI GENERATION ERROR ---")
        print(str(e))
        return "Pole! I had a quick system glitch. Which product were you inquiring about?"