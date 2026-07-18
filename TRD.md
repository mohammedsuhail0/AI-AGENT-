# TRD — Technical Requirements Document

## 1. System Components & Tech Stack
The project will be built entirely using **Python** and lightweight serverless infrastructure to ensure it remains 100% free and zero-maintenance.

| Component | Platform | Technology | Cost |
| :--- | :--- | :--- | :--- |
| **Email Scanner** | GitHub Actions | Python (scheduled script) | Free ($0) |
| **Approval Webhook** | Vercel Serverless | Python (FastAPI / Serverless Functions) | Free ($0) |
| **AI Processing** | Google AI Studio | Gemini 1.5 Flash API | Free ($0) |
| **Notification Engine** | Telegram | Telegram Bot API | Free ($0) |
| **Email Service** | Google Cloud | Gmail API (OAuth 2.0) | Free ($0) |
| **Calendar Service** | Google Cloud | Google Calendar API (OAuth 2.0) | Free ($0) |

---

## 2. API Specifications & Integrations

### 2.1 Gmail API
* **Authentication:** OAuth 2.0. We will generate a **Refresh Token** locally once, and use it to obtain temporary Access Tokens programmatically on GitHub Actions and Vercel.
* **Scopes:**
  * `https://www.googleapis.com/auth/gmail.modify` (needed to read emails, modify labels, and send replies).
* **State Sync:** We will query `q="is:unread -label:AI-Scanned"`. After scanning, the script applies the `AI-Scanned` label.

### 2.2 Google Calendar API
* **Scopes:** `https://www.googleapis.com/auth/calendar.readonly`
* **Function:** Fetch events between `timeMin` (now) and `timeMax` (now + 3 days) to check availability.

### 2.3 Gemini API
* **SDK:** `google-generativeai` library.
* **Model:** `gemini-1.5-flash` (fast, cost-effective, and highly capable for text classification/drafting).
* **System Prompt:** Instructs the model to output a strict JSON structure containing the category, urgency rating, reasoning, and draft reply.

### 2.4 Telegram Bot API
* **BotFather Bot:** Created bot with custom commands.
* **Message Delivery:** `POST https://api.telegram.org/bot<TOKEN>/sendMessage`
* **Inline Keyboards:** Use `reply_markup` with `inline_keyboard` buttons passing callback data (e.g., `approve:<thread_id>` or `reject:<thread_id>`).
* **Webhook Register:** Point Telegram callbacks to Vercel: `https://<vercel-deployment-url>/api/telegram_webhook`.

---

## 3. Secret & Environment Variables Management
All credentials will be stored as Environment Variables (on Vercel) and Repository Secrets (on GitHub). **No credentials will be hardcoded in git.**

| Secret Variable | Description |
| :--- | :--- |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET`| OAuth 2.0 Client Secret from Google Cloud Console |
| `GOOGLE_REFRESH_TOKEN`| The long-lived refresh token generated during setup |
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your personal Telegram User ID (blocks unauthorized users) |
| `GEMINI_API_KEY` | Free API key from Google AI Studio |

---

## 4. Execution Constraints & Limits
* **Vercel Execution Limit:** Vercel's free serverless functions have a maximum execution timeout of 10 seconds. The webhook handler must complete within this window (fetching the draft, calling the Gmail send API, and responding).
* **GitHub Actions Limit:** Cron triggers on GitHub Actions are not exact (they may run 5-10 minutes late depending on queue size), which is acceptable for a 15-minute polling interval.
* **Gemini Free Tier Rate Limits:** 15 Requests per minute (RPM). The script will process emails sequentially or sleep briefly if checking multiple messages at once to stay under the limit.
