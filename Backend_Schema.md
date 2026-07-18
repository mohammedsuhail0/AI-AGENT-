# Backend Schema & Data Formats

This document describes the structured schemas, payloads, and validation constraints for the serverless backend.

---

## 1. Gemini AI Structured JSON Output
To ensure the Python script can reliably parse Gemini's output, we use Gemini's **Structured Outputs** feature (passing a Pydantic schema or JSON schema).

### Schema (JSON Schema format)
```json
{
  "type": "object",
  "properties": {
    "category": {
      "type": "string",
      "enum": ["URGENT", "INFO", "SPAM"]
    },
    "urgency_score": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5
    },
    "reasoning": {
      "type": "string",
      "description": "Brief explanation for the category decision."
    },
    "draft_reply": {
      "type": "string",
      "description": "A draft reply in English. Leave empty if category is SPAM or INFO."
    }
  },
  "required": ["category", "urgency_score", "reasoning", "draft_reply"]
}
```

---

## 2. Telegram Callback Data Schema
**⚠️ Critical Constraint:** Telegram's `callback_data` field on inline keyboard buttons has a strict limit of **64 bytes**. 

If we try to store the draft or a long thread ID directly inside the button click payload, it will fail. Instead, we use a compact identifier layout:

```text
[Action]:[ThreadID]
```

### Callback Data Formats:
*   **Approve & Send:** `app:18f3a6b2c7e101f3` (Total: ~20 bytes)
*   **Ignore & Archive:** `ign:18f3a6b2c7e101f3` (Total: ~20 bytes)
*   **Edit Draft:** `edt:18f3a6b2c7e101f3` (Total: ~20 bytes)

*How n8n/Vercel handles this:* When Vercel receives `app:18f3a6b2c7e101f3`, it:
1. Fetches the email thread from Gmail using the `threadId` (`18f3a6b2c7e101f3`).
2. Re-runs Gemini to generate the draft reply (or reads the draft stored in Telegram's message itself using parsing). **Parsing from the Telegram message text is free and requires no database!**

---

## 3. Gmail API Reply Payload Schema
When replying to an email thread, the API payload must conform to RFC 822 headers to keep the reply grouped in the same thread.

### RFC 822 Reply Headers:
```text
To: sender@external.com
Subject: Re: Original Subject
Thread-Id: 18f3a6b2c7e101f3
In-Reply-To: <original-message-id@mail.gmail.com>
References: <original-message-id@mail.gmail.com>

This is the text body of the reply.
```

### Gmail send API request structure:
```json
{
  "raw": "Base64URLEncodedStringOfRFC822Message",
  "threadId": "18f3a6b2c7e101f3"
}
```

---

## 4. Local State (GitHub Artifacts / Cache)
To log statistics or create the daily digest, the polling script stores a temporary log in the GitHub workflow directory.
* **File:** `digest_cache.json`
* **Schema:**
```json
{
  "date": "2026-07-17",
  "digests": [
    {
      "sender": "academic@college.edu",
      "subject": "Time Table Update",
      "summary": "Final exams start Nov 3rd."
    }
  ]
}
```
This cache is cleared after the 8:00 PM daily digest is sent.
