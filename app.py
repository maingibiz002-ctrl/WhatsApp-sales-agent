import os
import re
import logging
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Module imports
from ai_salesman import generate_intelligent_reply
import database as db
import paystack_client


# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OrbDigitalSolutions")

# Initialize FastAPI Application
app = FastAPI(title="Orb Digital Solutions - WhatsApp Engine")

# ------------------------------------------------------------------------------
# ENVIRONMENT CONFIGURATION & TOKEN SANITIZATION
# ------------------------------------------------------------------------------
RAW_TOKEN = os.getenv("WHATSAPP_TOKEN") or os.getenv("ACCESS_TOKEN") or ""
WHATSAPP_TOKEN = RAW_TOKEN.strip().strip('"').strip("'")
ACCESS_TOKEN = WHATSAPP_TOKEN  # Aliased so all functions find it

PHONE_NUMBER_ID = (os.getenv("PHONE_NUMBER_ID") or "").strip().strip('"').strip("'")
ADMIN_PHONE = (os.getenv("ADMIN_PHONE_NUMBER") or "").strip().strip('"').strip("'")
VERIFY_TOKEN = (os.getenv("VERIFY_TOKEN") or "orb_digital_token").strip().strip('"').strip("'")

PROCESSED_MESSAGE_IDS = set()

# ------------------------------------------------------------------------------
# META GRAPH API OUTBOUND HELPERS
# ------------------------------------------------------------------------------
def send_whatsapp_message(to_phone: str, text_body: str):
    """Sends a text message via Meta Graph API."""
    if not PHONE_NUMBER_ID or not WHATSAPP_TOKEN:
        logger.error("❌ Cannot send message: PHONE_NUMBER_ID or WHATSAPP_TOKEN missing.")
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
            logger.info(f"📤 [Outbound Message Sent] To {to_phone}")
        else:
            logger.error(f"❌ [Meta API Error] {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"❌ Outbound Request Exception: {e}")


def send_whatsapp_image(to_phone: str, image_url: str, caption: str = ""):
    """Sends an image message via Meta Graph API."""
    if not PHONE_NUMBER_ID or not WHATSAPP_TOKEN:
        logger.error("❌ Cannot send image: PHONE_NUMBER_ID or WHATSAPP_TOKEN missing.")
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
            logger.info(f"🖼️ [Outbound Image Sent] To {to_phone}")
        else:
            logger.error(f"❌ [Meta API Image Error] {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"❌ Outbound Image Request Exception: {e}")


def log_lead_to_file(lead_type: str, sender: str, details: str):
    """Saves leads to local storage and database."""
    try:
        db.save_lead(lead_type, sender, details)
    except Exception as e:
        logger.error(f"Failed to save lead to database: {e}")

    with open("leads_captured.txt", "a", encoding="utf-8") as f:
        f.write(f"[{lead_type}] Sender: {sender} | Details: {details}\n")


def send_admin_notification(title: str, client_sender: str, details: str):
    """Dispatches dashboard alerts to the admin WhatsApp number."""
    if not ADMIN_PHONE:
        logger.warning("⚠️ ADMIN_PHONE_NUMBER missing in environment variables.")
        return

    alert_body = (
        f"📊 *ORB DIGITAL DASHBOARD ALERT*\n"
        f"────────────────────────────\n"
        f"📌 *Event:* {title}\n"
        f"📱 *Customer:* +{client_sender}\n"
        f"📝 *Details:* {details}\n"
        f"────────────────────────────"
    )
    send_whatsapp_message(ADMIN_PHONE, alert_body)

# ------------------------------------------------------------------------------
# BACKGROUND MESSAGE PROCESSING WORKER
# ------------------------------------------------------------------------------
def process_whatsapp_message(sender: str, message_body: str, background_tasks: BackgroundTasks):
    """Executes AI processing and dispatches single reply in the background."""
    try:
        # 1. Forward inquiry alert to Admin WhatsApp
        if sender != ADMIN_PHONE:
            send_admin_notification(
                title="New Client Inquiry",
                client_sender=sender,
                details=f"Message: \"{message_body}\""
            )

        # 2. Generate short AI response
        reply = generate_intelligent_reply(sender, message_body)

        # 3. Process Action Tags & Backend Tasks
        stk_match = re.search(r"\[TRIGGER_STK:\s*(\d+(?:\.\d+)?)\]", reply)
        nil_match = re.search(r"\[KRA_NIL:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        cert_match = re.search(r"\[KRA_CERT:\s*(.*?)\s*\|\s*(.*?)\]", reply)
        kra_app_match = re.search(r"\[KRA_APP:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        tech_match = re.search(r"\[TECH_LEAD:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        store_match = re.search(r"\[STORE_INQUIRY:\s*(.*?)\s*\|\s*(.*?)\]", reply)

        # Handle Standalone Payment Prompt Request
        if stk_match:
            amount = float(stk_match.group(1))
            reply = re.sub(r"\[TRIGGER_STK:.*?\]", "", reply).strip()
            logger.info(f"💳 [Standalone STK Prompt Requested] Sender: {sender} | Amount: KES {amount}")

            pay_res = paystack_client.trigger_mpesa_stk_push(phone_number=sender, amount=amount)
            if pay_res.get("status"):
                reply += "\n\n💳 *Payment Prompt Sent!* Please check your phone screen and enter your M-Pesa PIN."
            else:
                reply += f"\n\n⚠️ Could not send prompt. Please pay via M-Pesa Till 3543414."

        # Handle Full KRA NIL Submission + Payment
        elif nil_match:
            full_name, kra_pin, password = [nil_match.group(i).strip() for i in range(1, 4)]
            reply = re.sub(r"\[KRA_NIL:.*?\]", "", reply).strip()
            logger.info(f"📝 [KRA NIL Return Captured] Name: {full_name} | PIN: {kra_pin}")

            pay_res = paystack_client.trigger_mpesa_stk_push(phone_number=sender, amount=200.0)
            if pay_res.get("status"):
                reply += "\n\n💳 *Payment Prompt Sent!* Please enter your M-Pesa PIN on your phone screen to start automatic filing."
            else:
                reply += "\n\n⚠️ Could not send prompt. You can pay via M-Pesa Till 3543414."

            background_tasks.add_task(execute_kra_nil_task, sender, kra_pin, password)

        elif cert_match:
            kra_pin, password = [cert_match.group(i).strip() for i in range(1, 3)]
            reply = re.sub(r"\[KRA_CERT:.*?\]", "", reply).strip()
            background_tasks.add_task(execute_kra_cert_task, sender, kra_pin, password)

        elif kra_app_match:
            nat_id, dob, name, email = [kra_app_match.group(i).strip() for i in range(1, 5)]
            reply = re.sub(r"\[KRA_APP:.*?\]", "", reply).strip()
            logger.info(f"📝 [KRA New App] Name: {name} | ID: {nat_id}")

            pay_res = paystack_client.trigger_mpesa_stk_push(phone_number=sender, amount=300.0)
            if pay_res.get("status"):
                reply += "\n\n💳 *Payment Prompt Sent!* Please enter your M-Pesa PIN on your phone screen to complete application."
            else:
                reply += "\n\n⚠️ Could not send prompt. You can pay via M-Pesa Till 3543414."

        elif tech_match:
            client_name, contact_info, reqs = [tech_match.group(i).strip() for i in range(1, 4)]
            details = f"Name: {client_name} | Contact: {contact_info} | Project: {reqs}"
            log_lead_to_file("TECH_LEAD", sender, details)

            if sender != ADMIN_PHONE:
                send_admin_notification("🔥 SOFTWARE LEAD CAPTURED", sender, details)

            reply = re.sub(r"\[TECH_LEAD:.*?\]", "", reply).strip()

        elif store_match:
            item_specs, budget_loc = [store_match.group(i).strip() for i in range(1, 3)]
            details = f"Item: {item_specs} | Budget/Location: {budget_loc}"
            log_lead_to_file("STORE_INQUIRY", sender, details)

            if sender != ADMIN_PHONE:
                send_admin_notification("🛒 STORE INQUIRY CAPTURED", sender, details)

            reply = re.sub(r"\[STORE_INQUIRY:.*?\]", "", reply).strip()

        # 4. Single outbound response dispatch
        image_match = re.search(r"\[IMAGE:\s*(https?://[^\s\]]+)\]", reply)
        if image_match:
            image_url = image_match.group(1)
            reply = re.sub(r"\[IMAGE:\s*https?://[^\s\]]+\]", "", reply).strip()
            send_whatsapp_image(sender, image_url, caption=reply)
        else:
            send_whatsapp_message(sender, reply)

        logger.info(f"🤖 [Single AI Reply Sent] To {sender}")

    except Exception as e:
        logger.error(f"Error executing background WhatsApp processing: {e}")
# ------------------------------------------------------------------------------
# FASTAPI ENDPOINTS
# ------------------------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    try:
        db.init_db()
        logger.info("📦 Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database init error: {e}")


@app.get("/")
async def root():
    return {"status": "online", "system": "Orb Digital Solutions WhatsApp Engine"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("WEBHOOK_VERIFIED")
            return int(challenge)
        return {"status": "error", "message": "Verification token mismatch"}
    return {"status": "error", "message": "Invalid request"}


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()

        entry = data.get("entry", [{}])[0]
        value = entry.get("changes", [{}])[0].get("value", {})

        if "statuses" in value and "messages" not in value:
            return {"status": "ignored"}

        messages = value.get("messages", [])
        if not messages:
            return {"status": "received"}

        message = messages[0]
        msg_id = message.get("id")

        if msg_id in PROCESSED_MESSAGE_IDS:
            logger.info(f"🔁 [Duplicate Discarded] Message ID {msg_id}")
            return {"status": "ignored"}

        PROCESSED_MESSAGE_IDS.add(msg_id)
        if len(PROCESSED_MESSAGE_IDS) > 2000:
            PROCESSED_MESSAGE_IDS.clear()

        sender = message.get("from")
        if message.get("type") != "text":
            return {"status": "received"}

        message_body = message.get("text", {}).get("body", "").strip()
        logger.info(f"📩 [Incoming] {sender}: '{message_body}'")

        # Offload logic to background processing to return HTTP 200 immediately
        background_tasks.add_task(process_whatsapp_message, sender, message_body, background_tasks)

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Webhook Processing Error: {e}")
        return {"status": "error", "message": str(e)}