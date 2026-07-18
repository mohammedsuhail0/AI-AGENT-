# Implementation Plan — Personal Email AI Agent

This document outlines the step-by-step implementation plan to build and deploy your personal email filtering agent.

---

## 1. Goal Description
Build a personal AI agent that runs a scheduled Python script on GitHub Actions to scan Gmail for urgent emails (scholarships, exam dates, placements), uses Gemini AI to draft replies, and pushes them to your phone via a Telegram bot. The bot features interactive buttons, backed by a Vercel serverless function, to allow you to approve and send replies instantly with a single tap.

---

## 2. User Review Required

> [!IMPORTANT]
> **Manual Actions Required by You:**
> 1. **Create a Telegram Bot:** You will need to message `@BotFather` on Telegram to generate a bot token.
> 2. **Google Cloud Credentials:** You will need to create a free project in the Google Cloud Console, enable the Gmail and Calendar APIs, download a `credentials.json` file, and run a local Python script (which I will provide) once to authenticate and generate a long-lived `refresh_token`.
> 3. **Environment Setup:** You will need to add these secret keys to your Vercel project and GitHub repository settings.

---

## 3. Open Questions
* **Resume/Context Text:** Do you have a short text summary of your background, resume highlights, or typical writing style that we should feed to Gemini so the draft replies sound like you? (We can add this later).
* **Calendar Integration:** Should we start with Gmail scanning first, and add the Google Calendar check in a subsequent phase? (Recommended to start simple).

---

## 4. Proposed Changes

We will create the project files in this directory.

### Component 1: Local Authentication Setup Helper

#### [NEW] [auth_helper.py](file:///C:/Users/Lenovo/OneDrive/ドキュメント/n8n%20prjects/auth_helper.py)
* A one-time script you run on your machine to log into your Google Account, authorize the app, and print the `GOOGLE_REFRESH_TOKEN` to your terminal.

---

### Component 2: Scanner (Runs on GitHub Actions)

#### [NEW] [check_emails.py](file:///C:/Users/Lenovo/OneDrive/ドキュメント/n8n%20prjects/check_emails.py)
* Fetches unread emails from Gmail.
* Skips emails already labeled `AI-Scanned`.
* Calls Gemini API to classify content and draft replies.
* Sends structured notifications with buttons to Telegram.
* Applies the `AI-Scanned` label to the processed emails.

#### [NEW] [requirements.txt](file:///C:/Users/Lenovo/OneDrive/ドキュメント/n8n%20prjects/requirements.txt)
* Declares standard dependencies: `google-auth-oauthlib`, `google-api-python-client`, `google-generativeai`, `requests`.

#### [NEW] [scan.yml](file:///C:/Users/Lenovo/OneDrive/ドキュメント/n8n%20prjects/.github/workflows/scan.yml)
* GitHub Actions workflow that installs Python, runs `check_emails.py` every 15 minutes, and caches the daily digest.

---

### Component 3: Webhook Server (Runs on Vercel Serverless)

#### [NEW] [telegram_webhook.py](file:///C:/Users/Lenovo/OneDrive/ドキュメント/n8n%20prjects/api/telegram_webhook.py)
* A FastAPI/Python serverless function entrypoint.
* Listens to incoming callback data from Telegram (e.g., `app:<thread_id>`).
* Refreshes Google access token, constructs the Gmail reply raw payload, and calls Gmail `send`.
* Updates the Telegram message to display "Sent!" or "Error" and removes the buttons.

#### [NEW] [vercel.json](file:///C:/Users/Lenovo/OneDrive/ドキュメント/n8n%20prjects/vercel.json)
* Configures Vercel to route all `/api/telegram_webhook` traffic to the Python serverless function.

---

## 5. Verification Plan

### Automated/Unit Testing
1. **Mock Scanner Test:** We will run `check_emails.py` locally using mock environment variables and a dummy email body to verify Gemini accurately returns the JSON category and reply draft.
2. **Local Webhook Test:** We will run the FastAPI server locally and use `curl` to send a fake Telegram callback payload to verify it processes OAuth tokens and sends emails correctly.

### Manual Verification
1. **Live Test Email:** Send an email from a secondary account to your scanning inbox (e.g., *"Subject: Scholarship Interview slot. Are you available on Tuesday?"*).
2. **Alert Check:** Verify you receive the Telegram push notification on your phone within 15 minutes (or trigger the action manually).
3. **Approve Check:** Tap `[ ✅ Approve & Send ]` on your phone and verify the secondary account receives the drafted reply, and the Telegram bot updates the message status.
