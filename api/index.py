import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, Request, Response, status

# Load environment variables from .env
load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "your_custom_secret_verify_token")

app = FastAPI(title="WhatsApp Cloud API Webhook", version="1.0.0", redirect_slashes=False)


# ==========================================
# 1. Webhook Verification (GET endpoint)
# ==========================================
def handle_verify(hub_mode: str, hub_verify_token: str, hub_challenge: str):
    print(f"[*] Verification request received - Mode: {hub_mode}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("[+] Webhook verified successfully!")
        return Response(content=hub_challenge, media_type="text/plain", status_code=status.HTTP_200_OK)
    
    print("[-] Webhook verification failed. Token mismatch.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


# ==========================================
# 2. Receive Incoming Messages (POST endpoint)
# ==========================================
async def handle_post_message(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    entry = body.get("entry", [])
    if not entry:
        return {"status": "no_entry"}

    for item in entry:
        for change in item.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            contact_name = contacts[0].get("profile", {}).get("name", "Unknown") if contacts else "Unknown"

            for message in messages:
                sender = message.get("from")
                msg_type = message.get("type")
                msg_id = message.get("id")

                print("\n" + "=" * 50)
                print("[*] INCOMING WHATSAPP MESSAGE")
                print(f"  Contact Name : {contact_name}")
                print(f"  Sender Number: {sender}")
                print(f"  Message ID   : {msg_id}")
                print(f"  Type         : {msg_type}")

                if msg_type == "text":
                    text_body = message.get("text", {}).get("body", "")
                    print(f"  Message Text : {text_body}")
                elif msg_type == "interactive":
                    interactive_type = message.get("interactive", {}).get("type")
                    print(f"  Interactive ({interactive_type}): {message.get('interactive')}")
                else:
                    print(f"  Payload      : {json.dumps(message, indent=2)}")

                print("=" * 50 + "\n")

            statuses = value.get("statuses", [])
            for msg_status in statuses:
                status_name = msg_status.get("status")
                recipient_id = msg_status.get("recipient_id")
                print(f"[i] Message status update: '{status_name}' for {recipient_id}")

    return {"status": "ok"}


# Define all possible routes
@app.get("/")
@app.get("/api")
@app.get("/api/index")
def root():
    return {"status": "WhatsApp Webhook is running", "message": "Backend is live and healthy"}


@app.get("/webhook")
@app.get("/api/webhook")
@app.get("/api/index/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    return handle_verify(hub_mode, hub_verify_token, hub_challenge)


@app.post("/webhook")
@app.post("/api/webhook")
@app.post("/api/index/webhook")
async def receive_webhook(request: Request):
    return await handle_post_message(request)


# Catch-all router to handle any path format from Vercel
@app.api_route("/{path_name:path}", methods=["GET", "POST"])
async def catch_all(request: Request, path_name: str):
    # Normalize path
    clean_path = path_name.strip("/")
    
    if request.method == "GET":
        if "webhook" in clean_path:
            hub_mode = request.query_params.get("hub.mode")
            hub_verify_token = request.query_params.get("hub.verify_token")
            hub_challenge = request.query_params.get("hub.challenge")
            if hub_challenge:
                return handle_verify(hub_mode, hub_verify_token, hub_challenge)
        return {
            "status": "WhatsApp Webhook is running",
            "received_path": request.url.path,
            "path_name": path_name
        }
    
    if request.method == "POST":
        return await handle_post_message(request)
