import os
import re
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ai_salesman import generate_intelligent_reply
import database as db
from paystack import PaystackManager

load_dotenv(override=True)

app = FastAPI()

# Setup Templates Directory
templates = Jinja2Templates(directory="templates")

# Fallback default added so verification works even if ENV isn't set
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "chatseller_test_123").strip()
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "").strip()

# Initialize Paystack Payment Engine
paystack_client = PaystackManager()

# --------------------------------------------------
# STARTUP CHECK
# --------------------------------------------------

print("========================================")
print("ChatSeller starting...")
print("PHONE_NUMBER_ID:", PHONE_NUMBER_ID)
print("ACCESS TOKEN LOADED:", bool(ACCESS_TOKEN))
print("VERIFY TOKEN LOADED:", bool(VERIFY_TOKEN))
print("VERIFY TOKEN VALUE:", VERIFY_TOKEN)
print("========================================")


@app.get("/")
def home():
    return {"status": "ChatSeller is running"}


# --------------------------------------------------
# META WEBHOOK VERIFICATION (FIXED)
# --------------------------------------------------


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    print("\n--- WEBHOOK VERIFICATION REQUEST ---")
    print("Mode:", mode)
    print("Token received from Meta:", token)
    print("Expected VERIFY_TOKEN:", VERIFY_TOKEN)

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Verification successful!")
        # Must return ONLY the plain text challenge with 200 OK
        return Response(content=challenge, media_type="text/plain", status_code=200)

    print("Verification failed! Token mismatch or bad mode.")
    return Response(content="Verification failed", status_code=403)


# --------------------------------------------------
# SEND WHATSAPP MESSAGES (TEXT & IMAGE)
# --------------------------------------------------


def send_whatsapp_message(recipient, message):
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
        response = requests.post(
            url, headers=headers, json=payload, timeout=30
        )
        print("\n--- WHATSAPP API RESPONSE ---")
        print("Status:", response.status_code)
        print("Response:", response.text)
        return response
    except Exception as e:
        print("\n--- WHATSAPP API ERROR ---", str(e))
        return None


def send_whatsapp_image(recipient: str, image_url: str, caption: str = ""):
    """Sends an image message with an optional text caption via WhatsApp API."""
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
        response = requests.post(
            url, headers=headers, json=payload, timeout=30
        )
        print("\n--- WHATSAPP IMAGE RESPONSE ---")
        print("Status:", response.status_code)
        print("Response:", response.text)
        return response
    except Exception as e:
        print("\n--- WHATSAPP IMAGE ERROR ---", str(e))
        return None


# --------------------------------------------------
# RECEIVE WHATSAPP WEBHOOK
# --------------------------------------------------


@app.post("/webhook")
async def receive_webhook(request: Request):
    print("\n========================================")
    print("INCOMING WEBHOOK")
    print("========================================")

    try:
        data = await request.json()
        print("\n--- RAW WEBHOOK PAYLOAD ---")
        print(data)

        entry = data.get("entry", [])
        if not entry:
            return {"status": "received"}

        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "received"}

        value = changes[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "received"}

        message = messages[0]
        sender = message.get("from")
        message_type = message.get("type")

        if message_type != "text":
            print("Message is not text. Ignoring.")
            return {"status": "received"}

        message_body = message.get("text", {}).get("body", "")
        print(f"Customer ({sender}): {message_body}")

        # --------------------------------------------------
        # GENERATE AI SALES RESPONSE & HANDLE ORDERS / IMAGES
        # --------------------------------------------------
        reply = generate_intelligent_reply(sender, message_body)

        # 1. Check for Order Tag
        order_match = re.search(
            r"\[ORDER:\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.*?)\]", reply
        )
        if order_match:
            p_id = int(order_match.group(1))
            qty = int(order_match.group(2))
            addr = order_match.group(3).strip()

            order_res = db.create_order(sender, p_id, qty, addr)

            if order_res["success"]:
                clean_reply = re.sub(r"\[ORDER:.*?\]", "", reply).strip()
                summary_msg = (
                    f"{clean_reply}\n\n"
                    f"📋 *Order Summary* #{order_res['order_id']}\n"
                    f"• Item: {order_res['product_name']}\n"
                    f"• Total: KSh {order_res['total_price']:,.0f}\n"
                    f"• Address: {order_res['address']}"
                )

                # TRIGGER AUTOMATIC PAYSTACK STK PUSH
                pay_res = paystack_client.trigger_mpesa_stk_push(
                    phone_number=sender, amount=order_res["total_price"]
                )

                if pay_res.get("status"):
                    ref = pay_res["data"]["reference"]
                    db.save_payment_reference(order_res["order_id"], ref)
                    summary_msg += "\n\n💳 *Payment Prompt Sent!* Please check your phone to enter your M-Pesa PIN."

                send_whatsapp_message(sender, summary_msg)
                return {"status": "received"}

        # 2. Check for Image Tag
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

        return {"status": "received"}

    except Exception as e:
        print("\n--- WEBHOOK ERROR ---", str(e))
        return {"status": "error", "message": str(e)}


# --------------------------------------------------
# PAYSTACK PAYMENT ENDPOINTS
# --------------------------------------------------


@app.post("/api/pay")
async def trigger_payment(request: Request):
    """Trigger payment manually or via HTTP test calls."""
    try:
        data = await request.json()
        phone = data.get("phone")
        amount = data.get("amount")
        order_id = data.get("order_id")

        res = paystack_client.trigger_mpesa_stk_push(
            phone_number=phone, amount=amount
        )

        if res.get("status"):
            reference = res["data"]["reference"]
            db.save_payment_reference(order_id, reference)
            return JSONResponse(
                content={
                    "status": True,
                    "message": "STK Push sent to phone!",
                    "reference": reference,
                },
                status_code=200,
            )

        return JSONResponse(
            content={
                "status": False,
                "message": res.get("message", "Payment initiation failed"),
            },
            status_code=400,
        )
    except Exception as e:
        return JSONResponse(
            content={"status": False, "error": str(e)}, status_code=500
        )


@app.post("/paystack/webhook")
async def paystack_webhook(request: Request):
    """Receives automated payment notifications from Paystack."""
    try:
        payload = await request.json()
        event = payload.get("event")

        if event == "charge.success":
            reference = payload.get("data", {}).get("reference")
            if reference:
                db.mark_order_as_paid(reference)

        return JSONResponse(content={"status": "success"}, status_code=200)
    except Exception as e:
        print("\n--- PAYSTACK WEBHOOK ERROR ---", str(e))
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
    """Adds a new product directly into products.db."""
    db.add_product(name, price, description, image_url)
    return RedirectResponse(url="/dashboard", status_code=303)