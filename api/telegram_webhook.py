import os
import json
import base64
import requests
import re
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONEncoder
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from email.mime.text import MIMEText

app = FastAPI()

# Retrieve Env Secrets
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def get_gmail_service():
    """Refreshes the OAuth credentials and returns a Gmail API service client."""
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    creds.refresh(GoogleRequest())
    return build('gmail', 'v1', credentials=creds)

def extract_draft_from_message(text):
    """Parses the drafted reply out of the Telegram alert message block."""
    # Find text inside the markdown code block ```text ... ```
    pattern = r"```text\n(.*?)\n```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def send_gmail_reply(service, thread_id, draft_body):
    """Sends a reply back in the original Gmail thread, preserving headers."""
    # Fetch thread messages to find the parent Message-ID and Subject
    thread = service.users().threads().get(userId='me', id=thread_id).execute()
    messages = thread.get('messages', [])
    if not messages:
        raise Exception("Original email thread not found.")
        
    last_msg = messages[-1]
    headers = last_msg.get('payload', {}).get('headers', [])
    
    # Extract headers
    msg_id = ""
    subject = ""
    to_email = ""
    from_email = ""
    
    for h in headers:
        name = h['name'].lower()
        if name == 'message-id':
            msg_id = h['value']
        elif name == 'subject':
            subject = h['value']
        elif name == 'from':
            from_email = h['value']
        elif name == 'to':
            to_email = h['value']

    # Extract target email (reply to sender)
    # The 'From' header looks like "Sender Name <email@domain.com>" or just "email@domain.com"
    match = re.search(r'<(.*?)>', from_email)
    reply_to = match.group(1) if match else from_email

    # Standardize Subject line
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    # Build MIME RFC 822 Email Message
    msg = MIMEText(draft_body)
    msg['To'] = reply_to
    msg['Subject'] = subject
    msg['In-Reply-To'] = msg_id
    msg['References'] = msg_id
    
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    
    body = {
        'raw': raw_message,
        'threadId': thread_id
    }
    
    # Send using Gmail API
    result = service.users().messages().send(userId='me', body=body).execute()
    return result, reply_to

def edit_telegram_message(chat_id, message_id, status_text):
    """Updates the original Telegram alert message, removing inline keyboard buttons."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": status_text,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({"inline_keyboard": []}) # Remove keyboard
    }
    requests.post(url, json=payload)

@app.post("/api/telegram_webhook")
async def telegram_webhook(request: Request):
    """Entrypoint for Telegram callback_query webhook updates."""
    data = await request.json()
    
    # Check if this is a callback query update
    if "callback_query" not in data:
        return {"status": "ignored", "reason": "not a callback query"}

    callback = data["callback_query"]
    user_chat_id = str(callback["message"]["chat"]["id"])
    message_id = callback["message"]["message_id"]
    message_text = callback["message"]["text"]
    callback_data = callback["data"]
    
    # Security check: Ignore unauthorized users
    if user_chat_id != TELEGRAM_CHAT_ID:
        return {"status": "unauthorized"}

    # Parse Action and ThreadID from callback_data (e.g. app:18f3a6b2c7e101f3)
    parts = callback_data.split(":")
    if len(parts) != 2:
        return {"status": "error", "reason": "invalid callback data format"}
        
    action, thread_id = parts[0], parts[1]

    if action == "ign":
        # User clicked Ignore, just update Telegram UI
        new_text = f"❌ *Archived Alert (Ignored)*\n\n{message_text}"
        edit_telegram_message(user_chat_id, message_id, new_text)
        return {"status": "ignored"}

    elif action == "app":
        # Extract reply draft from Telegram message
        draft_reply = extract_draft_from_message(message_text)
        if not draft_reply:
            error_text = f"⚠️ *Error:* Could not extract draft reply from message.\n\n{message_text}"
            edit_telegram_message(user_chat_id, message_id, error_text)
            return {"status": "error", "reason": "draft parse failed"}

        # Attempt to reply using Gmail API
        try:
            gmail = get_gmail_service()
            _, recipient = send_gmail_reply(gmail, thread_id, draft_reply)
            
            # Success, update Telegram
            success_text = (
                f"📬 *STATUS: Email Sent successfully!*\n\n"
                f"📧 *To:* `{recipient}`\n"
                f"✅ *Status:* Success (API 200)\n\n"
                f"*Sent Reply:*\n"
                f"```text\n{draft_reply}\n```"
            )
            edit_telegram_message(user_chat_id, message_id, success_text)
            return {"status": "sent"}
            
        except Exception as e:
            # Failure, alert user in Telegram
            fail_text = (
                f"⚠️ *Error Sending Email:*\n`{str(e)}`\n\n"
                f"*Draft Preserved:*\n"
                f"```text\n{draft_reply}\n```"
            )
            edit_telegram_message(user_chat_id, message_id, fail_text)
            return {"status": "error", "reason": str(e)}

    return {"status": "unrecognized action"}
