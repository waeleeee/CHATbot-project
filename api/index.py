import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, Request, Response, status

# Load environment variables from .env
load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "your_custom_secret_verify_token")

app = FastAPI(title="WhatsApp Cloud API Webhook", version="1.0.0")


@app.get("/")
def root():
    return {"status": "WhatsApp Webhook is running"}


# ==========================================
# 1. Webhook Verification (GET endpoint)
# ==========================================
@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Handles the verification handshake when configuring the Webhook in Meta Developer Dashboard.
    Meta expects hub.challenge returned as plain text with 200 OK.
    """
    print(f"[*] Verification request received - Mode: {hub_mode}")

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("[+] Webhook verified successfully!")
        # Must return the challenge directly as plain text
        return Response(content=hub_challenge, media_type="text/plain", status_code=status.HTTP_200_OK)
    
    print("[-] Webhook verification failed. Token mismatch.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


# ==========================================
# 2. Receive Incoming Messages (POST endpoint)
# ==========================================
@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Receives incoming WhatsApp webhook payloads (messages, status updates, reactions).
    Always returns 200 OK immediately so Meta does not retry delivery.
    """
    try:
        body = await request.json()
    except Exception:
        # Return 200 even for invalid JSON to prevent webhook disablement
        return {"status": "ignored"}

    # Extract WhatsApp payload hierarchy
    entry = body.get("entry", [])
    if not entry:
        return {"status": "no_entry"}

    for item in entry:
        for change in item.get("changes", []):
            value = change.get("value", {})

            # 1. Check for incoming messages
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

                # Extract Text Content
                if msg_type == "text":
                    text_body = message.get("text", {}).get("body", "")
                    print(f"  Message Text : {text_body}")
                elif msg_type == "interactive":
                    interactive_type = message.get("interactive", {}).get("type")
                    print(f"  Interactive ({interactive_type}): {message.get('interactive')}")
                else:
                    print(f"  Payload      : {json.dumps(message, indent=2)}")

                print("=" * 50 + "\n")

            # 2. Check for message statuses (sent, delivered, read)
            statuses = value.get("statuses", [])
            for msg_status in statuses:
                status_name = msg_status.get("status")
                recipient_id = msg_status.get("recipient_id")
                print(f"[i] Message status update: '{status_name}' for {recipient_id}")

    # Meta requires a 200 OK response within a few seconds
    return {"status": "ok"}
