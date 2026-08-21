import os
import re
import logging
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Internal module imports
from ai_salesman import generate_intelligent_reply
import database as db

# Initialize Application Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OrbDigitalSolutions")

# Initialize FastAPI Framework
app = FastAPI(title="Orb Digital Solutions - ChatMall WhatsApp Engine")

# ==============================================================================
# 1. ENVIRONMENT CONFIGURATION & SECURITY SANITIZATION
# ==============================================================================
RAW_TOKEN = os.getenv("WHATSAPP_TOKEN") or os.getenv("ACCESS_TOKEN") or ""
WHATSAPP_TOKEN = RAW_TOKEN.strip().strip('"').strip("'")
ACCESS_TOKEN = WHATSAPP_TOKEN  # Alias for fallback verification

PHONE_NUMBER_ID = (os.getenv("PHONE_NUMBER_ID") or "").strip().strip('"').strip("'")
ADMIN_PHONE = (os.getenv("ADMIN_PHONE_NUMBER") or "").strip().strip('"').strip("'")
VERIFY_TOKEN = (os.getenv("VERIFY_TOKEN") or "orb_digital_token").strip().strip('"').strip("'")

# In-memory deduplication set to avoid processing duplicate Meta webhooks
PROCESSED_MESSAGE_IDS = set()


# ==============================================================================
# 2. META GRAPH API OUTBOUND MESSAGING HELPERS
# ==============================================================================
def send_whatsapp_message(to_phone: str, text_body: str):
    """
    Dispatches a standard text message to a customer or admin via Meta Graph API.
    """
    if not PHONE_NUMBER_ID or not WHATSAPP_TOKEN:
        logger.error("❌ Outbound Failed: PHONE_NUMBER_ID or WHATSAPP_TOKEN missing.")
        return

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text_body},
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            logger.info(f"📤 [Outbound Text Sent] To: +{to_phone}")
        else:
            logger.error(f"❌ [Meta API Error] {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"❌ Outbound Request Exception: {e}")


def send_whatsapp_image(to_phone: str, image_url: str, caption: str = ""):
    """
    Dispatches a media image with an optional text caption via Meta Graph API.
    """
    if not PHONE_NUMBER_ID or not WHATSAPP_TOKEN:
        logger.error("❌ Outbound Failed: PHONE_NUMBER_ID or WHATSAPP_TOKEN missing.")
        return

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            logger.info(f"🖼️ [Outbound Image Sent] To: +{to_phone}")
        else:
            logger.error(f"❌ [Meta API Image Error] {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"❌ Outbound Image Request Exception: {e}")


# ==============================================================================
# 3. LEAD STORAGE & ADMIN NOTIFICATION PIPELINE
# ==============================================================================
def log_lead_to_file(lead_type: str, sender: str, details: str):
    """
    Persists order inquiries and service leads to SQLite database and text logs.
    """
    try:
        db.save_lead(lead_type, sender, details)
    except Exception as e:
        logger.error(f"Database save exception: {e}")

    with open("leads_captured.txt", "a", encoding="utf-8") as f:
        f.write(f"[{lead_type}] Sender: {sender} | Details: {details}\n")


def send_admin_notification(title: str, client_sender: str, details: str):
    """
    Routes real-time order alerts directly to your Admin WhatsApp number for JForce fulfillment.
    """
    if not ADMIN_PHONE:
        logger.warning("⚠️ ADMIN_PHONE_NUMBER missing in environment variables.")
        return

    alert_body = (
        f"📊 *CHATMALL / ORB DIGITAL ALERT*\n"
        f"────────────────────────────\n"
        f"📌 *Event:* {title}\n"
        f"📱 *Customer Phone:* +{client_sender}\n"
        f"📝 *Details:* {details}\n"
        f"────────────────────────────"
    )
    send_whatsapp_message(ADMIN_PHONE, alert_body)


# ==============================================================================
# 4. BACKGROUND AI & WORKFLOW PROCESSING ENGINE
# ==============================================================================
def process_whatsapp_message(sender: str, message_body: str):
    """
    Executes AI query analysis, extracts media/tags, logs leads, and sends customer responses.
    """
    try:
        # Step A: Notify Admin of incoming client inquiry
        if sender != ADMIN_PHONE:
            send_admin_notification(
                title="New Client Inquiry",
                client_sender=sender,
                details=f"Message: \"{message_body}\""
            )

        # Step B: Generate AI salesman response
        reply = generate_intelligent_reply(sender, message_body)

        # Step C: Parse domain-specific action tags from AI response
        tech_match = re.search(r"\[TECH_LEAD:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        store_match = re.search(r"\[STORE_INQUIRY:\s*(.*?)\s*\|\s*(.*?)\]", reply)

        if tech_match:
            client_name, contact_info, reqs = [tech_match.group(i).strip() for i in range(1, 4)]
            details = f"Name: {client_name} | Contact: {contact_info} | Project: {reqs}"
            log_lead_to_file("TECH_LEAD", sender, details)

            if sender != ADMIN_PHONE:
                send_admin_notification("🔥 SOFTWARE / TECH LEAD CAPTURED", sender, details)

            reply = re.sub(r"\[TECH_LEAD:.*?\]", "", reply).strip()

        elif store_match:
            item_specs, location_info = [store_match.group(i).strip() for i in range(1, 3)]
            details = f"Item/Order: {item_specs} | Location & Contact: {location_info}"
            log_lead_to_file("STORE_INQUIRY", sender, details)

            if sender != ADMIN_PHONE:
                send_admin_notification("🛒 CHATMALL ORDER READY FOR JFORCE", sender, details)

            reply = re.sub(r"\[STORE_INQUIRY:.*?\]", "", reply).strip()

        # Step D: Route response (Send Native WhatsApp Image OR Plain Text)
        image_match = re.search(r"\[IMAGE:\s*(https?://[^\s\]]+)\]", reply)
        if image_match:
            image_url = image_match.group(1)
            clean_caption = re.sub(r"\[IMAGE:\s*https?://[^\s\]]+\]", "", reply).strip()
            send_whatsapp_image(sender, image_url, caption=clean_caption)
        else:
            send_whatsapp_message(sender, reply)

        logger.info(f"🤖 [AI Response Dispatched] To: +{sender}")

    except Exception as e:
        logger.error(f"Error processing background WhatsApp message: {e}")


# ==============================================================================
# 5. FASTAPI ROUTING ENDPOINTS & LIFECYCLE
# ==============================================================================
@app.on_event("startup")
def startup_event():
    """Initializes local database tables on app boot."""
    try:
        db.init_db()
        logger.info("📦 Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database init error: {e}")


@app.get("/")
async def root():
    """Health check ping endpoint."""
    return {"status": "online", "system": "Orb Digital Solutions WhatsApp Engine"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Handles Meta Graph API Webhook Verification."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("✅ WEBHOOK_VERIFIED")
            return int(challenge)
        return {"status": "error", "message": "Verification token mismatch"}
    return {"status": "error", "message": "Invalid request"}


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives incoming WhatsApp messages, deduplicates requests, and offloads work to background tasks.
    """
    try:
        data = await request.json()

        entry = data.get("entry", [{}])[0]
        value = entry.get("changes", [{}])[0].get("value", {})

        # Ignore status updates (read receipts, delivery confirmations)
        if "statuses" in value and "messages" not in value:
            return {"status": "ignored"}

        messages = value.get("messages", [])
        if not messages:
            return {"status": "received"}

        message = messages[0]
        msg_id = message.get("id")

        # Deduplicate incoming Meta requests
        if msg_id in PROCESSED_MESSAGE_IDS:
            logger.info(f"🔁 [Duplicate Suppressed] Message ID: {msg_id}")
            return {"status": "ignored"}

        PROCESSED_MESSAGE_IDS.add(msg_id)
        if len(PROCESSED_MESSAGE_IDS) > 2000:
            PROCESSED_MESSAGE_IDS.clear()

        sender = message.get("from")
        if message.get("type") != "text":
            return {"status": "received"}

        message_body = message.get("text", {}).get("body", "").strip()
        logger.info(f"📩 [Incoming Message] +{sender}: '{message_body}'")

        # Delegate execution to FastAPI background worker (returns HTTP 200 immediately to Meta)
        background_tasks.add_task(process_whatsapp_message, sender, message_body)

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Webhook Processing Error: {e}")
        return {"status": "error", "message": str(e)}