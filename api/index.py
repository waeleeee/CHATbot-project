import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, Request, Response, status

# Load environment variables from .env
load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "wael_secret_token_2026")

app = FastAPI(title="WhatsApp Cloud API Webhook", version="1.0.0", redirect_slashes=False)


# ==========================================
# 1. Webhook Verification Handler
# ==========================================
def handle_verify(hub_mode: str, hub_verify_token: str, hub_challenge: str):
    print(f"[*] Verification request received - Mode: {hub_mode}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("[+] Webhook verified successfully!")
        return Response(content=str(hub_challenge), media_type="text/plain", status_code=status.HTTP_200_OK)
    
    print("[-] Webhook verification failed. Token mismatch.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


# ==========================================
# 2. Receive Incoming Messages Handler
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


# Catch-all router to handle all paths and rewrites seamlessly on Vercel
@app.api_route("/{path_name:path}", methods=["GET", "POST", "HEAD"])
async def route_all(request: Request, path_name: str = ""):
    if request.method == "GET" or request.method == "HEAD":
        hub_mode = request.query_params.get("hub.mode")
        hub_verify_token = request.query_params.get("hub.verify_token")
        hub_challenge = request.query_params.get("hub.challenge")
        
        # If this is Meta's verification handshake
        if hub_mode or hub_verify_token or hub_challenge:
            return handle_verify(hub_mode, hub_verify_token, hub_challenge)
            
        return {
            "status": "WhatsApp Webhook is running",
            "message": "Backend is live and healthy"
        }
    
    if request.method == "POST":
        return await handle_post_message(request)
