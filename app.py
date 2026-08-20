import logging
import os
import re
import asyncio
import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ai_salesman import generate_intelligent_reply
import database as db
from paystack import PaystackManager
from services.kra_automator import KRAAutomator

load_dotenv(override=True)

app = FastAPI()


# ------------------------------------------------------------------------------
# META WHATSAPP & ADMIN CONFIGURATION (MUST BE DEFINED HERE)
# ------------------------------------------------------------------------------
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "").strip()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()
ADMIN_PHONE = os.getenv("ADMIN_PHONE_NUMBER", "").strip()
ACCESS_TOKEN = WHATSAPP_TOKEN
PROCESSED_MESSAGE_IDS = set()

# ==============================================================================
# SECTION 1: SERVER CONFIGURATION & LOGGING
# (Edit this section ONLY if changing server environment variables or API ports)
# ==============================================================================

logger = logging.getLogger("OrbDigitalSolutions")

ADMIN_PHONE = os.getenv("ADMIN_PHONE_NUMBER", "").strip()

# Helper function to send instant WhatsApp updates to admin
def send_admin_notification(title: str, client_sender: str, details: str):
    """Sends immediate activity and lead alerts to your personal WhatsApp number."""
    if not ADMIN_PHONE:
        logger.warning("⚠️ ADMIN_PHONE_NUMBER not configured. Skipping admin alert.")
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
        sender = message.get("from")

        if message.get("type") != "text":
            return {"status": "received"}

        message_body = message.get("text", {}).get("body", "").strip()
        logger.info(f"📩 [Incoming] {sender}: '{message_body}'")

        # Skip alerts if the admin is texting the bot directly
        if sender == ADMIN_PHONE:
            reply = generate_intelligent_reply(sender, message_body)
            send_whatsapp_message(sender, reply)
            return {"status": "received"}

        # 1. ALERT ADMIN: Log every new contact/inquiry attempt
        send_admin_notification(
            title="New Inquiry Received",
            client_sender=sender,
            details=f"Inquired: \"{message_body}\""
        )

        # Generate AI response
        reply = generate_intelligent_reply(sender, message_body)

        # 2. TAG: SOFTWARE / TECH DEVELOPMENT
        tech_lead_match = re.search(r"\[TECH_LEAD:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if tech_lead_match:
            client_name, contact_info, reqs = [tech_lead_match.group(i).strip() for i in range(1, 4)]
            
            send_admin_notification(
                title="🔥 HIGH PRIOR TICKET: Software Lead",
                client_sender=sender,
                details=f"Name: {client_name}\nContact: {contact_info}\nProject Specs: {reqs}"
            )

            clean_reply = re.sub(r"\[TECH_LEAD:.*?\]", "", reply).strip()
            send_whatsapp_message(sender, clean_reply)
            return {"status": "received"}

        # 3. TAG: COMPUTER & ELECTRONICS STORE INQUIRY
        store_match = re.search(r"\[STORE_INQUIRY:\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if store_match:
            item_specs, budget_loc = [store_match.group(i).strip() for i in range(1, 3)]
            
            send_admin_notification(
                title="🛒 STORE INQUIRY: Hardware / Electronics",
                client_sender=sender,
                details=f"Item Request: {item_specs}\nBudget/Location: {budget_loc}"
            )

            clean_reply = re.sub(r"\[STORE_INQUIRY:.*?\]", "", reply).strip()
            send_whatsapp_message(sender, clean_reply)
            return {"status": "received"}

        # 4. TAG: KRA NIL RETURN
        nil_match = re.search(r"\[KRA_NIL:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if nil_match:
            full_name, kra_pin, password = [nil_match.group(i).strip() for i in range(1, 4)]
            
            send_admin_notification(
                title="📄 KRA NIL Filing Order",
                client_sender=sender,
                details=f"Name: {full_name}\nPIN: {kra_pin}"
            )

            clean_reply = re.sub(r"\[KRA_NIL:.*?\]", "", reply).strip()
            send_whatsapp_message(sender, clean_reply)
            background_tasks.add_task(execute_kra_nil_task, sender, kra_pin, password)
            return {"status": "received"}

        # 5. TAG: KRA PIN CERTIFICATE
        cert_match = re.search(r"\[KRA_CERT:\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if cert_match:
            kra_pin, password = [cert_match.group(i).strip() for i in range(1, 3)]
            
            send_admin_notification(
                title="📜 KRA Certificate Download Order",
                client_sender=sender,
                details=f"PIN: {kra_pin}"
            )

            clean_reply = re.sub(r"\[KRA_CERT:.*?\]", "", reply).strip()
            send_whatsapp_message(sender, clean_reply)
            background_tasks.add_task(execute_kra_cert_task, sender, kra_pin, password)
            return {"status": "received"}

        # Standard AI response to customer
        send_whatsapp_message(sender, reply)
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Webhook Processing Error: {e}")
        return {"status": "error", "message": str(e)}

# ==============================================================================
# SECTION 2: OUTBOUND WHATSAPP MESSAGING HELPERS
# (Edit this section ONLY if Meta API endpoints or message formats change)
# ==============================================================================

def send_whatsapp_message(recipient: str, message: str):
    if not message or not message.strip():
        message = "Please try again later or contact support at [0743634717]."

    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": message},
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code != 200:
            logger.error(f"Failed to send message to {recipient}: {res.text}")
        return res
    except Exception as e:
        logger.error(f"WhatsApp API Error ({recipient}): {e}")
        return None


def send_whatsapp_image(recipient: str, image_url: str, caption: str = ""):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code != 200:
            logger.error(f"Failed to send image to {recipient}: {res.text}")
        return res
    except Exception as e:
        logger.error(f"WhatsApp Image API Error ({recipient}): {e}")
        return None


def send_whatsapp_document(recipient: str, file_path: str, caption: str = ""):
    if not os.path.exists(file_path):
        logger.error(f"Cannot send missing file: {file_path}")
        return None

    upload_url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    
    try:
        with open(file_path, "rb") as file:
            files = {"file": (os.path.basename(file_path), file, "application/pdf")}
            data = {"messaging_product": "whatsapp"}
            upload_res = requests.post(upload_url, headers=headers, data=data, files=files, timeout=30)

        media_id = upload_res.json().get("id")
        if not media_id:
            logger.error(f"Media upload failed: {upload_res.text}")
            return None

        message_url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": os.path.basename(file_path),
                "caption": caption
            }
        }
        return requests.post(message_url, headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}, json=payload, timeout=15)
    except Exception as e:
        logger.error(f"WhatsApp Document API Error ({recipient}): {e}")
        return None


# ==============================================================================
# SECTION 3: INCOMING MESSAGES & AI ACTION TAG HANDLER
# (Edit this section when adding NEW services, tags, or lead collection rules)
# ==============================================================================

async def execute_kra_nil_task(sender: str, kra_pin: str, password: str):
    logger.info(f"⚡ [Background Task] Running NIL return for PIN: {kra_pin}")
    result = await kra_automator.file_nil_return(kra_pin, password)
    
    if result.get("success"):
        file_path = result.get("file_path")
        send_whatsapp_message(sender, f"✅ Your KRA NIL Return for PIN {kra_pin} has been filed successfully!")
        send_whatsapp_document(sender, file_path, caption="Official KRA Acknowledgment Receipt")
    else:
        error_msg = result.get("error", "Unknown error")
        send_whatsapp_message(sender, f"⚠️ We encountered an issue filing your return for {kra_pin}: {error_msg}. A representative will review this shortly.")


async def execute_kra_cert_task(sender: str, kra_pin: str, password: str):
    logger.info(f"⚡ [Background Task] Downloading PIN Certificate for PIN: {kra_pin}")
    result = await kra_automator.download_pin_certificate(kra_pin, password)
    
    if result.get("success"):
        file_path = result.get("file_path")
        send_whatsapp_message(sender, f"✅ Here is your requested KRA PIN Certificate for {kra_pin}:")
        send_whatsapp_document(sender, file_path, caption=f"KRA PIN Certificate ({kra_pin})")
    else:
        error_msg = result.get("error", "Unknown error")
        send_whatsapp_message(sender, f"⚠️ Unable to download certificate for {kra_pin}: {error_msg}.")


def log_lead_to_file(lead_type: str, sender: str, details: str):
    """Saves leads to both the SQLite database and log file."""
    try:
        db.save_lead(lead_type, sender, details)
        logger.info(f"💾 [DB Saved] Lead saved to database successfully.")
    except Exception as e:
        logger.error(f"Failed to save lead to database: {e}")

    with open("leads_captured.txt", "a", encoding="utf-8") as f:
        f.write(f"[{lead_type}] Sender: {sender} | Details: {details}\n")


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
        sender = message.get("from")

        if message.get("type") != "text":
            return {"status": "received"}

        message_body = message.get("text", {}).get("body", "").strip()
        logger.info(f"📩 [Incoming] {sender}: '{message_body}'")

        # ----------------------------------------------------------------------
        # 1. ADMIN WHATSAPP DASHBOARD ALERT
        # ----------------------------------------------------------------------
        if sender != ADMIN_PHONE:
            send_admin_notification(
                title="New Client Inquiry",
                client_sender=sender,
                details=f"Message: \"{message_body}\""
            )

        # Generate AI response
        reply = generate_intelligent_reply(sender, message_body)

        # ----------------------------------------------------------------------
        # 2. ACTION TAG PROCESSING & BACKEND TASKS
        # ----------------------------------------------------------------------
        # TAG 1: KRA NIL RETURN
        nil_match = re.search(r"\[KRA_NIL:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if nil_match:
            full_name, kra_pin, password = [nil_match.group(i).strip() for i in range(1, 4)]
            reply = re.sub(r"\[KRA_NIL:.*?\]", "", reply).strip()
            
            pay_res = paystack_client.trigger_mpesa_stk_push(phone_number=sender, amount=200.0)
            if pay_res.get("status"):
                reply += "\n\n💳 *Payment Prompt Sent!* Please enter your M-Pesa PIN on your phone screen to start automatic filing."
            
            background_tasks.add_task(execute_kra_nil_task, sender, kra_pin, password)

        # TAG 2: KRA CERTIFICATE DOWNLOAD
        cert_match = re.search(r"\[KRA_CERT:\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if cert_match:
            kra_pin, password = [cert_match.group(i).strip() for i in range(1, 3)]
            reply = re.sub(r"\[KRA_CERT:.*?\]", "", reply).strip()
            background_tasks.add_task(execute_kra_cert_task, sender, kra_pin, password)

        # TAG 3: KRA NEW APPLICATION
        kra_app_match = re.search(r"\[KRA_APP:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if kra_app_match:
            nat_id, dob, name, email = [kra_app_match.group(i).strip() for i in range(1, 5)]
            reply = re.sub(r"\[KRA_APP:.*?\]", "", reply).strip()
            
            pay_res = paystack_client.trigger_mpesa_stk_push(phone_number=sender, amount=300.0)
            if pay_res.get("status"):
                reply += "\n\n💳 *Payment Prompt Sent!* Please enter your M-Pesa PIN on your phone screen to complete application."

        # TAG 4: SOFTWARE / TECH DEVELOPMENT LEAD
        tech_lead_match = re.search(r"\[TECH_LEAD:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if tech_lead_match:
            client_name, contact_info, reqs = [tech_lead_match.group(i).strip() for i in range(1, 4)]
            details = f"Name: {client_name} | Contact: {contact_info} | Project: {reqs}"
            log_lead_to_file("TECH_LEAD", sender, details)
            
            if sender != ADMIN_PHONE:
                send_admin_notification("🔥 SOFTWARE LEAD CAPTURED", sender, details)
            
            reply = re.sub(r"\[TECH_LEAD:.*?\]", "", reply).strip()

        # TAG 5: COMPUTER & ELECTRONICS STORE INQUIRY
        store_match = re.search(r"\[STORE_INQUIRY:\s*(.*?)\s*\|\s*(.*?)\]", reply)
        if store_match:
            item_specs, budget_loc = [store_match.group(i).strip() for i in range(1, 3)]
            details = f"Item: {item_specs} | Budget/Loc: {budget_loc}"
            log_lead_to_file("STORE_INQUIRY", sender, details)
            
            if sender != ADMIN_PHONE:
                send_admin_notification("🛒 STORE INQUIRY CAPTURED", sender, details)
            
            reply = re.sub(r"\[STORE_INQUIRY:.*?\]", "", reply).strip()

        # ----------------------------------------------------------------------
        # 3. SINGLE MESSAGE DISPATCH TO CLIENT
        # ----------------------------------------------------------------------
        image_match = re.search(r"\[IMAGE:\s*(https?://[^\s\]]+)\]", reply)
        if image_match:
            image_url = image_match.group(1)
            reply = re.sub(r"\[IMAGE:\s*https?://[^\s\]]+\]", "", reply).strip()
            send_whatsapp_image(sender, image_url, caption=reply)
        else:
            send_whatsapp_message(sender, reply)

        logger.info(f"🤖 [AI Reply Sent] To {sender}")
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Webhook Processing Error: {e}")
        return {"status": "error", "message": str(e)}

# ==============================================================================
# SECTION 4: PAYMENTS & ADMIN DASHBOARD ENDPOINTS
# (Edit this section ONLY if changing Paystack routes or Web Dashboard views)
# ==============================================================================

@app.post("/paystack/webhook")
async def paystack_webhook(request: Request):
    try:
        payload = await request.json()
        if payload.get("event") == "charge.success":
            reference = payload.get("data", {}).get("reference")
            if reference:
                logger.info(f"💰 [Payment Received] Reference: {reference}")
                db.mark_order_as_paid(reference)

        return JSONResponse(content={"status": "success"}, status_code=200)
    except Exception as e:
        logger.error(f"Paystack Webhook Error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


@app.get("/dashboard", response_class=HTMLResponse)
async def seller_dashboard(request: Request):
    try:
        orders = db.get_all_orders()
        products = db.get_all_products()
        leads = db.get_all_leads()  # Fetch leads from DB
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={"orders": orders, "products": products, "leads": leads},
        )
    except Exception as e:
        return HTMLResponse(content=f"<h2>Dashboard Load Error</h2><p><b>Error:</b> {e}</p>")


@app.post("/dashboard/products/add")
async def add_product(
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    image_url: str = Form(""),
):
    db.add_product(name, price, description, image_url)
    return RedirectResponse(url="/dashboard", status_code=303)