import os
import json
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, Request, Response, status

# Load environment variables
load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "wael_secret_token_2026")
KIE_API_KEY = os.getenv("KIE_API_KEY", "401c276f82c61ade9b9a6e70df2e33cd")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1330678653455611")
WHATSAPP_ACCESS_TOKEN = os.getenv(
    "WHATSAPP_ACCESS_TOKEN",
    "EAAZAmTJHgOd0BSVErocbnYroJZB0BYJxhSM2k5EJrieuds5MIcCSxfZCZCEgoNtBzZAxupZCkCnZAvZBl27TVzOShHyC569D6e74H1YMW4RwnGV3wuwZBvNlhRrw98RG1mn4sYsgpCbuWK5slpBiPSt0FVFCDwJZC45s25riLkADsJFyYNW1RkYDXdyoRlEmgTRypwp4AaaEeVLZCi12FGXozy6mA46K9jM0ZCbMJeiDrzNMd59fCt4ZCTzMX9wY5CsIyPQpFE2t3831O4MZCWUCe42l9w"
)

app = FastAPI(title="WhatsApp Cloud API Webhook", version="1.0.0", redirect_slashes=False)


# ==========================================
# 1. Helper: Send WhatsApp Message
# ==========================================
async def send_whatsapp_message(recipient_number: str, message_text: str):
    """
    Sends a WhatsApp text message to a user via Meta Graph API.
    """
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message_text
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            print(f"[+] WhatsApp API Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[-] Error sending WhatsApp message: {str(e)}")


# ==========================================
# 2. Helper: AI Reply Generation
# ==========================================
async def generate_ai_reply(user_message: str, contact_name: str) -> str:
    """
    Intelligent chatbot response.
    """
    lower_msg = user_message.lower()
    if "chkon" in lower_msg or "chkoun" in lower_msg:
        return f"3aslema {contact_name}! 🤖 Ena el Chatbot intelligent mte3ek fi WhatsApp, ma5doum b Python & FastAPI w connecte b l'AI!"
    elif "chtajm" in lower_msg or "chneya taaml" in lower_msg or "faserli" in lower_msg:
        return f"Najem njeweb el klyanat 24/7, nfasrelhom les services, n'enregistri les commandes, w n3awnek fi ay 7aja t7ebha! 🚀"
    else:
        return f"3aslema {contact_name}! 🤖 Jawbtini b: \"{user_message}\". Kifeh najem n3awnek?"


# ==========================================
# 3. Process Incoming Message
# ==========================================
async def process_and_reply(sender: str, contact_name: str, incoming_text: str):
    ai_response = await generate_ai_reply(incoming_text, contact_name)
    await send_whatsapp_message(sender, ai_response)


# ==========================================
# 4. Webhook Verification Handler
# ==========================================
def handle_verify(hub_mode: str, hub_verify_token: str, hub_challenge: str):
    print(f"[*] Verification request received - Mode: {hub_mode}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("[+] Webhook verified successfully!")
        return Response(content=str(hub_challenge), media_type="text/plain", status_code=status.HTTP_200_OK)
    
    print("[-] Webhook verification failed. Token mismatch.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


# ==========================================
# 5. Receive Incoming Messages Handler
# ==========================================
async def handle_post_message(request: Request):
    try:
        body = await request.json()
        print(f"\n[WEBHOOK RECEIVED] {json.dumps(body)}")
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return {"status": "ignored"}

    entry = body.get("entry", [])
    if not entry:
        return {"status": "no_entry"}

    for item in entry:
        for change in item.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            contact_name = contacts[0].get("profile", {}).get("name", "Wael") if contacts else "Wael"

            for message in messages:
                sender = message.get("from")
                msg_type = message.get("type")

                if msg_type == "text":
                    text_body = message.get("text", {}).get("body", "")
                    print(f"[*] Dispatching reply to {sender} for message: '{text_body}'")
                    await process_and_reply(sender, contact_name, text_body)

    return {"status": "ok"}


# Catch-all router
@app.api_route("/{path_name:path}", methods=["GET", "POST", "HEAD"])
async def route_all(request: Request, path_name: str = ""):
    if request.method in ("GET", "HEAD"):
        hub_mode = request.query_params.get("hub.mode")
        hub_verify_token = request.query_params.get("hub.verify_token")
        hub_challenge = request.query_params.get("hub.challenge")
        
        if hub_mode or hub_verify_token or hub_challenge:
            return handle_verify(hub_mode, hub_verify_token, hub_challenge)
            
        return {
            "status": "WhatsApp Webhook is running",
            "message": "Backend is live and healthy with auto-reply enabled!"
        }
    
    if request.method == "POST":
        return await handle_post_message(request)
