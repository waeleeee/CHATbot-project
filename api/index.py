import os
import csv
import json
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, Request, Response, status, BackgroundTasks

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


PRODUCTS_CONTEXT = load_products_context()
print(f"[+] Loaded product catalog with {len(PRODUCTS_CONTEXT.split(chr(10)))} lines")


# ==========================================
# 2. Send WhatsApp Message
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
            print(f"[+] WhatsApp sent: {response.status_code}")
    except Exception as e:
        print(f"[-] WhatsApp send error: {str(e)}")


# ==========================================
# 3. Call KIE GPT-5.2 AI
# ==========================================
async def call_kie_ai(user_message: str, contact_name: str) -> str:
    system_prompt = f"""You are a helpful WhatsApp sales assistant. Your job is to help customers find products and answer their questions.
Reply in the SAME language the user writes in (Tunisian Arabic dialect, French, or English).
Be friendly, concise, and helpful.

{PRODUCTS_CONTEXT}

If a product is not in the catalog, say it is not available and suggest the closest alternative.
"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    "reasoning_effort": "low"  # faster response!
                }
            )
            if res.status_code == 200:
                data = res.json()
                reply = data["choices"][0]["message"]["content"]
                print(f"[+] KIE reply received")
                return reply
            else:
                print(f"[-] KIE error: {res.status_code} {res.text[:100]}")
    except Exception as e:
        print(f"[-] KIE call error: {str(e)}")

    return f"Marhba {contact_name}! Sorry, AI is temporarily busy. Please try again in a moment."


# ==========================================
# 4. Background: Process & Reply
# ==========================================
async def process_and_reply(sender: str, contact_name: str, text: str):
    print(f"[BG] Processing from {contact_name} ({sender}): {text}")
    ai_reply = await call_kie_ai(text, contact_name)
    await send_whatsapp_message(sender, ai_reply)
    print(f"[BG] Done - replied to {sender}")


# ==========================================
# 5. Webhook Verification
# ==========================================
def handle_verify(hub_mode, hub_verify_token, hub_challenge):
    print(f"[*] Verification: mode={hub_mode}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("[+] Webhook verified!")
        return Response(content=str(hub_challenge), media_type="text/plain", status_code=200)
    raise HTTPException(status_code=403, detail="Token mismatch")


# ==========================================
# 6. Receive Messages
# ==========================================
async def handle_post_message(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    for item in body.get("entry", []):
        for change in item.get("changes", []):
            value = change.get("value", {})
            contacts = value.get("contacts", [])
            contact_name = contacts[0].get("profile", {}).get("name", "Client") if contacts else "Client"

            for message in value.get("messages", []):
                sender = message.get("from")
                msg_type = message.get("type")
                print(f"[MSG] {contact_name} ({sender}): type={msg_type}")

                if msg_type == "text":
                    text_body = message.get("text", {}).get("body", "")
                    print(f"[MSG] Text: {text_body}")
                    # Use background task so Meta gets 200 OK immediately
                    # while AI reply is being processed
                    background_tasks.add_task(process_and_reply, sender, contact_name, text_body)

    return {"status": "ok"}


# ==========================================
# 7. Main Router
# ==========================================
@app.api_route("/{path_name:path}", methods=["GET", "POST", "HEAD"])
async def route_all(request: Request, background_tasks: BackgroundTasks, path_name: str = ""):
    if request.method in ("GET", "HEAD"):
        hub_mode = request.query_params.get("hub.mode")
        hub_verify_token = request.query_params.get("hub.verify_token")
        hub_challenge = request.query_params.get("hub.challenge")
        if hub_mode or hub_challenge:
            return handle_verify(hub_mode, hub_verify_token, hub_challenge)
        return {
            "status": "WhatsApp AI Chatbot running",
            "ai": "KIE GPT-5.2",
            "products": len(PRODUCTS_CONTEXT.split("\n")) - 1
        }
    if request.method == "POST":
        return await handle_post_message(request, background_tasks)
