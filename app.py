import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")


@app.get("/")
def home():
    return {"status": "ChatSeller is running"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)

    return {"error": "Verification failed"}


@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()

    print("\n--- INCOMING WHATSAPP MESSAGE ---")
    print(data)

    return {"status": "received"}