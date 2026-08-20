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
from kra_automator import KRAAutomator

load_dotenv(override=True)

# --------------------------------------------------
# LOGGING & CONFIGURATION
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ChatSeller")

app = FastAPI(title="Orb Digital Solutions - WhatsApp Server")
templates = Jinja2Templates(directory="templates")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "chatseller_test_123").strip()
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "").strip()

paystack_client = PaystackManager()
kra_automator = KRAAutomator()

logger.info(f"🚀 Server started | Phone ID: {PHONE_NUMBER_ID[:6]}... | Verify Token: Configured")


@app.get("/")
def home():
    return {"status": "Orb Digital Solutions API is running"}


# --------------------------------------------------
# META WEBHOOK VERIFICATION
# --------------------------------------------------

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully with Meta.")
        return Response(content=challenge, media_type="text/plain", status_code=200)

    logger.warning("❌ Webhook verification failed. Token mismatch.")
    return Response(content="Verification failed", status_code=403)


# --------------------------------------------------
# OUTBOUND MESSAGING UTILITIES
# --------------------------------------------------

def send_whatsapp_message(recipient: str, message: str):
    if not message or not message.strip():
        message = "Hello! How can Orb Digital Solutions assist you today?"

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
    """Uploads a local PDF file to Meta and sends it to the user."""
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


# --------------------------------------------------
# BACKGROUND KRA AUTOMATION TASKS
# --------------------------------------------------

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


# --------------------------------------------------
# INCOMING WEBHOOK HANDLER
# --------------------------------------------------

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()

        entry = data.get("entry", [{}])[0]
        value = entry.get("changes", [{}])[0].get("value", {})

        # Ignore non-message status updates (read, delivered, sent)
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

        # Generate AI response
        reply = generate_intelligent_reply(sender, message_body)

        # 1. HANDLE KRA NIL RETURN TAG
        nil_match = re.search(
            r"\[KRA_NIL:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply
        )
        if nil_match:
            full_name = nil_match.group(1).strip()
            kra_pin = nil_match.group(2).strip()
            password = nil_match.group(3).strip()

            clean_reply = re.sub(r"\[KRA_NIL:.*?\]", "", reply).strip()
            logger.info(f"📝 [KRA NIL Return Captured] Name: {full_name} | PIN: {kra_pin}")

            # Trigger M-Pesa Payment (KSh 200)
            pay_res = paystack_client.trigger_mpesa_stk_push(phone_number=sender, amount=200.0)

            if pay_res.get("status"):
                clean_reply += "\n\n💳 *Payment Prompt Sent!* Please enter your M-Pesa PIN on your phone screen to start automatic filing."
            
            send_whatsapp_message(sender, clean_reply)
            
            # Delegate automation task to background queue
            background_tasks.add_task(execute_kra_nil_task, sender, kra_pin, password)
            return {"status": "received"}

        # 2. HANDLE KRA CERTIFICATE DOWNLOAD TAG
        cert_match = re.search(
            r"\[KRA_CERT:\s*(.*?)\s*\|\s*(.*?)\]", reply
        )
        if cert_match:
            kra_pin = cert_match.group(1).strip()
            password = cert_match.group(2).strip()

            clean_reply = re.sub(r"\[KRA_CERT:.*?\]", "", reply).strip()
            send_whatsapp_message(sender, clean_reply)

            background_tasks.add_task(execute_kra_cert_task, sender, kra_pin, password)
            return {"status": "received"}

        # 3. HANDLE KRA NEW APPLICATION TAG
        kra_app_match = re.search(
            r"\[KRA_APP:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]", reply
        )
        if kra_app_match:
            nat_id = kra_app_match.group(1).strip()
            dob = kra_app_match.group(2).strip()
            name = kra_app_match.group(3).strip()
            email = kra_app_match.group(4).strip()

            clean_reply = re.sub(r"\[KRA_APP:.*?\]", "", reply).strip()
            logger.info(f"📝 [KRA New Application] Name: {name} | ID: {nat_id}")

            pay_res = paystack_client.trigger_mpesa_stk_push(phone_number=sender, amount=300.0)
            if pay_res.get("status"):
                clean_reply += "\n\n💳 *Payment Prompt Sent!* Please enter your M-Pesa PIN on your phone screen to complete application."

            send_whatsapp_message(sender, clean_reply)
            return {"status": "received"}

        # 4. HANDLE IMAGE TAG
        image_match = re.search(r"\[IMAGE:\s*(https?://[^\s\]]+)\]", reply)
        if image_match:
            image_url = image_match.group(1)
            clean_reply = re.sub(r"\[IMAGE:\s*https?://[^\s\]]+\]", "", reply).strip()
            send_whatsapp_image(sender, image_url, caption=clean_reply)
        else:
            send_whatsapp_message(sender, reply)

        logger.info(f"🤖 [AI Reply Sent] To {sender}")
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Webhook Processing Error: {e}")
        return {"status": "error", "message": str(e)}


# --------------------------------------------------
# PAYMENT ENDPOINTS
# --------------------------------------------------

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


# --------------------------------------------------
# DASHBOARD ENDPOINTS
# --------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse)
async def seller_dashboard(request: Request):
    try:
        orders = db.get_all_orders()
        products = db.get_all_products()
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={"orders": orders, "products": products},
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