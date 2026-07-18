# App Flow & Workflows

This document outlines the operational workflows of the agent. There are two primary asynchronous loops:
1. **The Polling Loop (GitHub Actions):** Scans and categorizes emails.
2. **The Approval Callback Loop (Vercel):** Handles user button taps and sends the draft.

---

## 1. Flow A: The Polling Loop (Every 15 Minutes)

This flow runs headlessly in the background via GitHub Actions.

```mermaid
sequenceDiagram
    autonumber
    participant GH as GitHub Actions Cron
    participant Gmail as Gmail API
    participant Cal as Google Calendar API
    participant Gemini as Gemini AI API
    participant Bot as Telegram Bot API

    GH->>Gmail: Authenticate & Query (is:unread -label:AI-Scanned)
    alt No new emails found
        GH->>GH: Terminate execution (save minutes)
    else New emails found
        loop For each email
            GH->>Gmail: Apply 'AI-Scanned' label
            GH->>Gmail: Fetch Full Email Body & Metadata
            alt Email contains date/scheduling query
                GH->>Cal: Fetch events (Next 3 Days)
                Cal-->>GH: Return calendar schedules
            else No scheduling query
                GH->>GH: Set calendar context to [Empty]
            end
            GH->>Gemini: Send (Email Content + Calendar Context + Resume Context)
            Gemini-->>GH: Return JSON (Category, Reason, DraftReply)
            
            alt Category == 'URGENT'
                GH->>Bot: Send Alert Message + Inline Keyboard Buttons
            else Category == 'INFO'
                GH->>GH: Append to local Daily Digest log
            end
        end
    end
```

---

## 2. Flow B: The Webhook Approval Loop (Instant Action)

This flow is triggered when you tap a button in your Telegram app. The Telegram server sends a webhook request to Vercel.

```mermaid
sequenceDiagram
    autonumber
    actor User as You (on Telegram app)
    participant TeleAPI as Telegram Bot API
    participant Vercel as Vercel Serverless Function
    participant Gmail as Gmail API

    User->>TeleAPI: Tap [ ✅ Approve & Send ] button
    TeleAPI->>Vercel: Forward Webhook (CallbackQuery with callback_data)
    Note over Vercel: Parse data (thread_id, draft_text)
    
    Vercel->>Gmail: Refresh OAuth Token
    Vercel->>Gmail: Send Email (using threadId to reply inline)
    
    alt Send Success (HTTP 200)
        Vercel->>TeleAPI: Update Telegram Message (Remove buttons, update text to "Sent")
    else Send Failure
        Vercel->>TeleAPI: Update Telegram Message (Add "❌ Error: Failed to send")
    end
    Vercel-->>TeleAPI: Return HTTP 200 OK (Acknowledge Callback)
```

---

## 3. Edge Cases & Error Flow
* **OAuth Token Expires:** If the `GOOGLE_REFRESH_TOKEN` is revoked or invalid, the script sends an emergency Telegram message: *"⚠️ Error: Gmail API disconnected. Please run local setup to renew OAuth tokens."*
* **Gemini Free Tier Exhausted:** If rate limited, the Python script catches the error, sleeps for 10 seconds, and retries. If it fails 3 times, it alerts Telegram: *"⚠️ Gemini API rate limit hit. Skipping scan. Will retry in 15 minutes."*
* **Double Clicks on Telegram:** If the user clicks `[ Approve & Send ]` twice, the serverless webhook checks if the draft was already sent (by checking the state or Telegram message text). If yes, it ignores the second click to prevent duplicate emails from being sent to the recipient.
