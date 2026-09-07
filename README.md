# WhatsApp Cloud API Webhook (FastAPI)

A lightweight and clean FastAPI backend designed to verify and receive webhooks from Meta's WhatsApp Cloud API. Ready for local testing and direct deployment to Vercel.

---

## 📁 Project Structure

```text
whatsapp-webhook/
├── api/
│   └── index.py         # Main FastAPI webhook application
├── .env                 # Secret environment variables (VERIFY_TOKEN)
├── requirements.txt     # Python dependencies
├── vercel.json          # Vercel serverless routing configuration
└── README.md
```

---

## 🚀 How to Run Locally

### 1. Install Dependencies
Open PowerShell or Command Prompt inside the `whatsapp-webhook` directory:

```bash
pip install -r requirements.txt
```

### 2. Start the FastAPI Server
```bash
uvicorn api.index:app --reload --port 8000
```
Your server is now active at: `http://localhost:8000`

---

## 🌐 Exposing Locally with ngrok

Since Meta requires a public HTTPS URL to send webhooks:

1. In a separate terminal window, run:
   ```bash
   ngrok http 8000
   ```
2. Copy the generated HTTPS forwarding URL (e.g., `https://xxxx-xx-xx.ngrok-free.app`).
3. In Meta Developer Dashboard:
   - **Callback URL**: `https://xxxx-xx-xx.ngrok-free.app/webhook`
   - **Verify Token**: Must match `VERIFY_TOKEN` in your `.env` file (`your_custom_secret_verify_token`).

---

## ☁️ Deploying to Vercel

1. Push this folder to a GitHub repository.
2. Go to [Vercel](https://vercel.com) and click **Add New Project** > **Import**.
3. Under **Environment Variables**, add:
   - **Key**: `VERIFY_TOKEN`
   - **Value**: `your_custom_secret_verify_token` (or whatever secret token you prefer).
4. Click **Deploy**.
5. Update your Meta Webhook URL to:
   `https://<your-project-name>.vercel.app/webhook`
