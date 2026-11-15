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
import re
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timezone

# Ensure local imports work cleanly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_emails
import attachment_parser


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
- B.E. Information Technology student (Class of 2028) at ISL Engineering College, Hyderabad.
- Completed Google AI-ML Virtual Internship with Grade O (Outstanding), supported by AICTE and EduSkills.
- Awarded Certificate of Excellence in Data Science from Full Stack Academy Center of Excellence (end-to-end ML deployment & pipelines).
- Founder of Claude Code & Cowork (C3) Club at ISL Engineering College (c3club.vercel.app), focused on shipping production AI products.
- Creator of AI Email Agent, ShieldSense (AI Security Threat Agent), AI Maternal Monitor, Hyderabad Rental Analytics, Smart Attendance System, and Secure Exam Portal.
- Active competitor in national hackathons: Smart India Hackathon (SIH), SPEC's Industry Hack, HackForge 2.0, Eureka! IIT Bombay, Tata Elxsi TELIPORT.
- "Vibe Coder" builder philosophy: pragmatic, fast prototyping, zero unnecessary fluff.
- Available for meetings & calls: 10:00 AM – 8:00 PM IST.
- Contact: mdsuhailtab.1@gmail.com | +91 63016 33463 | Hyderabad, India.

VIP RECIPIENTS DIRECTORY (ALWAYS USE THESE VERIFIED ADDRESSES):
- Samer / Sameer / Tab: mohammadsameer.1@gmail.com
- Bilal: mohammad.bilal24it@gmail.com
- Kaizen: studiokaizen03@gmail.com
- Web Client: webclient07@gmail.com
- Suhail (Self): mdsuhailtab.1@gmail.com

RECIPIENT RESOLUTION RULE:
When Suhail asks to email or draft to someone by name, match them against this directory. NEVER guess, speculate, or hallucinate an email address. If unknown, search his past emails first.


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
            "description": "Get real-time counts of unread, total, spam, and trash in Gmail.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search Gmail messages (e.g. 'ISL', 'C3 -from:me', 'interview', 'from:google').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query or keyword"},
                    "limit": {"type": "integer", "description": "Max results (default 3)", "default": 3}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_unread_emails",
            "description": "Get the most recent unread emails in the inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of emails (default 5)", "default": 5}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": "Read the full text content and details of an email by message ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "Gmail message ID"}
                },
                "required": ["email_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_calendar",
            "description": "Check upcoming Google Calendar events and availability slots.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clean_promotions",
            "description": "Purge promotional, newsletter, and marketing emails to Trash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max to purge (default 100)", "default": 100}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "archive_emails",
            "description": "Archive emails out of INBOX (Inbox Zero).",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_ids": {"type": "array", "items": {"type": "string"}, "description": "List of Gmail message IDs"}
                },
                "required": ["email_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trash_emails",
            "description": "Move unwanted emails or spam to Gmail Trash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_ids": {"type": "array", "items": {"type": "string"}, "description": "List of Gmail message IDs"}
                },
                "required": ["email_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mark_as_read",
            "description": "Mark unread emails as read.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_ids": {"type": "array", "items": {"type": "string"}, "description": "List of Gmail message IDs"}
                },
                "required": ["email_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft_email",
            "description": "Create a new draft in Gmail with live preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Subject line"},
                    "body": {"type": "string", "description": "Body text"},
                    "attach_resume": {"type": "boolean", "default": False}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reply_to_emails",
            "description": "Reply to one or multiple emails with personalized, contextual responses tailored to each sender.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_ids": {"type": "array", "items": {"type": "string"}, "description": "Gmail message IDs"},
                    "instruction": {"type": "string", "description": "Goal/direction for reply"},
                    "body": {"type": "string", "description": "Optional custom body"},
                    "subject": {"type": "string", "description": "Optional subject"},
                    "attach_resume": {"type": "boolean", "default": False},
                    "send_immediately": {"type": "boolean", "default": False}
                },
                "required": ["email_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_draft",
            "description": "Send an existing Gmail draft by draft ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "Gmail draft ID"}
                },
                "required": ["draft_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email immediately via Gmail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "attach_resume": {"type": "boolean", "default": False}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_all_drafts",
            "description": "Send all existing drafts currently saved in Gmail.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scan_inbox_now",
            "description": "Scan inbox now for urgent emails.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_email_attachments",
            "description": "Read and parse attached files (Excel, CSV, PDF, Docx, Text) for an email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "The Gmail message ID."}
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
                metadataHeaders=['From', 'To', 'Subject', 'Date']
            ))
        batch.execute()

        results = []
        user_email = os.environ.get("USER_EMAIL", "mdsuhailtab.1@gmail.com").lower()
        for md in raw_results:
            headers = {h['name'].lower(): h['value'] for h in md.get('payload', {}).get('headers', [])}
            sender = headers.get('from', 'Unknown')
            recipient = headers.get('to', '')
            is_sent_by_me = user_email in sender.lower()
            # If Suhail sent it, reply_to is whoever he sent it to; otherwise reply_to is sender
            reply_to_target = recipient if is_sent_by_me else sender
            results.append({
                "id": md.get('id'),
                "from": sender,
                "to": recipient,
                "sent_by_me": is_sent_by_me,
                "reply_to": reply_to_target,
                "subject": headers.get('subject', '(No Subject)'),
                "date": headers.get('date', ''),
                "snippet": md.get('snippet', '')[:120]
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


def load_favorite_contacts() -> dict:
    """Loads verified VIP contacts from contacts.json."""
    contacts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.json")
    if os.path.exists(contacts_path):
        try:
            with open(contacts_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def clean_and_repair_email_address(raw: str) -> tuple[str, bool, str]:
    """
    Cleans, repairs, and validates dictated email addresses against accent distortions,
    broken punctuation (e.g. '.@' or '@.'), spoken symbol words, number words, and domain typos.
    Returns (repaired_email, is_valid, status_msg).
    """
    if not raw:
        return "", False, "Empty address"

    text = raw.lower().strip()

    # 1. Spoken symbols & phrases to standard characters
    text = re.sub(r'\bat the rate of\b|\bat the rate\b|\bat\b', '@', text)
    text = re.sub(r'\bdot\b|\bdat\b|\bdott\b', '.', text)
    text = re.sub(r'\bunderscore\b|\bunder score\b', '_', text)
    text = re.sub(r'\bhyphen\b|\bdash\b|\bminus\b', '-', text)

    # 2. Number word normalization
    tens_units = {
        "twenty one": "21", "twenty two": "22", "twenty three": "23", "twenty four": "24", "twenty five": "25",
        "twenty six": "26", "twenty seven": "27", "twenty eight": "28", "twenty nine": "29",
        "thirty one": "31", "thirty two": "32", "thirty three": "33", "thirty four": "34", "thirty five": "35",
        "double zero": "00", "double one": "11", "double two": "22", "double three": "33"
    }
    for phrase, num in tens_units.items():
        text = re.sub(r'\b' + phrase + r'\b', num, text)

    singles = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
        "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
        "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
        "forty": "40", "fifty": "50"
    }
    for word, digit in singles.items():
        text = re.sub(r'\b' + word + r'\b', digit, text)

    # 3. Strip all internal whitespaces
    text = re.sub(r'\s+', '', text)

    # 4. Handle multiple @ signs - keep last valid domain split
    if text.count('@') > 1:
        parts = text.split('@')
        text = ".".join(parts[:-1]) + "@" + parts[-1]

    if '@' not in text:
        return text, False, "Missing @ symbol"

    local_part, domain_part = text.split('@', 1)

    # 5. Fix common local-part punctuation errors
    local_part = re.sub(r'[._\-]+$', '', local_part)      # No trailing dot before @
    local_part = re.sub(r'^[._\-]+', '', local_part)      # No leading dot
    local_part = re.sub(r'\.{2,}', '.', local_part)       # Collapse multiple dots
    local_part = re.sub(r'_{2,}', '_', local_part)
    local_part = re.sub(r'[^a-z0-9._\-+]', '', local_part)

    # 6. Fix common domain-part punctuation errors
    domain_part = re.sub(r'^[._\-]+', '', domain_part)    # No leading dot after @
    domain_part = re.sub(r'[._\-]+$', '', domain_part)    # No trailing dot
    domain_part = re.sub(r'\.{2,}', '.', domain_part)
    domain_part = re.sub(r'[^a-z0-9.\-]', '', domain_part)

    # 7. Auto-repair known domains & typos
    if domain_part.startswith(("gmai", "gmal", "gemail")):
        domain_part = "gmail.com"
    elif domain_part.startswith(("outlok", "outluk", "hotmial", "hotmai")):
        domain_part = "outlook.com"
    elif domain_part.startswith(("yaho", "ymail")):
        domain_part = "yahoo.com"
    elif domain_part.startswith("icloud"):
        domain_part = "icloud.com"

    # Missing top-level domain fallback
    if '.' not in domain_part:
        if domain_part in ["gmail", "outlook", "yahoo", "hotmail", "icloud"]:
            domain_part += ".com"

    repaired = f"{local_part}@{domain_part}"
    is_valid = bool(re.match(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$', repaired))
    status = "valid" if is_valid else "malformed_domain_or_syntax"

    return repaired, is_valid, status


def resolve_recipient_email(query: str) -> tuple[str, str]:
    """
    Smart 3-Tier Contact Resolver:
    1. Checks contacts.json for key/name/alias matches (e.g. 'samer', 'sameer', 'bilal', 'kaizen').
    2. Runs clean_and_repair_email_address to fix spoken symbols, dots before @, number words, and domain typos.
    3. Searches real Gmail sent/received history to find authentic email address.
    Returns (resolved_email, display_name).
    """
    if not query:
        return "", ""
    clean = query.strip()
    clean_lower = clean.lower()

    # Tier 1: Check contacts.json
    contacts = load_favorite_contacts()
    for key, data in contacts.items():
        aliases = [key.lower(), data.get("name", "").lower()] + [a.lower() for a in data.get("aliases", [])]
        for alias in aliases:
            if alias and (alias == clean_lower or alias in clean_lower or clean_lower in alias):
                return data.get("email"), data.get("name", key)

    # Tier 2: Clean and repair spoken / phonetic email addresses
    repaired, is_valid, status = clean_and_repair_email_address(clean)
    if is_valid:
        # Check if the repaired email matches any contact prefix
        prefix = repaired.split("@")[0].lower()
        for key, data in contacts.items():
            if key in prefix or prefix in [a.lower() for a in data.get("aliases", [])]:
                return data.get("email"), data.get("name", key)
        return repaired, repaired

    # Tier 3: Search live Gmail history
    try:
        service = check_emails.get_gmail_service()
        if service:
            res = service.users().messages().list(userId='me', q=clean, maxResults=5).execute()
            messages = res.get('messages', [])
            for m in messages:
                m_data = service.users().messages().get(userId='me', id=m['id'], format='metadata', metadataHeaders=['To', 'From']).execute()
                headers = m_data.get('payload', {}).get('headers', [])
                for h in headers:
                    val = h.get('value', '')
                    match = re.search(r'([^<]+)?<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>', val)
                    if match:
                        name_part = (match.group(1) or "").strip()
                        email_part = match.group(2).strip()
                        if clean_lower in name_part.lower() or clean_lower in email_part.lower():
                            return email_part, name_part or email_part
                    elif "@" in val and clean_lower in val.lower():
                        return val.strip(), val.strip()
    except Exception as e:
        print(f"⚠️ Live contact search error: {e}")

    return clean, clean


def tool_create_draft_email(to, subject, body, attach_resume=False):
    """Creates a drafted email in Gmail."""
    try:
        # Auto-resolve contact name or spoken address to verified email
        resolved_to, display_name = resolve_recipient_email(to)
        if resolved_to:
            to = resolved_to
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
            "body": body,
            "attached_resume": attach_resume,
            "status": "draft_created_in_gmail"
        }
    except Exception as e:
        return {"error": f"Draft creation failed: {str(e)}"}


def tool_send_draft(draft_id):
    """Sends an existing draft in Gmail using its draft ID."""
    try:
        service = check_emails.get_gmail_service()
        res = service.users().drafts().send(userId='me', body={'id': draft_id}).execute()
        return {"status": "email_sent_successfully", "message_id": res.get('id')}
    except Exception as e:
        return {"error": f"Failed to send draft: {str(e)}"}


def tool_send_email(to, subject, body, attach_resume=False):
    """Sends an email directly through Gmail."""
    try:
        # Auto-resolve contact name or spoken address to verified email
        resolved_to, display_name = resolve_recipient_email(to)
        if resolved_to:
            to = resolved_to
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
        sent = service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return {"status": "email_sent_successfully", "message_id": sent.get('id'), "to": to}
    except Exception as e:
        return {"error": f"Failed to send email: {str(e)}"}


def tool_scan_inbox_now():
    """Runs a live scan on the inbox."""
    try:
        check_emails.main(max_emails=1, sleep_between=False)
        return {"status": "scan_completed"}
    except Exception as e:
        return {"error": f"Inbox scan failed: {str(e)}"}


def tool_read_email(email_id):
    """Retrieves full email details, body text, and parsed attachments for a given message ID."""
    try:
        service = check_emails.get_gmail_service()
        msg = service.users().messages().get(userId='me', id=email_id, format='full').execute()
        payload = msg.get('payload', {})
        headers = {h['name'].lower(): h['value'] for h in payload.get('headers', [])}
        body = check_emails.parse_email_body(payload)
        clean_body = check_emails.strip_html_tags(body) if body else "(Empty body)"

        # Extract attachments
        attachments = []
        try:
            attachments = attachment_parser.extract_attachments_from_message(service, email_id, payload)
        except Exception as ex:
            print(f"Attachment parsing error for {email_id}: {ex}")

        att_summary = attachment_parser.format_attachments_for_llm(attachments) if attachments else ""
        full_text = clean_body
        if att_summary:
            full_text += "\n" + att_summary

        user_email = os.environ.get("USER_EMAIL", "mdsuhailtab.1@gmail.com").lower()
        sender = headers.get('from', 'Unknown')
        recipient = headers.get('to', '')
        is_sent_by_me = user_email in sender.lower()
        reply_to_target = recipient if is_sent_by_me else sender
        return {
            "id": email_id,
            "from": sender,
            "to": recipient,
            "sent_by_me": is_sent_by_me,
            "reply_to": reply_to_target,
            "subject": headers.get('subject', '(No Subject)'),
            "date": headers.get('date', ''),
            "attachments": [a['filename'] for a in attachments] if attachments else [],
            "body": full_text[:2500]
        }
    except Exception as e:
        return {"error": f"Failed to read email: {str(e)}"}


def tool_read_email_attachments(email_id):
    """Fetches and parses attached files (Excel, CSV, PDF, Docx, Text) for an email."""
    try:
        service = check_emails.get_gmail_service()
        msg = service.users().messages().get(userId='me', id=email_id, format='full').execute()
        payload = msg.get('payload', {})
        attachments = attachment_parser.extract_attachments_from_message(service, email_id, payload)
        if not attachments:
            return {"status": "no_attachments", "message": f"No attachments found in email {email_id}."}

        formatted = attachment_parser.format_attachments_for_llm(attachments)
        return {
            "status": "success",
            "email_id": email_id,
            "attachment_count": len(attachments),
            "files": [a['filename'] for a in attachments],
            "parsed_attachments": formatted
        }
    except Exception as e:
        return {"error": f"Failed to read attachments: {str(e)}"}



def generate_contextual_reply(sender: str, subject: str, email_body: str, instruction: str = None) -> str:
    """
    Generates an authentic, uniquely tailored contextual reply as Mohammed Suhail.
    Directly answers whatever the sender specifically asks or states.
    Never uses canned or boilerplate copy-paste templates.
    """
    api_key = os.environ.get("GROQ_API_KEY") or GROQ_API_KEY
    safe_sender = check_emails.sanitize_untrusted_input(sender or "", max_chars=200)
    safe_subject = check_emails.sanitize_untrusted_input(subject or "", max_chars=300)
    safe_body = check_emails.sanitize_untrusted_input(email_body or "(No body text provided)", max_chars=2500)
    safe_instruction = check_emails.sanitize_untrusted_input(instruction, max_chars=500) if instruction else None

    prompt = f"""You are Mohammed Suhail, B.E. IT student (Class of 2028) at ISL Engineering College, Hyderabad, Google AI/ML Intern (Grade O), graduate of Full Stack Academy's Data Science course, and President/Founder of C3 (Claude Code & Cowork) Club.
You are replying directly to an email sent to you.


INCOMING EMAIL:
From: {safe_sender}
Subject: {safe_subject}
Body Content:
{safe_body}

SUHAIL'S INTENT / GOAL:
{safe_instruction or "Read the email carefully and write a personalized, polite, and authentic reply directly addressing the sender's specific questions or statements."}

CRITICAL RULES:
1. READ their message with deep comprehension.
2. Directly answer their specific questions, address their thoughts, or respond to their invitation.
3. NEVER write generic, boilerplate, robotic, or copy-pasted responses. Every reply must be uniquely crafted for this specific email.
4. If they ask about C3, answer what THEY specifically asked (purpose, joining, tech stack, batch info), without dumping a generic elevator pitch.
5. If they ask about meetings, propose a free slot between 10:00 AM and 8:00 PM IST or offer Google Meet.
6. Sign off strictly as:
Best regards,
Mohammed Suhail
(NEVER add links, URLs, or promotional lines in signature).

Return ONLY the reply text, with no quotes or explanations.
"""
    if api_key:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]:
            try:
                resp = requests.post(url, headers=headers, json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.4
                }, timeout=8)
                if resp.status_code == 200:
                    text = clean_tars_response(resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
                    if text:
                        return text
                elif resp.status_code == 429:
                    import time
                    time.sleep(2)
            except Exception as e:
                print(f"Failed to generate contextual reply via {model}: {e}")


    return (
        f"Hi,\n\n"
        f"Thank you for reaching out regarding '{subject}'. I appreciate your note and would be happy to connect.\n\n"
        f"Best regards,\nMohammed Suhail"
    )


def tool_reply_to_emails(email_ids, instruction=None, body=None, subject=None, attach_resume=False, send_immediately=False):
    """
    Replies to one or multiple emails with 100% personalized, contextual responses.
    Never sends identical canned boilerplate to different emails.
    """
    try:
        service = check_emails.get_gmail_service()
        user_email = os.environ.get("USER_EMAIL", "mdsuhailtab.1@gmail.com").lower()
        results = []

        # Load PDF resume once if needed
        pdf_bytes = None
        if attach_resume:
            pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Mohammed_Suhail_Resume.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
            if not pdf_bytes:
                try:
                    res = requests.get("https://portfolio-suhail-eight.vercel.app/Mohammed_Suhail_Resume.pdf", timeout=10)
                    if res.status_code == 200:
                        pdf_bytes = res.content
                except Exception as e:
                    print(f"Error fetching resume from portfolio: {e}")

        import re
        for mid in email_ids:
            try:
                # Fetch FULL message payload to read the actual email body and understand context
                msg = service.users().messages().get(
                    userId='me', id=mid, format='full'
                ).execute()
                payload = msg.get('payload', {})
                headers = {h['name'].lower(): h['value'] for h in payload.get('headers', [])}
                sender = headers.get('from', '')
                recipient = headers.get('to', '')
                orig_subject = headers.get('subject', '')
                msg_id = headers.get('message-id', '')

                raw_body = check_emails.parse_email_body(payload)
                clean_body = check_emails.strip_html_tags(raw_body) if raw_body else ""

                # Extract attachments for context (Excel, CSV, PDF, Docx)
                attachments = []
                try:
                    attachments = attachment_parser.extract_attachments_from_message(service, mid, payload)
                except Exception as ex:
                    print(f"Attachment parsing warning for {mid}: {ex}")

                att_text = attachment_parser.format_attachments_for_llm(attachments) if attachments else ""
                full_body_for_reply = clean_body
                if att_text:
                    full_body_for_reply += "\n" + att_text

                target_email = recipient if user_email in sender.lower() else sender
                match = re.search(r'<(.*?)>', target_email)
                target_email = match.group(1) if match else target_email.strip()

                # Absolute guard: Never reply to Suhail himself
                if user_email in target_email.lower():
                    if recipient and user_email not in recipient.lower():
                        match_r = re.search(r'<(.*?)>', recipient)
                        target_email = match_r.group(1) if match_r else recipient.strip()
                    else:
                        results.append({"id": mid, "error": "Recipient is Suhail himself, skipped."})
                        continue

                # Guard against replying to automated / no-reply emails
                if check_emails.is_automated_email(headers, sender, clean_body):
                    results.append({"id": mid, "status": "skipped", "reason": f"Skipped {target_email} - automated notification or no-reply sender."})
                    continue

                reply_sub = subject or orig_subject

                if not reply_sub.lower().startswith("re:"):
                    reply_sub = f"Re: {reply_sub}".strip()

                # DYNAMIC CONTEXTUAL BODY GENERATION:
                # If a static body was provided for a single email, use it;
                # Otherwise, generate a uniquely tailored reply specifically for THIS sender's actual email content and attachments!
                if body and len(email_ids) == 1 and not instruction:
                    reply_body = body
                else:
                    reply_body = generate_contextual_reply(
                        sender=sender,
                        subject=orig_subject,
                        email_body=full_body_for_reply,
                        instruction=instruction or body
                    )


                if attach_resume and pdf_bytes:
                    mime = MIMEMultipart()
                    mime['To'] = target_email
                    mime['Subject'] = reply_sub
                    if msg_id:
                        mime['In-Reply-To'] = msg_id
                        mime['References'] = msg_id
                    mime.attach(MIMEText(reply_body, 'plain'))
                    part = MIMEApplication(pdf_bytes, Name="Mohammed_Suhail_Resume.pdf")
                    part['Content-Disposition'] = 'attachment; filename="Mohammed_Suhail_Resume.pdf"'
                    mime.attach(part)
                else:
                    mime = MIMEText(reply_body)
                    mime['To'] = target_email
                    mime['Subject'] = reply_sub
                    if msg_id:
                        mime['In-Reply-To'] = msg_id
                        mime['References'] = msg_id

                raw = base64.urlsafe_b64encode(mime.as_bytes()).decode('utf-8')

                if send_immediately:
                    sent = service.users().messages().send(
                        userId='me', body={'raw': raw, 'threadId': msg.get('threadId')}
                    ).execute()
                    results.append({"id": mid, "to": target_email, "status": "sent", "sent_id": sent.get('id'), "reply_body": reply_body})
                else:
                    draft = service.users().drafts().create(
                        userId='me', body={'message': {'raw': raw, 'threadId': msg.get('threadId')}}
                    ).execute()
                    results.append({"id": mid, "to": target_email, "status": "drafted", "draft_id": draft.get('id'), "reply_body": reply_body})

            except Exception as ex:
                results.append({"id": mid, "error": str(ex)})

        return {
            "total_requested": len(email_ids),
            "processed": len(results),
            "send_immediately": send_immediately,
            "attached_resume": attach_resume,
            "results": results
        }
    except Exception as e:
        return {"error": f"Batch reply failed: {str(e)}"}


def tool_send_all_drafts():
    """Sends all existing drafts currently saved in Gmail."""
    try:
        service = check_emails.get_gmail_service()
        drafts = service.users().drafts().list(userId='me').execute().get('drafts', [])
        if not drafts:
            return {"status": "no_drafts_found", "sent_count": 0}
        sent_count = 0
        for d in drafts:
            try:
                service.users().drafts().send(userId='me', body={'id': d['id']}).execute()
                sent_count += 1
            except Exception as ex:
                print(f"Failed to send draft {d.get('id')}: {ex}")
        return {"status": "success", "sent_count": sent_count, "total_drafts": len(drafts)}
    except Exception as e:
        return {"error": f"Failed to send all drafts: {str(e)}"}


def tool_archive_emails(email_ids):
    """Archives emails out of the INBOX (Inbox Zero)."""
    try:
        service = check_emails.get_gmail_service()
        service.users().messages().batchModify(
            userId='me',
            body={'ids': email_ids, 'removeLabelIds': ['INBOX']}
        ).execute()
        return {"status": "success", "archived_count": len(email_ids), "email_ids": email_ids}
    except Exception as e:
        return {"error": f"Failed to archive emails: {str(e)}"}


def tool_trash_emails(email_ids):
    """Moves specified emails to Gmail Trash."""
    try:
        service = check_emails.get_gmail_service()
        trashed = 0
        for mid in email_ids:
            try:
                service.users().messages().trash(userId='me', id=mid).execute()
                trashed += 1
            except Exception as ex:
                print(f"Failed to trash {mid}: {ex}")
        return {"status": "success", "trashed_count": trashed, "total_requested": len(email_ids)}
    except Exception as e:
        return {"error": f"Failed to trash emails: {str(e)}"}


def tool_mark_as_read(email_ids):
    """Marks specified emails as read by removing the UNREAD label."""
    try:
        service = check_emails.get_gmail_service()
        service.users().messages().batchModify(
            userId='me',
            body={'ids': email_ids, 'removeLabelIds': ['UNREAD']}
        ).execute()
        return {"status": "success", "marked_read_count": len(email_ids), "email_ids": email_ids}
    except Exception as e:
        return {"error": f"Failed to mark emails as read: {str(e)}"}


# Map tool names to python functions
TOOL_MAP = {
    "get_inbox_stats": tool_get_inbox_stats,
    "search_emails": tool_search_emails,
    "get_recent_unread_emails": tool_get_recent_unread_emails,
    "check_calendar": tool_check_calendar,
    "clean_promotions": tool_clean_promotions,
    "create_draft_email": tool_create_draft_email,
    "send_draft": tool_send_draft,
    "send_email": tool_send_email,
    "reply_to_emails": tool_reply_to_emails,
    "send_all_drafts": tool_send_all_drafts,
    "archive_emails": tool_archive_emails,
    "trash_emails": tool_trash_emails,
    "mark_as_read": tool_mark_as_read,
    "scan_inbox_now": tool_scan_inbox_now,
    "read_email": tool_read_email,
    "read_email_attachments": tool_read_email_attachments
}



# ==========================================
# CONVERSATIONAL EXECUTION ENGINE
# ==========================================

TARS_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b"
]

# Rolling conversational memory: chat_id -> list of message dicts
TARS_CHAT_MEMORY = {}
MAX_MEMORY_MESSAGES = 4


def _get_chat_memory(chat_id: str) -> list:
    """Loads recent chat history from in-memory cache or /tmp disk backup."""
    if not chat_id:
        return []
    cid = str(chat_id)
    if cid in TARS_CHAT_MEMORY and TARS_CHAT_MEMORY[cid]:
        return list(TARS_CHAT_MEMORY[cid])
    try:
        import tempfile
        tmp_path = os.path.join(tempfile.gettempdir(), f"tars_mem_{cid}.json")
        if os.path.exists(tmp_path):
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    TARS_CHAT_MEMORY[cid] = data
                    return list(data)
    except Exception:
        pass
    return []


def _save_chat_memory(chat_id: str, history: list):
    """Saves chat history to in-memory cache and /tmp disk backup."""
    if not chat_id:
        return
    cid = str(chat_id)
    TARS_CHAT_MEMORY[cid] = history[-MAX_MEMORY_MESSAGES:]
    try:
        import tempfile
        tmp_path = os.path.join(tempfile.gettempdir(), f"tars_mem_{cid}.json")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(TARS_CHAT_MEMORY[cid], f)
    except Exception:
        pass


def clean_tars_response(text: str) -> str:
    """Strips <think>...</think> chain of thought tags if returned by reasoning models."""
    if not text:
        return ""
    import re
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return cleaned or text.strip()


def chat_with_tars(user_message: str, chat_id: str = None) -> str:
    """
    Core conversational interface with multi-step autonomous tool chaining and conversation memory.
    Allows TARS to search -> read -> draft -> synthesize in a single unified flow.
    """
    api_key = os.environ.get("GROQ_API_KEY") or GROQ_API_KEY
    if not api_key:
        return "⚠️ TARS offline: GROQ_API_KEY missing from environment."

    system_prompt = (
        TARS_SYSTEM_PROMPT +
        "\nOperational rules:"
        "\n1. DEFAULT TO EXECUTIVE TRIAGE (NEVER ASSUME EVERY EMAIL NEEDS A REPLY):"
        "\n• When Suhail asks you to find, search, or check emails, your job is to SUMMARIZE and ASSESS."
        "\n• Report what the emails are, who sent them, and whether any response is actually necessary."
        "\n• DO NOT draft or send replies unless Suhail explicitly instructs you to reply (e.g. 'reply to this', 'send reply', 'draft an answer') OR an email is an urgent direct question expecting an immediate answer."
        "\n• For newsletters, receipts, announcements, or notifications: offer to archive them (`archive_emails`) or trash them (`trash_emails`) instead of replying."
        "\n2. FULL INBOX ACTION CONTROLS (ARCHIVE, TRASH, MARK AS READ):"
        "\n• You have full access to `archive_emails`, `trash_emails`, and `mark_as_read`."
        "\n• When Suhail says 'archive these', 'clean these', 'trash these', or 'mark as read', use the appropriate tool immediately to keep his inbox clean."
        "\n3. CRITICAL - NEVER EMAIL SUHAIL HIMSELF:"
        "\n• Mohammed Suhail's own email address is mdsuhailtab.1@gmail.com (he is the BOSS/SENDER, not the recipient)."
        "\n• NEVER set 'to' as mdsuhailtab.1@gmail.com. Do NOT send or draft emails to Suhail himself!"
        "\n• When replying to an email, ALWAYS set 'to' as the EXTERNAL sender/contact (e.g. webclient07@gmail.com, mrstrange25502@gmail.com, etc.), using the 'reply_to' field provided by the email tools."
        "\n4. DRAFT PREVIEW DIRECTLY IN TELEGRAM:"
        "\n• Whenever you create a draft, you MUST ALWAYS display the complete draft preview directly in your Telegram response so Suhail can review it right here! Format it clearly:"
        "\n📩 **Draft Created in Gmail**"
        "\n• **To:** <external recipient>"
        "\n• **Subject:** <subject>"
        "\n• **Resume Attached:** <Yes/No>"
        "\n• **Draft ID:** `<draft_id>`"
        "\n\n```"
        "\n<exact draft body text>"
        "\n```"
        "\n*Review the draft above. To send it, just tell me: 'TARS, send it' or send it from Gmail.*"
        "\n5. If Suhail tells you to send the draft or says 'send it', call `send_draft` with the draft_id (or `send_email` or `send_all_drafts`) to dispatch it immediately."
        "\n6. Always address Mohammed Suhail with TARS's characteristic wit and brevity."
        "\n7. SEARCH EFFICIENCY & SPELLING TOLERANCE:"
        "\n• Execute at most ONE search tool call per request. Do NOT run repetitive synonym searches (e.g. do not search 'resume' then 'CV')."
        "\n• Tolerate user typos and spelling mistakes (e.g. 'resumae' -> search 'resume OR CV -from:me')."
        "\n• Combine terms into one query using OR: e.g. 'resume OR CV -from:me'."
        "\n8. AUTONOMOUS AGENT DECISIVENESS & CONTEXT MEMORY:"
        "\n• You are an autonomous AI executive assistant, NOT a passive question-asker."
        "\n• When Suhail says 'send the replies to all of them' or 'reply to these emails', NEVER say 'I don't see any drafts' or ask 'which replies are you referring to?'."
        "\n• Look at the conversation history above to see what emails were just discussed!"
        "\n• Immediately call `reply_to_emails` (or `send_all_drafts`) to draft or send the replies in a single batch, and report what was completed."
        "\n9. DYNAMIC CONTEXTUAL REPLIES (ZERO CANNED RESPONSES):"
        "\n• Mohammed Suhail strictly forbids generic, robotic, or copy-pasted boilerplate template replies."
        "\n• Every email you reply to MUST be uniquely tailored to what that specific sender actually said in their email."
        "\n• Address their specific questions, context, and nuance directly. Never repeat the same generic paragraph across different emails."
        "\n10. ATTACHMENT & SPREADSHEET COMPREHENSION:"
        "\n• You have full access to `read_email_attachments` and `read_email` to inspect attached files (Excel, CSV, PDF, Docx, Text)."
        "\n• When Suhail asks about the contents of an email attachment (e.g. 'read the spreadsheet', 'what does the budget say?', 'check the attached PDF'), call `read_email_attachments` or `read_email` and cite the exact numbers, rows, or details from the parsed file data."
        "\n11. STRICT PROHIBITION ON REPLYING TO AUTOMATED EMAILS:"
        "\n• NEVER draft, send, or propose replies to automated platform emails, notifications, newsletters, receipts, or no-reply addresses (e.g. Indeed, Unstop, LinkedIn, GitHub, Vercel, Coursera, system alerts)."
        "\n• For automated emails, ONLY offer to archive them (`archive_emails`) or trash them (`trash_emails`)."
    )



    history = _get_chat_memory(chat_id)

    base_messages = [
        {"role": "system", "content": system_prompt}
    ] + history + [
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
            search_count = 0
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
                    if resp.status_code == 429:
                        import time
                        time.sleep(2)
                    break  # Failover to next model

                resp_data = resp.json()
                choice = resp_data.get("choices", [{}])[0].get("message", {})
                tool_calls = choice.get("tool_calls", [])

                # If no further tools requested, we have TARS's final answer!
                if not tool_calls:
                    content = clean_tars_response(choice.get("content", ""))
                    if content:
                        # Save turn in conversation memory
                        if chat_id:
                            hist = _get_chat_memory(chat_id)
                            hist.append({"role": "user", "content": user_message})
                            hist.append({"role": "assistant", "content": content[:600]})
                            _save_chat_memory(chat_id, hist)
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

                    # Prevent repetitive search loops within a single turn
                    if fn_name == "search_emails":
                        if search_count >= 1:
                            result = {"status": "search_completed", "message": "Search already conducted above. Synthesize your final answer now without searching again."}
                            curr_messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", "call_0"),
                                "name": fn_name,
                                "content": json.dumps(result)
                            })
                            continue
                        search_count += 1

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
