import os
import json
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, Request, Response, BackgroundTasks, status

# Load environment variables
load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "wael_secret_token_2026")
KIE_API_KEY = os.getenv("KIE_API_KEY", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")

app = FastAPI(title="WhatsApp Cloud API Webhook", version="1.0.0", redirect_slashes=False)


# ==========================================
# 1. Helper: Send WhatsApp Message
# ==========================================
async def send_whatsapp_message(recipient_number: str, message_text: str):
    """
    Sends a WhatsApp text message to a user via Meta Graph API.
    """
    if not WHATSAPP_PHONE_NUMBER_ID or not WHATSAPP_ACCESS_TOKEN:
        print("[-] Missing WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN.")
        return

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
            if response.status_code == 200:
                print(f"[+] Message sent successfully to {recipient_number}: {message_text}")
            else:
                print(f"[-] Failed to send message: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[-] Error sending WhatsApp message: {str(e)}")


# ==========================================
# 2. Helper: AI Reply Generation
# ==========================================
async def generate_ai_reply(user_message: str, contact_name: str) -> str:
    """
    Generates an AI response using KIE API or intelligent chatbot fallback.
    """
    # If KIE API key is provided, try calling KIE / OpenAI endpoint
    if KIE_API_KEY:
        try:
            # Standard OpenAI/KIE compatible chat completion
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",  # Can be updated to custom KIE endpoint
                    headers={
                        "Authorization": f"Bearer {KIE_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are a helpful and polite WhatsApp assistant. Reply in the same language the user speaks (Arabic, French, or English). Keep answers concise and friendly."},
                            {"role": "user", "content": user_message}
                        ]
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[i] Note on KIE AI call: {str(e)}")

    # Friendly default conversational reply if AI endpoint is not custom routed yet
    return f"3aslema {contact_name}! 🤖 Mar7ba bik fi chatbot WhatsApp mte3na. Waslatni rseltek: \"{user_message}\" w el backend mrigel 100%!"


# ==========================================
# 3. Process Incoming Message in Background
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
async def handle_post_message(request: Request, background_tasks: BackgroundTasks):
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
            contact_name = contacts[0].get("profile", {}).get("name", "User") if contacts else "User"

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
                    # Dispatch background reply task
                    background_tasks.add_task(process_and_reply, sender, contact_name, text_body)

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
async def route_all(request: Request, background_tasks: BackgroundTasks, path_name: str = ""):
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
        return await handle_post_message(request, background_tasks)
