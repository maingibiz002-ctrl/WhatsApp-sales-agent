import logging
import os
import re
import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ai_salesman import generate_intelligent_reply
import database as db
from paystack import PaystackManager

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

logger.info(
    f"🚀 Server started | Phone ID: {PHONE_NUMBER_ID[:6]}... | Verify Token: Configured"
)


@app.get("/")
def home():
    return {"status": "ChatSeller is running"}


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


# --------------------------------------------------
# INCOMING WEBHOOK HANDLER
# --------------------------------------------------


@app.post("/webhook")
async def receive_webhook(request: Request):
    try:
        data = await request.json()

        # Extract entry and change payload cleanly
        entry = data.get("entry", [{}])[0]
        value = entry.get("changes", [{}])[0].get("value", {})

        # 1. SILENTLY IGNORE STATUS RECEIPTS (delivered, read, sent)
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

        # Clean Log: Displays only when an actual customer text arrives
        logger.info(f"📩 [Incoming] {sender}: '{message_body}'")

        # Generate AI response
        reply = generate_intelligent_reply(sender, message_body)

        # 2. HANDLE KRA APPLICATION / ORDER TAG
        kra_match = re.search(
            r"\[(?:KRA_APP|ORDER):\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\]",
            reply,
        )
        if kra_match:
            nat_id = kra_match.group(1).strip()
            dob = kra_match.group(2).strip()
            name = kra_match.group(3).strip()
            email = kra_match.group(4).strip()

            clean_reply = re.sub(
                r"\[(?:KRA_APP|ORDER):.*?\]", "", reply
            ).strip()

            logger.info(
                f"📝 [KRA Application Captured] Name: {name} | ID: {nat_id}"
            )

            # Trigger Payment Prompt (KSh 300)
            pay_res = paystack_client.trigger_mpesa_stk_push(
                phone_number=sender, amount=300.0
            )

            if pay_res.get("status"):
                ref = pay_res["data"]["reference"]
                clean_reply += "\n\n💳 *Payment Prompt Sent!* Please enter your M-Pesa PIN on your phone screen to start automatic processing."

            send_whatsapp_message(sender, clean_reply)
            return {"status": "received"}

        # 3. HANDLE IMAGE TAG
        image_match = re.search(
            r"\[IMAGE:\s*(https?://[^\s\]]+)\]", reply
        )
        if image_match:
            image_url = image_match.group(1)
            clean_reply = re.sub(
                r"\[IMAGE:\s*https?://[^\s\]]+\]", "", reply
            ).strip()
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
        return JSONResponse(
            content={"status": "error", "message": str(e)}, status_code=500
        )


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
        return HTMLResponse(
            content=f"<h2>Dashboard Load Error</h2><p><b>Error:</b> {e}</p>"
        )


@app.post("/dashboard/products/add")
async def add_product(
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    image_url: str = Form(""),
):
    db.add_product(name, price, description, image_url)
    return RedirectResponse(url="/dashboard", status_code=303)