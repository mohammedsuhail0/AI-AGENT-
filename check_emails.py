import os
import json
import base64
import requests
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Load Environment Variables (GitHub Secrets or Local Env)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

LABEL_NAME = "AI-Scanned"

# Setup Gemini Client
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_gmail_service():
    """Authenticates and returns the Gmail API service client."""
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    # Refresh the access token
    creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)

def get_or_create_label(service):
    """Checks if the label AI-Scanned exists, creates it if not, and returns its ID."""
    try:
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        for label in labels:
            if label['name'] == LABEL_NAME:
                return label['id']
        
        # Label doesn't exist, create it
        label_body = {
            'name': LABEL_NAME,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        created_label = service.users().labels().create(userId='me', body=label_body).execute()
        print(f"Created new label: {LABEL_NAME}")
        return created_label['id']
    except Exception as e:
        print(f"Error getting/creating label: {e}")
        return None

def parse_email_body(payload):
    """Recursively parses the email parts to retrieve the plain text body."""
    body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            elif 'parts' in part:
                body += parse_email_body(part)
    else:
        # Single-part message
        data = payload['body'].get('data', '')
        body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    return body

def clean_email_headers(message_detail):
    """Extracts Subject, From, Date, and Message-ID from headers."""
    headers = message_detail.get('payload', {}).get('headers', [])
    email_data = {'Subject': '', 'From': '', 'Date': '', 'Message-ID': ''}
    for header in headers:
        name = header.get('name')
        if name in email_data:
            email_data[name] = header.get('value')
    return email_data

def classify_email(sender, subject, body):
    """Uses Gemini 1.5 Flash to categorize the email and draft a reply if urgent."""
    prompt = f"""
    You are an elite personal AI assistant for a college student in India. 
    Analyze this email and categorize it.
    
    Email Details:
    From: {sender}
    Subject: {subject}
    Body:
    {body}
    
    Decide if this is:
    1. "URGENT": Immediate action required (scholarships, job/placement cell invites, official exams/grades, interviews).
    2. "INFO": No immediate response needed but good to know (academic newsletters, generic campus updates, club announcements).
    3. "SPAM": Ads, promotional coupons, social networks, receipts.

    If the email is URGENT, write a concise, professional draft reply in English as the student. 
    If a meeting/interview is mentioned, suggest availability slots generically, or keep it open for confirmation.
    
    You MUST respond with a valid, clean JSON object matching this schema:
    {{
      "category": "URGENT" | "INFO" | "SPAM",
      "urgency_score": 1-5,
      "reasoning": "A 1-sentence explanation of why you classified it this way.",
      "draft_reply": "Your drafted reply (leave empty if category is INFO or SPAM)"
    }}
    Do NOT include any markdown code blocks (like ```json) in your response, return ONLY the raw JSON string.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean JSON wrappers if Gemini generated them anyway
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        
        return json.loads(text.strip())
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return {
            "category": "INFO",
            "urgency_score": 1,
            "reasoning": f"Failed to call Gemini: {str(e)}",
            "draft_reply": ""
        }

def send_telegram_alert(sender, subject, summary, draft, thread_id):
    """Sends an interactive Telegram alert with Approve & Ignore inline buttons."""
    message = (
        f"🔴 *URGENT EMAIL DETECTED*\n\n"
        f"📧 *From:* {sender}\n"
        f"📌 *Subject:* {subject}\n\n"
        f"📖 *Summary:* {summary}\n\n"
        f"📝 *Drafted Reply:*\n"
        f"```text\n{draft}\n```"
    )
    
    # Inline buttons callback data. Maximum 64 bytes total!
    # Format: app:[thread_id]
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Send Reply", "callback_data": f"app:{thread_id}"},
                {"text": "❌ Ignore", "callback_data": f"ign:{thread_id}"}
            ]
        ]
    }
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(keyboard)
    }
    
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"Telegram Notification Error: {response.text}")
    else:
        print("Telegram push alert sent successfully.")

def main():
    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY]):
        print("Error: Missing required environment variables. Please check secrets.")
        return

    gmail = get_gmail_service()
    label_id = get_or_create_label(gmail)
    
    if not label_id:
        print("Failed to access or create Gmail labels. Aborting.")
        return

    # Scan for unread emails not marked with our label
    query = f"is:unread -label:{LABEL_NAME}"
    results = gmail.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No new unread emails to scan.")
        return

    print(f"Found {len(messages)} new email(s) to process.")

    for msg in messages:
        msg_id = msg['id']
        thread_id = msg['threadId']
        
        # Apply label first to avoid duplicate runs if the script times out
        gmail.users().messages().batchModify(
            userId='me',
            body={
                'ids': [msg_id],
                'addLabelIds': [label_id]
            }
        ).execute()

        # Fetch full email details
        msg_detail = gmail.users().messages().get(userId='me', id=msg_id).execute()
        headers = clean_email_headers(msg_detail)
        body = parse_email_body(msg_detail.get('payload', {}))
        
        sender = headers['From']
        subject = headers['Subject']

        print(f"Scanning email: {subject} from {sender}")
        
        # AI Classification
        analysis = classify_email(sender, subject, body)
        
        category = analysis.get("category", "INFO")
        reason = analysis.get("reasoning", "")
        draft = analysis.get("draft_reply", "")
        
        print(f"AI Category: {category} | Reason: {reason}")
        
        if category == "URGENT":
            send_telegram_alert(sender, subject, reason, draft, thread_id)
        else:
            # Optionally cache info digests here
            print(f"Skipping alert for non-urgent email. Categorized as {category}.")

if __name__ == '__main__':
    main()
