import os
import csv
import json
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status

load_dotenv()

VERIFY_TOKEN        = os.getenv("VERIFY_TOKEN", "wael_secret_token_2026")
KIE_API_KEY         = os.getenv("KIE_API_KEY", "401c276f82c61ade9b9a6e70df2e33cd")
PHONE_NUMBER_ID     = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1330678653455611")
ACCESS_TOKEN        = os.getenv("WHATSAPP_ACCESS_TOKEN",
    "EAAZAmTJHgOd0BSfkIIBymGZBemelNaRwN9p5pXgZBZAfIlDDvfG04nechwZBHnVOyfuvnZABV1SwIx6MtTv5wYFXCzzX9pLgarVXvAJujyn3oIhnKlaYWWHREZANBptSZBesGDodZAaN4Ro7hE3Io5S5ZBwvgf6OP83e5ZB8b6D6ZAzTGxdJaCDsA6FxkZAKEKOBNlOuho4zZCo7UmYdXY5wF09YY705Tm5bNiBwSTsQM5Vt8D6gUAO45J6DiWkHZAR6PNjU6WkFu3EP8Sbo2ZBn550NNMON")

app = FastAPI(title="WhatsApp AI Chatbot", version="3.0.0", redirect_slashes=False)


# ── Load products CSV once ────────────────────────────────────────────────────
def load_products() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "products.csv")
    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        lines = ["Product catalog:\n"]
        for r in rows:
            lines.append(f"- {r['nom']} | Prix: {r['prix']} | {r['description']} | Stock: {r['stock']}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[!] CSV load error: {e}")
        return "No product catalog available."

PRODUCTS = load_products()
print(f"[+] Products loaded: {len(PRODUCTS.splitlines())} lines")


# ── Send WhatsApp message ─────────────────────────────────────────────────────
async def send_whatsapp(to: str, text: str):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "recipient_type": "individual",
                  "to": to, "type": "text", "text": {"body": text, "preview_url": False}}
        )
        print(f"[WA] sent → {to}: {r.status_code}")


# ── Call KIE GPT-5.2 ──────────────────────────────────────────────────────────
async def ask_kie(user_msg: str, name: str) -> str:
    system = (
        "You are a helpful WhatsApp sales assistant. "
        "Always reply in the SAME language as the user (Tunisian Arabic, French, or English). "
        "Be friendly and concise.\n\n" + PRODUCTS
    )
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.kie.ai/gpt-5-2/v1/chat/completions",
                headers={"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"},
                json={
                    "messages": [
                        {"role": "system",  "content": [{"type": "text", "text": system}]},
                        {"role": "user",    "content": [{"type": "text", "text": user_msg}]}
                    ],
                    "reasoning_effort": "low"
                }
            )
        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"]
            print(f"[KIE] reply ready ({len(reply)} chars)")
            return reply
        print(f"[KIE] error {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[KIE] exception: {e}")
    return f"Marhba {name}! Service temporarily unavailable, please try again."


# ── Webhook verification ──────────────────────────────────────────────────────
def verify(mode, token, challenge):
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("[+] Webhook verified")
        return Response(content=str(challenge), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token mismatch")


# ── Main router ───────────────────────────────────────────────────────────────
@app.api_route("/{path:path}", methods=["GET", "POST", "HEAD"])
async def router(request: Request, path: str = ""):

    # ── GET: Meta verification handshake
    if request.method in ("GET", "HEAD"):
        p = request.query_params
        if p.get("hub.mode"):
            return verify(p.get("hub.mode"), p.get("hub.verify_token"), p.get("hub.challenge"))
        return {"status": "WhatsApp AI Chatbot running", "ai": "KIE GPT-5.2",
                "products": len(PRODUCTS.splitlines()) - 1}

    # ── POST: incoming WhatsApp messages
    try:
        body = await request.json()
        print(f"[POST] {json.dumps(body)[:200]}")
    except Exception:
        return {"status": "ignored"}

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value   = change.get("value", {})
            msgs    = value.get("messages", [])
            contacts= value.get("contacts", [])
            name    = contacts[0]["profile"]["name"] if contacts else "Client"

            for msg in msgs:
                sender   = msg.get("from")
                msg_type = msg.get("type")
                print(f"[MSG] {name} ({sender}) type={msg_type}")

                if msg_type == "text":
                    text = msg["text"]["body"]
                    print(f"[MSG] '{text}'")
                    reply = await ask_kie(text, name)
                    await send_whatsapp(sender, reply)

    return {"status": "ok"}
