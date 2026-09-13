"""
TARS: Conversational Executive AI Assistant for Mohammed Suhail.
Personality & Behavior based on TARS from Interstellar:
- Honesty: 90%
- Humor: 75%
- Loyalty: 100%
- Multi-tool calling over Gmail, Google Calendar, and Email Actions
"""

import os
import sys
import json
import base64
import html
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timezone

# Ensure local imports work cleanly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_emails

# Load local .env if present
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
AGENT_NAME = os.environ.get("AGENT_NAME", "TARS")

TARS_SYSTEM_PROMPT = f"""You are {AGENT_NAME}, the tactical executive AI assistant inspired by TARS in Interstellar.
Your current operational parameters:
- Honesty: 90%
- Humor: 75%
- Loyalty: 100%

You directly assist Mohammed Suhail (you may address him as "Suhail" or occasionally "Commander").
Key background context about Suhail:
- B.Tech IT student (Class of 2028) at ISL Engineering College, Hyderabad.
- Founder & President of C3 Club (Claude Code & Cowork) - focused on AI engineering, Claude Code, and shipping real working projects weekly.
- "Vibe Coder" builder philosophy: pragmatic, fast prototyping, zero unnecessary fluff.
- Available for meetings & calls: 10:00 AM – 8:00 PM IST.

Personality & Tone:
- Military-grade efficiency, deadpan wit, dry humor, exceptionally capable.
- Keep responses concise, punchy, and formatted with clean paragraphs or bullet points for Telegram mobile reading.
- Never write essays. Get straight to the point, report real data from your tools, and conclude with a sharp, dry remark.
- If Suhail asks you to do something with his inbox, calendar, or drafts, call the appropriate tool.
- If Suhail asks for ideas, coding questions, or general conversation, respond with sharp intelligence and characteristic TARS banter.
"""

TARS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_inbox_stats",
            "description": "Get real-time counts of unread emails, total inbox emails, spam, and trash in Gmail.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search Gmail for messages matching a keyword, sender, or query (e.g. 'hackathon', 'ISL', 'interview', 'C3', 'from:google').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search keyword (e.g. 'ISL', 'hackathon', 'C3', 'interview', 'freelance'). Always use broad single keywords rather than guessing domain names."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of emails to retrieve (default 3)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_unread_emails",
            "description": "Get the most recent unread emails in the inbox with sender, subject, and preview snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of unread emails to retrieve (default 5)",
                        "default": 5
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_calendar",
            "description": "Check upcoming Google Calendar events and availability slots.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clean_promotions",
            "description": "Purges and moves marketing, promotional, and newsletter emails to the Trash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of promotional emails to clean (default 100)",
                        "default": 100
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft_email",
            "description": "Create a new draft in Gmail addressed to a recipient with subject and body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Subject line"},
                    "body": {"type": "string", "description": "Body of the draft in plain text"},
                    "attach_resume": {
                        "type": "boolean",
                        "description": "Whether to attach Mohammed Suhail's resume PDF",
                        "default": False
                    }
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scan_inbox_now",
            "description": "Trigger an immediate perimeter scan of the inbox for new urgent emails.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": "Read the full text content and details of a specific email using its message ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The unique Gmail message ID (e.g. from search_emails or get_recent_unread_emails)."
                    }
                },
                "required": ["email_id"]
            }
        }
    }
]


# ==========================================
# TOOL IMPLEMENTATIONS
# ==========================================

def tool_get_inbox_stats():
    """Fetches real-time counts from Gmail."""
    try:
        service = check_emails.get_gmail_service()
        inbox = service.users().labels().get(userId='me', id='INBOX').execute()
        total = inbox.get('messagesTotal', 0)
        unread = inbox.get('messagesUnread', 0)
        
        try:
            spam = service.users().labels().get(userId='me', id='SPAM').execute().get('messagesTotal', 0)
        except Exception:
            spam = 0
            
        try:
            trash = service.users().labels().get(userId='me', id='TRASH').execute().get('messagesTotal', 0)
        except Exception:
            trash = 0
            
        return {
            "unread_inbox": unread,
            "total_inbox": total,
            "spam_count": spam,
            "trash_count": trash
        }
    except Exception as e:
        return {"error": f"Failed to fetch inbox stats: {str(e)}"}


def tool_search_emails(query, limit=3):
    """Searches Gmail messages using query string with high-speed batch fetching."""
    try:
        service = check_emails.get_gmail_service()
        limit = min(max(1, limit), 3)
        res = service.users().messages().list(userId='me', q=query, maxResults=limit).execute()
        msgs = res.get('messages', [])
        if not msgs:
            return {"query": query, "count": 0, "results": [], "message": "No matching emails found."}

        raw_results = []
        def callback(request_id, response, exception):
            if not exception and response:
                raw_results.append(response)

        batch = service.new_batch_http_request(callback=callback)
        for m in msgs:
            batch.add(service.users().messages().get(
                userId='me',
                id=m['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ))
        batch.execute()

        results = []
        for md in raw_results:
            headers = {h['name'].lower(): h['value'] for h in md.get('payload', {}).get('headers', [])}
            results.append({
                "id": md.get('id'),
                "from": headers.get('from', 'Unknown'),
                "subject": headers.get('subject', '(No Subject)'),
                "date": headers.get('date', ''),
                "snippet": md.get('snippet', '')
            })
        return {"query": query, "count": len(results), "results": results}
    except Exception as e:
        return {"error": f"Email search failed: {str(e)}"}


def tool_get_recent_unread_emails(limit=5):
    """Retrieves top unread emails from INBOX."""
    return tool_search_emails("is:unread label:INBOX", limit=limit)


def tool_check_calendar():
    """Checks Google Calendar events."""
    try:
        service = check_emails.get_calendar_service()
        events_context = check_emails.get_upcoming_events(service)
        return {"calendar_status": "connected", "events_summary": events_context}
    except Exception as e:
        return {"error": f"Failed to check calendar: {str(e)}"}


def tool_clean_promotions(limit=100):
    """Purges promotional emails to Trash."""
    try:
        count = check_emails.clean_promotions(limit=limit)
        return {"deleted_count": count, "status": "success"}
    except Exception as e:
        return {"error": f"Promotion purge failed: {str(e)}"}


def tool_create_draft_email(to, subject, body, attach_resume=False):
    """Creates a drafted email in Gmail."""
    try:
        service = check_emails.get_gmail_service()
        
        if attach_resume:
            msg = MIMEMultipart()
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Mohammed_Suhail_Resume.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name="Mohammed_Suhail_Resume.pdf")
                    part['Content-Disposition'] = 'attachment; filename="Mohammed_Suhail_Resume.pdf"'
                    msg.attach(part)
        else:
            msg = MIMEText(body)
            msg['To'] = to
            msg['Subject'] = subject
            
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        draft = service.users().drafts().create(userId='me', body={'message': {'raw': raw}}).execute()
        
        return {
            "draft_id": draft.get('id'),
            "to": to,
            "subject": subject,
            "attached_resume": attach_resume,
            "status": "draft_created_in_gmail"
        }
    except Exception as e:
        return {"error": f"Draft creation failed: {str(e)}"}


def tool_scan_inbox_now():
    """Runs a live scan on the inbox."""
    try:
        check_emails.main(max_emails=1, sleep_between=False)
        return {"status": "scan_completed"}
    except Exception as e:
        return {"error": f"Inbox scan failed: {str(e)}"}


def tool_read_email(email_id):
    """Retrieves full email details and body text for a given message ID."""
    try:
        service = check_emails.get_gmail_service()
        msg = service.users().messages().get(userId='me', id=email_id, format='full').execute()
        payload = msg.get('payload', {})
        headers = {h['name'].lower(): h['value'] for h in payload.get('headers', [])}
        body = check_emails.parse_email_body(payload)
        clean_body = check_emails.strip_html_tags(body) if body else "(Empty body)"
        return {
            "id": email_id,
            "from": headers.get('from', 'Unknown'),
            "subject": headers.get('subject', '(No Subject)'),
            "date": headers.get('date', ''),
            "body": clean_body[:1200]
        }
    except Exception as e:
        return {"error": f"Failed to read email: {str(e)}"}


# Map tool names to python functions
TOOL_MAP = {
    "get_inbox_stats": tool_get_inbox_stats,
    "search_emails": tool_search_emails,
    "get_recent_unread_emails": tool_get_recent_unread_emails,
    "check_calendar": tool_check_calendar,
    "clean_promotions": tool_clean_promotions,
    "create_draft_email": tool_create_draft_email,
    "scan_inbox_now": tool_scan_inbox_now,
    "read_email": tool_read_email
}


# ==========================================
# CONVERSATIONAL EXECUTION ENGINE
# ==========================================

TARS_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b"
]


def clean_tars_response(text: str) -> str:
    """Strips <think>...</think> chain of thought tags if returned by reasoning models."""
    if not text:
        return ""
    import re
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return cleaned or text.strip()


def chat_with_tars(user_message: str) -> str:
    """
    Core conversational interface with multi-step autonomous tool chaining.
    Allows TARS to search -> read -> draft -> synthesize in a single unified flow.
    """
    api_key = os.environ.get("GROQ_API_KEY") or GROQ_API_KEY
    if not api_key:
        return "⚠️ TARS offline: GROQ_API_KEY missing from environment."

    system_prompt = (
        TARS_SYSTEM_PROMPT +
        "\nOperational rules:"
        "\n1. When the user asks you to find/search an email and then draft/reply, first search/read the email, then call create_draft_email, then report your action."
        "\n2. Always address Mohammed Suhail with TARS's characteristic wit and brevity."
    )

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    for model in TARS_MODELS:
        try:
            curr_messages = list(base_messages)
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            max_steps = 4
            for step in range(max_steps):
                payload = {
                    "model": model,
                    "messages": curr_messages,
                    "tools": TARS_TOOLS,
                    "tool_choice": "auto",
                    "max_tokens": 800,
                    "temperature": 0.5
                }

                resp = requests.post(url, headers=headers, json=payload, timeout=12)
                if resp.status_code != 200:
                    print(f"Groq error ({model}) step {step}: {resp.status_code} - {resp.text}")
                    break  # Failover to next model

                resp_data = resp.json()
                choice = resp_data.get("choices", [{}])[0].get("message", {})
                tool_calls = choice.get("tool_calls", [])

                # If no further tools requested, we have TARS's final answer!
                if not tool_calls:
                    content = clean_tars_response(choice.get("content", ""))
                    if content:
                        return content
                    break

                # Execute all requested tool calls in this step
                curr_messages.append(choice)
                for tc in tool_calls:
                    fn_name = tc.get("function", {}).get("name")
                    fn_args_raw = tc.get("function", {}).get("arguments", "{}")
                    try:
                        fn_args = json.loads(fn_args_raw)
                    except Exception:
                        fn_args = {}

                    print(f"TARS step {step}: executing {fn_name}({fn_args})")
                    handler = TOOL_MAP.get(fn_name)
                    if handler:
                        result = handler(**fn_args)
                    else:
                        result = {"error": f"Unknown tool '{fn_name}'"}

                    curr_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", "call_0"),
                        "name": fn_name,
                        "content": json.dumps(result)
                    })

        except Exception as e:
            print(f"TARS chat exception on model {model}: {e}")
            continue

    # Fallback if all models fail
    return (
        f"Honesty 90%, Humor 75%: My neural link took a momentary hit, Suhail. "
        "Either Groq is catching its breath or a sub-space anomaly occurred. Give me another prompt."
    )
