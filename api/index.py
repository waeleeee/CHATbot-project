import os
import csv
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

app = FastAPI(title="WhatsApp AI Chatbot", version="2.0.0", redirect_slashes=False)


# ==========================================
# 1. Load Products from CSV
# ==========================================
def load_products_context() -> str:
    """
    Reads products.csv and returns it as a formatted string context for the AI.
    """
    products_path = os.path.join(os.path.dirname(__file__), "..", "products.csv")
    
    try:
        with open(products_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return "No products available."

        lines = ["Here is the product catalog:\n"]
        for row in rows:
            lines.append(
                f"- {row['nom']} | Prix: {row['prix']} | Description: {row['description']} | Stock: {row['stock']}"
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"[!] Could not load products.csv: {e}")
        return "Product catalog is currently unavailable."


# Load products once at startup
PRODUCTS_CONTEXT = load_products_context()
print(f"[+] Loaded product catalog:\n{PRODUCTS_CONTEXT}")


# ==========================================
# 2. Helper: Send WhatsApp Message
# ==========================================
async def send_whatsapp_message(recipient_number: str, message_text: str):
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
        "text": {"preview_url": False, "body": message_text}
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            print(f"[+] WhatsApp sent to {recipient_number}: {response.status_code}")
    except Exception as e:
        print(f"[-] Error sending WhatsApp message: {str(e)}")


# ==========================================
# 3. Helper: Call KIE GPT-5.2 AI
# ==========================================
async def call_kie_ai(user_message: str, contact_name: str) -> str:
    """
    Sends user message to KIE GPT-5.2 with product context and returns AI reply.
    """
    system_prompt = f"""You are a helpful WhatsApp sales assistant. Answer questions about products from the catalog below.
Be friendly, concise, and answer in the same language the user writes in (Arabic dialect, French, or English).
If the user asks about a product not in the catalog, politely say it is not available.

{PRODUCTS_CONTEXT}
"""
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(
                "https://api.kie.ai/gpt-5-2/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {KIE_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": [{"type": "text", "text": system_prompt}]
                        },
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": user_message}]
                        }
                    ],
                    "reasoning_effort": "high"
                }
            )

            if res.status_code == 200:
                data = res.json()
                reply = data["choices"][0]["message"]["content"]
                print(f"[+] KIE GPT-5.2 reply generated")
                return reply
            else:
                print(f"[-] KIE API error: {res.status_code} - {res.text}")
                return f"Marhba {contact_name}! Sorry, the AI is temporarily unavailable. Please try again."

    except Exception as e:
        print(f"[-] KIE AI call failed: {str(e)}")
        return f"Marhba {contact_name}! Sorry, I encountered an error. Please try again."


# ==========================================
# 4. Process Incoming Message & Reply
# ==========================================
async def process_and_reply(sender: str, contact_name: str, incoming_text: str):
    print(f"[*] Processing message from {contact_name} ({sender}): '{incoming_text}'")
    ai_response = await call_kie_ai(incoming_text, contact_name)
    await send_whatsapp_message(sender, ai_response)


# ==========================================
# 5. Webhook Verification Handler
# ==========================================
def handle_verify(hub_mode: str, hub_verify_token: str, hub_challenge: str):
    print(f"[*] Verification request received - Mode: {hub_mode}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("[+] Webhook verified successfully!")
        return Response(content=str(hub_challenge), media_type="text/plain", status_code=status.HTTP_200_OK)
    print("[-] Webhook verification failed.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


# ==========================================
# 6. Receive Incoming Messages Handler
# ==========================================
async def handle_post_message(request: Request):
    try:
        body = await request.json()
        print(f"\n[WEBHOOK] Received: {json.dumps(body)[:200]}")
    except Exception as e:
        print(f"[-] JSON parse error: {e}")
        return {"status": "ignored"}

    entry = body.get("entry", [])
    if not entry:
        return {"status": "no_entry"}

    for item in entry:
        for change in item.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            contact_name = contacts[0].get("profile", {}).get("name", "Client") if contacts else "Client"

            for message in messages:
                sender = message.get("from")
                msg_type = message.get("type")
                print(f"\n[MSG] From: {contact_name} ({sender}) | Type: {msg_type}")

                if msg_type == "text":
                    text_body = message.get("text", {}).get("body", "")
                    print(f"[MSG] Content: {text_body}")
                    await process_and_reply(sender, contact_name, text_body)

    return {"status": "ok"}


# ==========================================
# 7. Main Router (Catch-All for Vercel)
# ==========================================
@app.api_route("/{path_name:path}", methods=["GET", "POST", "HEAD"])
async def route_all(request: Request, path_name: str = ""):
    if request.method in ("GET", "HEAD"):
        hub_mode = request.query_params.get("hub.mode")
        hub_verify_token = request.query_params.get("hub.verify_token")
        hub_challenge = request.query_params.get("hub.challenge")

        if hub_mode or hub_verify_token or hub_challenge:
            return handle_verify(hub_mode, hub_verify_token, hub_challenge)

        return {
            "status": "WhatsApp AI Chatbot is running",
            "ai_model": "KIE GPT-5.2",
            "products_loaded": len(PRODUCTS_CONTEXT.split("\n")) - 1
        }

    if request.method == "POST":
        return await handle_post_message(request)
