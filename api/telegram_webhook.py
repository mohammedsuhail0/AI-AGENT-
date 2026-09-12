import os
import json
import base64
import requests
import re
import sys
import html
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from email.mime.text import MIMEText

# Add parent directory to sys.path to import check_emails
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_emails

app = FastAPI()

# Load local .env file if it exists (for local testing)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# Retrieve Env Secrets
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Webhook Secret Token (optional)
WEBHOOK_SECRET_TOKEN = os.environ.get("WEBHOOK_SECRET_TOKEN")


def get_gmail_service():
    """Refreshes OAuth credentials and returns a Gmail API service client."""
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
    """
    Robustly parses the drafted reply out of Telegram message text.
    Handles HTML <pre>, <code>, Markdown code blocks, and plain text fallbacks.
    """
    if not text:
        return None

    # 1. Check HTML <pre>...</pre> or <pre><code>...</code></pre>
    html_match = re.search(r'<pre>(?:<code>)?(.*?)(?:</code>)?</pre>', text, re.DOTALL | re.IGNORECASE)
    if html_match:
        return html.unescape(html_match.group(1)).strip()

    # 2. Check Markdown ```text ... ``` or ``` ... ```
    md_match = re.search(r'```(?:text)?\n?(.*?)\n?```', text, re.DOTALL)
    if md_match:
        return md_match.group(1).strip()

    # 3. Check plain text label
    if "Drafted Reply:" in text:
        parts = text.split("Drafted Reply:")
        if len(parts) > 1:
            candidate = parts[1].strip()
            # Strip outer quotes or backticks if left over
            candidate = re.sub(r'^[`"\']+|[`"\']+$', '', candidate)
            return candidate.strip()

    return None


def send_gmail_reply(service, thread_id, draft_body):
    """Sends a reply back in the original Gmail thread, preserving RFC 822 thread headers."""
    thread = service.users().threads().get(userId='me', id=thread_id).execute()
    messages = thread.get('messages', [])
    if not messages:
        raise Exception("Original email thread not found.")
        
    last_msg = messages[-1]
    headers = last_msg.get('payload', {}).get('headers', [])
    
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

    match = re.search(r'<(.*?)>', from_email)
    reply_to = match.group(1) if match else from_email

    # Header injection hardening: strip any newlines
    reply_to = re.sub(r'[\r\n]+', ' ', reply_to).strip()
    subject = re.sub(r'[\r\n]+', ' ', subject).strip()

    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"


    msg = MIMEText(draft_body)
    msg['To'] = reply_to
    msg['Subject'] = subject
    if msg_id:
        msg['In-Reply-To'] = msg_id
        msg['References'] = msg_id
    
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    body = {
        'raw': raw_message,
        'threadId': thread_id
    }
    
    result = service.users().messages().send(userId='me', body=body).execute()
    return result, reply_to


def send_telegram_reply(chat_id, text, reply_to_message_id=None, parse_mode="HTML"):
    """Sends a text message back to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": parse_mode
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    res = requests.post(url, json=payload, timeout=10)
    if res.status_code != 200 and parse_mode is not None:
        payload["parse_mode"] = None
        requests.post(url, json=payload, timeout=10)


def edit_telegram_message(chat_id, message_id, status_text, parse_mode="HTML"):
    """Updates the original Telegram alert message and removes inline buttons."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": status_text[:4000],
        "parse_mode": parse_mode,
        "reply_markup": json.dumps({"inline_keyboard": []})
    }
    res = requests.post(url, json=payload, timeout=10)
    if res.status_code != 200 and parse_mode is not None:
        payload["parse_mode"] = None
        requests.post(url, json=payload, timeout=10)


def run_status_check():
    """Runs a check on Gmail, Calendar, and Groq APIs."""
    status_msg = "🔌 <b>API CONNECTION STATUS CHECK</b>\n\n"
    
    # 1. Gmail Check
    try:
        gmail = get_gmail_service()
        profile = gmail.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress', 'Unknown')
        status_msg += f"✅ <b>Gmail API:</b> Connected\n└ Account: <code>{html.escape(email)}</code>\n\n"
    except Exception as e:
        status_msg += f"❌ <b>Gmail API:</b> Disconnected\n└ Error: <code>{html.escape(str(e))}</code>\n\n"

    # 2. Calendar Check
    try:
        calendar = check_emails.get_calendar_service()
        calendar.calendarList().list(maxResults=1).execute()
        status_msg += "✅ <b>Google Calendar API:</b> Connected\n└ Permissions: Read-Only (OK)\n\n"
    except Exception as e:
        status_msg += f"❌ <b>Google Calendar API:</b> Disconnected\n└ Error: <code>{html.escape(str(e))}</code>\n\n"

    # 3. Groq Check (tries primary and fallback models)
    groq_success = False
    for model in check_emails.GROQ_MODELS:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Ping"}],
                "max_tokens": 5
            }
            res = requests.post(url, json=payload, headers=headers, timeout=8)
            if res.status_code == 200:
                status_msg += f"✅ <b>Groq API:</b> Connected\n└ Active Model: <code>{html.escape(model)}</code> (Free Tier)\n\n"
                groq_success = True
                break
        except Exception:
            continue

    if not groq_success:
        status_msg += "❌ <b>Groq API:</b> Disconnected\n└ All models failed or rate-limited.\n\n"
        
    return status_msg


def run_inbox_count():
    """Fetches real-time counts from Gmail."""
    try:
        gmail = get_gmail_service()
        inbox_info = gmail.users().labels().get(userId='me', id='INBOX').execute()
        total_inbox = inbox_info.get('messagesTotal', 0)
        unread_inbox = inbox_info.get('messagesUnread', 0)
        
        try:
            spam_info = gmail.users().labels().get(userId='me', id='SPAM').execute()
            total_spam = spam_info.get('messagesTotal', 0)
        except Exception:
            total_spam = "N/A"
            
        try:
            trash_info = gmail.users().labels().get(userId='me', id='TRASH').execute()
            total_trash = trash_info.get('messagesTotal', 0)
        except Exception:
            total_trash = "N/A"

        return (
            "📊 <b>GMAIL INBOX STATUS</b>\n\n"
            f"📬 <b>Total Inbox:</b> {total_inbox}\n"
            f"📩 <b>Unread Inbox:</b> {unread_inbox}\n"
            f"🗑️ <b>Trash:</b> {total_trash}\n"
            f"🚫 <b>Spam:</b> {total_spam}\n"
        )
    except Exception as e:
        return f"⚠️ <b>Error fetching inbox count:</b> <code>{html.escape(str(e))}</code>"


@app.post("/api/telegram_webhook")
async def telegram_webhook(request: Request):
    """Entrypoint for Telegram webhook updates."""
    if WEBHOOK_SECRET_TOKEN:
        received_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if received_token != WEBHOOK_SECRET_TOKEN:
            raise HTTPException(status_code=403, detail="Unauthorized webhook source")

    data = await request.json()
    
    # 1. Handle Callback Queries (Button Taps)
    if "callback_query" in data:
        callback = data["callback_query"]
        user_chat_id = str(callback["message"]["chat"]["id"])
        message_id = callback["message"]["message_id"]
        message_text = callback["message"].get("text", "")
        callback_data = callback.get("data", "")
        
        if user_chat_id != TELEGRAM_CHAT_ID:
            return JSONResponse(content={"status": "unauthorized"})

        # Double-click idempotency check
        if "Email Sent successfully" in message_text or "Archived Alert (Ignored)" in message_text:
            return JSONResponse(content={"status": "already_processed"})

        parts = callback_data.split(":")
        if len(parts) != 2:
            return JSONResponse(content={"status": "error", "reason": "invalid callback data format"})
            
        action, thread_id = parts[0], parts[1]

        if action == "ign":
            safe_original = html.escape(message_text)
            new_text = f"❌ <b>Archived Alert (Ignored)</b>\n\n{safe_original}"
            edit_telegram_message(user_chat_id, message_id, new_text)
            return {"status": "ignored"}

        elif action == "app":
            draft_reply = extract_draft_from_message(message_text)
            if not draft_reply:
                safe_msg = html.escape(message_text)
                error_text = f"⚠️ <b>Error:</b> Could not extract draft reply from message.\n\n{safe_msg}"
                edit_telegram_message(user_chat_id, message_id, error_text)
                return {"status": "error", "reason": "draft parse failed"}

            try:
                gmail = get_gmail_service()
                _, recipient = send_gmail_reply(gmail, thread_id, draft_reply)
                
                safe_recip = html.escape(recipient)
                safe_draft = html.escape(draft_reply)
                success_text = (
                    f"📬 <b>STATUS: Email Sent successfully!</b>\n\n"
                    f"📧 <b>To:</b> <code>{safe_recip}</code>\n"
                    f"✅ <b>Status:</b> Success (API 200)\n\n"
                    f"<b>Sent Reply:</b>\n"
                    f"<pre>{safe_draft}</pre>"
                )
                edit_telegram_message(user_chat_id, message_id, success_text)
                return {"status": "sent"}
            except Exception as e:
                safe_err = html.escape(str(e))
                safe_draft = html.escape(draft_reply)
                fail_text = (
                    f"⚠️ <b>Error Sending Email:</b>\n<code>{safe_err}</code>\n\n"
                    f"<b>Draft Preserved:</b>\n"
                    f"<pre>{safe_draft}</pre>"
                )
                edit_telegram_message(user_chat_id, message_id, fail_text)
                return {"status": "error", "reason": str(e)}

    # 2. Handle Text Messages & Slash Commands
    elif "message" in data:
        message = data["message"]
        user_chat_id = str(message["chat"]["id"])
        text = message.get("text", "").strip()

        if user_chat_id != TELEGRAM_CHAT_ID:
            return JSONResponse(content={"status": "unauthorized"})

        if text.startswith("/"):
            command = text.split(" ")[0].lower()
            
            if command == "/start":
                welcome_text = (
                    "👋 <b>Hello! I am your Personal Email AI Agent.</b>\n\n"
                    "I monitor your Gmail inbox, check Google Calendar availability, "
                    "auto-delete spam, and draft replies to urgent inquiries.\n\n"
                    "<b>Commands:</b>\n"
                    "🔌 <code>/status</code> - Check API connectivity status\n"
                    "📊 <code>/count</code> - View current inbox statistics\n"
                    "🔍 <code>/scan</code> - Scan inbox immediately for new emails\n"
                    "🧹 <code>/clean</code> - Move promotional emails to Trash\n"
                    "📅 <code>/summary</code> - Trigger your Daily Digest immediately"
                )
                send_telegram_reply(user_chat_id, welcome_text)
                return {"status": "command_processed", "command": "/start"}
                
            elif command == "/status":
                status_text = run_status_check()
                send_telegram_reply(user_chat_id, status_text)
                return {"status": "command_processed", "command": "/status"}

            elif command == "/count":
                count_text = run_inbox_count()
                send_telegram_reply(user_chat_id, count_text)
                return {"status": "command_processed", "command": "/count"}
                
            elif command == "/scan":
                send_telegram_reply(user_chat_id, "⏳ <b>Scanning your Gmail inbox for new emails...</b>")
                try:
                    # Scan 1 email without artificial sleep to stay well under Vercel's 10s ceiling
                    check_emails.main(max_emails=1, sleep_between=False)
                    send_telegram_reply(user_chat_id, "✅ <b>Scan completed!</b> Check above for any new URGENT email alerts.")
                    return {"status": "command_processed", "command": "/scan"}
                except Exception as e:
                    safe_err = html.escape(str(e))
                    send_telegram_reply(user_chat_id, f"⚠️ <b>Error scanning inbox:</b> <code>{safe_err}</code>")
                    return {"status": "error", "reason": str(e)}

            elif command == "/clean":
                send_telegram_reply(user_chat_id, "⏳ <b>Cleaning promotional emails...</b>")
                try:
                    count = check_emails.clean_promotions(limit=300)
                    if count > 0:
                        send_telegram_reply(user_chat_id, f"🧹 <b>Cleaned {count} promotional email(s)</b> from your inbox! Moved them to Trash.")
                    elif count == 0:
                        send_telegram_reply(user_chat_id, "🧹 <b>Your promotions folder is already empty!</b> Clean inbox! ✨")
                    else:
                        send_telegram_reply(user_chat_id, "⚠️ <b>Error cleaning promotions.</b> Check Vercel logs.")
                    return {"status": "command_processed", "command": "/clean"}
                except Exception as e:
                    safe_err = html.escape(str(e))
                    send_telegram_reply(user_chat_id, f"⚠️ <b>Error cleaning promotions:</b> <code>{safe_err}</code>")
                    return {"status": "error", "reason": str(e)}

            elif command == "/summary":
                send_telegram_reply(user_chat_id, "⏳ <b>Generating your Daily Digest immediately...</b>")
                try:
                    check_emails.send_daily_digest()
                    return {"status": "command_processed", "command": "/summary"}
                except Exception as e:
                    safe_err = html.escape(str(e))
                    send_telegram_reply(user_chat_id, f"⚠️ <b>Error generating summary:</b> <code>{safe_err}</code>")
                    return {"status": "error", "reason": str(e)}
            
            else:
                safe_cmd = html.escape(command)
                send_telegram_reply(user_chat_id, f"❓ <b>Unknown command:</b> <code>{safe_cmd}</code>")
                return {"status": "unknown_command"}

    return {"status": "ignored", "reason": "unhandled payload type"}
