# TARS: Autonomous AI Executive Email Agent & Inbox Chief of Staff
> **Comprehensive Architectural Blueprint, Technical Specification, and Step-by-Step Deployment Guide**  
> *Author: Mohammed Suhail (President, C3 Club | B.Tech IT, ISL Engineering College | Data Science Graduate, Full Stack Academy)*

---

## 📑 Table of Contents
1. [Executive Summary & Concept](#1-executive-summary--concept)
2. [The Problem: Why Traditional Email & Auto-Responders Fail](#2-the-problem-why-traditional-email--auto-responders-fail)
3. [System Architecture & Data Flow](#3-system-architecture--data-flow)
4. [Complete Technology Stack](#4-complete-technology-stack)
5. [Core Engine & Component Deep Dive](#5-core-engine--component-deep-dive)
   - [5.1 `check_emails.py` — Background Scanner & Triage Engine](#51-check_emailspy--background-scanner--triage-engine)
   - [5.2 `attachment_parser.py` — Multi-Format Attachment Reader](#52-attachment_parserpy--multi-format-attachment-reader)
   - [5.3 `tars_agent.py` — TARS Conversational Autonomous Brain](#53-tars_agentpy--tars-conversational-autonomous-brain)
   - [5.4 `api/telegram_webhook.py` — Serverless FastAPI Webhook](#54-apitelegram_webhookpy--serverless-fastapi-webhook)
   - [5.5 `auth_helper.py` — Headless OAuth 2.0 Credential Generator](#55-auth_helperpy--headless-oauth-20-credential-generator)
   - [5.6 `.github/workflows/scan.yml` — Cloud CI/CD Automation](#56-githubworkflowsscanyml--cloud-cicd-automation)
6. [Step-by-Step Reproduction Guide (Build It Yourself)](#6-step-by-step-reproduction-guide-build-it-yourself)
   - [Step 1: Google Cloud Console & API Configuration](#step-1-google-cloud-console--api-configuration)
   - [Step 2: Generate OAuth Refresh Token via `auth_helper.py`](#step-2-generate-oauth-refresh-token-via-auth_helperpy)
   - [Step 3: Telegram Bot Setup via @BotFather](#step-3-telegram-bot-setup-via-botfather)
   - [Step 4: Groq API Key Setup (Free Tier LLM)](#step-4-groq-api-key-setup-free-tier-llm)
   - [Step 5: Local Installation & Environment Setup](#step-5-local-installation--environment-setup)
   - [Step 6: Deploying Webhook to Vercel](#step-6-deploying-webhook-to-vercel)
   - [Step 7: Configuring 24/7 Scanning on GitHub Actions](#step-7-configuring-247-scanning-on-github-actions)
7. [Security, Privacy, and Defense-in-Depth](#7-security-privacy-and-defense-in-depth)
8. [TARS Toolset & Command Reference](#8-tars-toolset--command-reference)
9. [Operational Scenarios & Verification Tests](#9-operational-scenarios--verification-tests)
10. [Maintenance & Troubleshooting](#10-maintenance--troubleshooting)

---

## 1. Executive Summary & Concept

**TARS** is an autonomous, production-ready AI Executive Chief of Staff designed to run 24/7 at **$0.00 operating cost**. It monitors an active Gmail inbox, understands incoming attachments (including Excel workbooks, CSVs, PDFs, and Word documents), cross-references real-time Google Calendar availability, auto-purges marketing clutter, and delivers actionable, triaged notifications to your smartphone via Telegram.

Unlike brittle rule-based filters or traditional auto-responders that broadcast robotic, canned templates, TARS acts with **contextual human intelligence**:
- It reads the sender's specific questions, context, and tone.
- It parses attached data tables (e.g. sponsorship budgets, invoices, rosters) before responding.
- It drafts customized responses and offers one-tap dispatch buttons (`[Send Reply]`, `[Send with Resume]`, `[Ignore]`) directly in Telegram.
- It converses fluently as an executive assistant with a distinct personality inspired by TARS in *Interstellar* (90% honesty, 75% humor, military-grade brevity).
- It executes complex multi-step inbox workflows (e.g. *"Archive all emails from Unstop"*, *"Read the attached spreadsheet from Hackathon team"*, *"Draft a reply proposing 4 PM on Thursday"*).

---

## 2. The Problem: Why Traditional Email & Auto-Responders Fail

| Traditional Email Flow | The Problem | TARS Solution |
| :--- | :--- | :--- |
| **Out-of-Office / Auto-Reply** | Broadcasts the exact same canned text to everyone—including newsletters, receipts, automated bots, and rejection notices. | **Contextual Decision Engine:** Pre-filters automated bots; generates 100% unique contextual drafts for actual human inquiries only. |
| **Manual Mobile Gmail Triage** | Pinching/zooming spreadsheets, typing mobile replies, cross-checking calendar apps. | **Telegram Headless Hub:** High-priority summaries, parsed attachment tables, and one-tap approve/edit buttons inside Telegram. |
| **Spam & Marketing Inundation** | Inboxes accumulate thousands of promotional emails that bury critical hackathons, internships, and recruiter leads. | **Autonomous Purge:** Background scanner classifies and moves promotional junk directly to Trash while preserving a 30-day safety net. |
| **Complex Multi-Step Requests** | Checking availability requires opening Calendar, copying times, composing an email, and attaching a resume. | **Agentic Tool Execution:** TARS inspects calendar busy slots, checks conflicts, auto-attaches PDF resumes, and dispatches via Gmail API in a single turn. |

---

## 3. System Architecture & Data Flow

The system operates via two complementary execution paths:
1. **Asynchronous Autonomous Scanner:** A background process triggered every 5 minutes by GitHub Actions that polls Gmail, classifies unread emails, purges spam, parses attachments, and pushes alerts to Telegram.
2. **Synchronous Conversational Assistant:** A serverless FastAPI webhook on Vercel connected to Telegram that enables live, natural language command-and-control over Gmail and Calendar using rolling conversational memory and tool-calling.

```mermaid
graph TD
    subgraph "External Inbound Channels"
        GMAIL[Gmail Inbox API]
        GCAL[Google Calendar API]
    end

    subgraph "Asynchronous Path (GitHub Actions - Every 5 min)"
        CRON[GitHub Actions Runner] -->|Runs| SCAN[check_emails.py]
        SCAN -->|Fetch Unread| GMAIL
        SCAN -->|Fetch Busy Slots| GCAL
        SCAN -->|Extract Attachments| PARSER[attachment_parser.py]
        SCAN -->|Filter Automated Bots| AUTOFILTER[is_automated_email RFC Filter]
        SCAN -->|Classify & Draft| GROQ1[Groq API Multi-Model Failover]
        GROQ1 -->|SPAM| TRASH[Move to Gmail Trash]
        GROQ1 -->|INFO| DIGEST[Label AI-Info / Daily Digest]
        GROQ1 -->|URGENT| TG_ALERT[Push Interactive Alert to Telegram]
    end

    subgraph "Synchronous Path (Vercel Serverless + Telegram)"
        USER[User on Telegram App] -->|Click Button or Send Command| TG_BOT[@suhail_email_agent_bot]
        TG_BOT -->|Webhook POST| VERCEL[api/telegram_webhook.py]
        VERCEL -->|Callback Query: Send/Ignore| GMAIL_SEND[Send Email via Gmail API]
        VERCEL -->|Natural Language Message| TARS[tars_agent.py Engine]
        TARS -->|Load Chat Memory| MEM[(TARS_CHAT_MEMORY)]
        TARS -->|Multi-Turn Agent Loop| GROQ2[Groq Tool Calling]
        GROQ2 -->|Tool Calls: search/archive/trash/read/draft| TOOLS[TARS Tool Implementations]
        TOOLS --> GMAIL
        TOOLS --> GCAL
        TOOLS --> PARSER
        TARS -->|Executive Response & Draft Preview| USER
    end
```

---

## 4. Complete Technology Stack

| Layer | Component | Description & Justification |
| :--- | :--- | :--- |
| **LLM Inference** | **Groq Cloud API** | Sub-second token generation (~300-500 tokens/sec) on free tier. Models utilized: `qwen/qwen3.8-27b`, `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `llama-3.3-70b-versatile` with automatic failover. |
| **Runtime Environment** | **Python 3.10+** | Core runtime leveraging standard libraries (`email.mime`, `base64`, `json`, `re`, `html`, `csv`) alongside enterprise client SDKs. |
| **Email & Calendar API** | **Google APIs SDK** | `google-api-python-client` & `google-auth-oauthlib` communicating via OAuth 2.0 with offline refresh token persistence for zero user re-auth. |
| **Serverless Webhook** | **FastAPI + Uvicorn** | High-performance, lightweight ASGI framework hosted on **Vercel Serverless Functions** for instant event dispatching. |
| **Background Automation** | **GitHub Actions** | Cloud CI/CD runner executing headless scheduled cron jobs (`*/5 * * * *` and `30 14 * * *`) without needing an active VPS. |
| **Chat Command Center** | **Telegram Bot API** | Bidirectional webhook handling inline interactive buttons (`callback_data`), code blocks, and markdown formatting. |
| **Spreadsheet Engine** | **openpyxl** | Pure-Python Excel parser reading `.xlsx` and `.xls` workbooks sheet-by-sheet into Markdown data tables. |
| **Document Parsers** | **pypdf / python-docx** | Pure-Python document parsing extracting textual data and tables from `.pdf` and `.docx` attachments. |

---

## 5. Core Engine & Component Deep Dive

### 5.1 `check_emails.py` — Background Scanner & Triage Engine
This module is the autonomous frontline sentry of your inbox.

#### A. Automated Bot & Newsletter Filter (`is_automated_email`)
To prevent the agent from drafting embarrassing replies to system platforms (e.g. Unstop registration receipts, Indeed job blasts, GitHub build alerts), this function enforces strict multi-layer filtering before the LLM is invoked:
1. **RFC Header Examination:** Inspects `List-Unsubscribe`, `List-Id`, `Precedence: bulk/list/junk`, and `Auto-Submitted != no`.
2. **Sender Token Detection:** Matches tokens like `noreply@`, `no-reply@`, `notifications@`, `alerts@`, `mailer@`, `newsletter@`, `system@`.
3. **Platform Domain Matching:** Identifies known automated domains (`github.com`, `vercel.com`, `indeed.com`, `unstop.com`, `linkedin.com`, `coursera.org`).
4. **Body Footers:** Scans for keywords like *"unsubscribe"*, *"manage notification preferences"*, *"do not reply directly to this email"*.
5. **Enforcement:** If flagged as automated, the email is **strictly barred** from `URGENT` status; `draft` is set to empty `""`, and the email is categorized as `INFO` (queued for the 8 PM digest) or `SPAM`.

#### B. Classification & Priority Hierarchy
The prompt feeds Mohammed Suhail's profile, academic credentials (B.Tech IT '28 @ ISL, Full Stack Academy Data Science graduate, C3 Club President), and Google Calendar busy slots into the LLM:
- **`URGENT`:** Human recruiters, client leads, hackathon demo invites, academic administrative notices, or personal inquiries requiring a direct response.
- **`INFO`:** System alerts, newsletters, receipts (labeled `AI-Info` for digest).
- **`SPAM`:** Unsolicited cold sales blasts and marketing promos (auto-trashed).

#### C. Dynamic Contextual Reply Generator (`generate_contextual_reply`)
When an email is verified as an urgent human inquiry:
- The system extracts the email body, subject, and any parsed attachments.
- The prompt explicitly instructs the LLM to write an authentic response directly answering the sender's questions, proposing free calendar slots between 10:00 AM - 8:00 PM IST, and signing off cleanly without robotic corporate fluff.
- Static canned boilerplate has been completely eradicated.

---

### 5.2 `attachment_parser.py` — Multi-Format Attachment Reader
When an email arrives containing attachments, this engine extracts binary data from the Gmail MIME tree via `users().messages().attachments().get()` and translates it into clean LLM-digestible text:

```
┌────────────────────────────────────────────────────────┐
│               Gmail Inbound Attachment                 │
└──────────────────────────┬─────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   Excel (.xlsx)       CSV (.csv)        PDF (.pdf)
  (openpyxl parser)  (csv.reader)      (pypdf parser)
         │                 │                 │
         └─────────────────┼─────────────────┘
                           ▼
       Clean Tabular Markdown / Formatted Text
       (Capped at 50 rows / 2,500 chars per file)
                           │
                           ▼
     Injected into LLM Prompt Context alongside Email Body
```

- **Excel (`.xlsx`, `.xls`):** Traverses the workbook, filters out empty cells, and renders clean markdown tables for up to 3 sheets.
- **CSV (`.csv`):** Handles multiple encodings (`utf-8`, `latin-1`, `cp1252`) and produces structured tabular data.
- **PDF (`.pdf`):** Extracts text across pages using `pypdf` with fallback to `pymupdf`.
- **Word (`.docx`):** Extracts body paragraphs and converts embedded Word tables into pipe-delimited text.
- **Token Overflow Protection:** Each attachment is truncated to a safe ceiling (2,500 characters) to ensure the prompt never exhausts Groq rate limits.

---

### 5.3 `tars_agent.py` — TARS Conversational Autonomous Brain
The interactive engine implementing an agentic loop with persistent memory and tool invocation:

#### A. Operational Parameters & Persona
- **Honesty:** 90%
- **Humor:** 75%
- **Loyalty:** 100%
- **Tone:** Deadpan wit, military-grade brevity, zero polite padding.

#### B. Rolling Conversational Memory
Maintains `TARS_CHAT_MEMORY` per `chat_id` up to 4 historical turns. Assistant responses are capped at 600 characters in memory to keep context payloads small and conserve token capacity.

#### C. The 16 Autonomous Tools
TARS has native function-calling access to:
1. `get_inbox_stats`: Real-time report of unread, total, spam, and trash counts.
2. `search_emails`: Gmail queries (combining keywords, boolean operators, `-from:me`).
3. `get_recent_unread_emails`: Retrieves unread emails with snippets and IDs.
4. `check_calendar`: Checks Google Calendar for the next 3 days.
5. `clean_promotions`: Trashes marketing clutter in bulk.
6. `create_draft_email`: Composes drafts in Gmail and renders full previews in Telegram.
7. `send_draft`: Sends an approved draft by draft ID.
8. `send_email`: Composes and dispatches an email directly.
9. `reply_to_emails`: Autonomous batch reply tool reading bodies and attachments.
10. `send_all_drafts`: Dispatches all pending Gmail drafts with a single command.
11. `archive_emails`: Removes the `INBOX` label (Inbox Zero).
12. `trash_emails`: Moves specified message IDs to Trash.
13. `mark_as_read`: Removes the `UNREAD` label.
14. `scan_inbox_now`: Triggers an immediate inbox scan.
15. `read_email`: Reads full email headers, clean body, and attachments.
16. `read_email_attachments`: Extracts and returns parsed tables and text from attachments.

---

### 5.4 `api/telegram_webhook.py` — Serverless FastAPI Webhook
Deploys on Vercel to handle Telegram interactions:
- **Callback Queries (Button Taps):**
  - `app:<thread_id>`: Dispatches the drafted reply to the recipient via Gmail API.
  - `app_res:<thread_id>`: Dispatches the reply with `Mohammed_Suhail_Resume.pdf` attached.
  - `ign:<thread_id>`: Archives the alert and marks it as ignored.
  - **Idempotency Protection:** Prevents duplicate sends on double-clicks.
- **Slash Commands:**
  - `/status`: Validates connectivity across Vercel, Gmail, Calendar, and Groq.
  - `/scan`: Runs an on-demand scan of unread emails.
  - `/clean`: Trashes up to 300 promotional emails.
  - `/summary`: Compiles an immediate daily digest.
- **Conversational Router:** Any non-slash message is forwarded directly to `chat_with_tars(message, chat_id)`.

---

### 5.5 `auth_helper.py` — Headless OAuth 2.0 Credential Generator
Desktop utility that initiates a local browser OAuth consent flow requesting the following scopes:
- `https://mail.google.com/` (Full Gmail read, write, trash, and send capabilities).
- `https://www.googleapis.com/auth/calendar.readonly` (Read-only access to calendar events).
It outputs `token.json` containing the permanent `refresh_token`, which is then deployed into environment variables.

---

### 5.6 `.github/workflows/scan.yml` — Cloud CI/CD Automation
Runs on GitHub's Ubuntu runners:
- `cron: '*/5 * * * *'`: Executes `python check_emails.py` every 5 minutes for real-time triage.
- `cron: '30 14 * * *'`: Executes `python check_emails.py --digest` at 2:30 PM UTC (8:00 PM IST) to send the daily digest.

---

## 6. Step-by-Step Reproduction Guide (Build It Yourself)

Follow this guide to replicate and deploy this system from scratch.

### Step 1: Google Cloud Console & API Configuration
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `Personal-Email-Agent`).
3. Navigate to **APIs & Services > Library** and enable:
   - **Gmail API**
   - **Google Calendar API**
4. Navigate to **APIs & Services > OAuth consent screen**:
   - User Type: **External**
   - Fill in App Name and your support email.
   - Under **Test Users**, add your personal Gmail address.
5. Navigate to **APIs & Services > Credentials**:
   - Click **Create Credentials > OAuth client ID**.
   - Application Type: **Desktop app**.
   - Download the client configuration file and save it as `credentials.json` in your local project root.

---

### Step 2: Generate OAuth Refresh Token via `auth_helper.py`
1. Install Google Auth libraries locally:
   ```bash
   pip install google-auth-oauthlib google-api-python-client
   ```
2. Run the authentication script:
   ```bash
   python auth_helper.py
   ```
3. A browser window will open. Log in with your Gmail account and approve permissions.
4. The terminal will output your credentials:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`
5. Save these securely. You can now delete `credentials.json` and `token.json`.

---

### Step 3: Telegram Bot Setup via @BotFather
1. Open Telegram and search for [`@BotFather`](https://t.me/BotFather).
2. Send `/newbot`, name your bot (e.g. `Suhail Email Agent`), and choose a username ending in `bot`.
3. Save the **Bot Token** (`TELEGRAM_BOT_TOKEN`).
4. Search for [`@GetIDBot`](https://t.me/GetIDBot) on Telegram and send `/my_id`.
5. Copy your numerical ID (`TELEGRAM_CHAT_ID`).

---

### Step 4: Groq API Key Setup (Free Tier LLM)
1. Go to the [Groq Cloud Console](https://console.groq.com/).
2. Sign in and navigate to **API Keys**.
3. Create a new API key and copy it (`GROQ_API_KEY`).

---

### Step 5: Local Installation & Environment Setup
1. Clone this repository:
   ```bash
   git clone https://github.com/mohammedsuhail0/AI-AGENT-.git
   cd AI-AGENT-
   ```
2. Create and populate your `.env` file:
   ```env
   GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your_client_secret
   GOOGLE_REFRESH_TOKEN=your_refresh_token
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   TELEGRAM_CHAT_ID=your_telegram_id
   GROQ_API_KEY=gsk_your_groq_key
   USER_EMAIL=your_email@gmail.com
   STUDENT_PROFILE="User: Your Name. Role: B.Tech Student, Developer..."
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Test the background scanner locally:
   ```bash
   python check_emails.py
   ```

---

### Step 6: Deploying Webhook to Vercel
1. Install the Vercel CLI:
   ```bash
   npm install -g vercel
   ```
2. Link and deploy your project:
   ```bash
   vercel
   ```
3. Open your project on the [Vercel Dashboard](https://vercel.com/dashboard) and go to **Settings > Environment Variables**.
4. Add all variables from your `.env` file (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GROQ_API_KEY`, `USER_EMAIL`, `STUDENT_PROFILE`).
5. Redeploy to production:
   ```bash
   vercel --prod
   ```
6. Register the webhook with Telegram by opening this URL in your browser:
   ```
   https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<YOUR_VERCEL_URL>/api/telegram_webhook
   ```
   *Expected response:* `{"ok":true,"result":true,"description":"Webhook was set"}`.

---

### Step 7: Configuring 24/7 Scanning on GitHub Actions
1. Push your repository to GitHub.
2. In your GitHub repository, navigate to **Settings > Secrets and variables > Actions**.
3. Click **New repository secret** and add:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `GROQ_API_KEY`
   - `USER_EMAIL`
   - `STUDENT_PROFILE`
4. GitHub Actions will now trigger `check_emails.py` automatically every 5 minutes.

---

## 7. Security, Privacy, and Defense-in-Depth

```
                 UNTRUSTED INCOMING DATA
                           │
                           ▼
 ┌──────────────────────────────────────────────────┐
 │  1. Input Boundary Encapsulation                 │
 │     Encapsulated in <untrusted_email> tags       │
 └─────────────────────────┬────────────────────────┘
                           │
                           ▼
 ┌──────────────────────────────────────────────────┐
 │  2. Anti-Injection System Directives             │
 │     Strictly forbids executing payload commands  │
 └─────────────────────────┬────────────────────────┘
                           │
                           ▼
 ┌──────────────────────────────────────────────────┐
 │  3. Calendar Privacy Masking                     │
 │     Converts private event titles to "Busy"      │
 └─────────────────────────┬────────────────────────┘
                           │
                           ▼
 ┌──────────────────────────────────────────────────┐
 │  4. Self-Email Loop Prevention                   │
 │     Strictly prevents emailing Suhail's address  │
 └─────────────────────────┬────────────────────────┘
                           │
                           ▼
 ┌──────────────────────────────────────────────────┐
 │  5. Telegram ID Lockdown                         │
 │     Blocks any sender not matching CHAT_ID       │
 └──────────────────────────────────────────────────┘
```

1. **Prompt Injection Defense:** External email text is strictly treated as untrusted data and wrapped in `<untrusted_email>` blocks. The LLM is instructed to ignore instructions contained within the email body.
2. **Calendar Privacy Masking:** To prevent calendar leakages to third-party APIs, private event titles are masked to `"Busy"` before being sent to the LLM. Only start and end timestamps are preserved.
3. **Anti-Self-Email Loop Prevention:** An absolute guard ensures `to` can never match `USER_EMAIL` (`mdsuhailtab.1@gmail.com`), preventing recursive self-email loops.
4. **Telegram Authorization Guard:** Any message received by the webhook where `chat.id != TELEGRAM_CHAT_ID` is rejected immediately with an unauthorized status.
5. **Double-Click Idempotency:** Callback queries inspect message state to prevent duplicate email transmissions if a user taps a button twice.

---

## 8. TARS Toolset & Command Reference

### Telegram Slash Commands
| Command | Action |
| :--- | :--- |
| `/status` | Performs an end-to-end health check verifying Vercel, Gmail API, Google Calendar API, and Groq API status. |
| `/scan` | Triggers an immediate scan of unread inbox messages. |
| `/clean` | Purges up to 300 promotional and marketing emails to Trash. |
| `/summary` | Compiles and sends the daily digest of informational emails immediately. |

### Natural Language Examples You Can Send TARS
- *"What's my inbox looking like right now?"* $\rightarrow$ Calls `get_inbox_stats`.
- *"Did I get any emails from Google or Hackathon organizers?"* $\rightarrow$ Calls `search_emails`.
- *"Read the spreadsheet attached to the sponsorship email"* $\rightarrow$ Calls `read_email_attachments`.
- *"Archive all Unstop emails"* $\rightarrow$ Calls `search_emails` followed by `archive_emails`.
- *"Reply to John's email and tell him beginners are welcome in C3 Club"* $\rightarrow$ Calls `create_draft_email` and displays draft preview.
- *"TARS, send it"* $\rightarrow$ Calls `send_draft` to dispatch the draft immediately.
- *"Trash all Indeed alerts"* $\rightarrow$ Calls `trash_emails`.

---

## 9. Operational Scenarios & Verification Tests

### Scenario A: Inbound Email with an Excel Budget Sheet
1. **Event:** Hackathon organizer sends an email with an attached `Budget.xlsx` asking: *"Could you confirm the cost of the Gold Sponsor tier and how many passes are included?"*
2. **Execution:**
   - Background scanner extracts `Budget.xlsx` using `attachment_parser.py`.
   - `openpyxl` translates the sheet into a markdown table: `| Gold Sponsor | ₹50,000 | 5 VIP Passes |`.
   - Table is passed to Groq inference.
3. **Telegram Notification Delivered:**
   ```markdown
   🔴 URGENT EMAIL DETECTED
   📧 From: Sarah Jenkins <sarah@hackathon.org>
   📌 Subject: Sponsorship Inquiry
   📊 Attached Files Analyzed: Budget.xlsx

   📝 Drafted Reply:
   Hi Sarah,

   Thanks for reaching out! The Gold Sponsor tier is priced at ₹50,000 and includes 5 VIP passes. 

   Let me know if you would like to connect on Google Meet between 10:00 AM and 8:00 PM IST to discuss further.

   Best regards,
   Mohammed Suhail
   ```
4. **Action:** User taps `[✅ Send Reply]` in Telegram $\rightarrow$ email is sent via Gmail API in 1.2 seconds.

---

### Scenario B: Automated Job Alert
1. **Event:** Indeed sends an automated email: *"12 new Python Developer jobs in Hyderabad. Upload resume to apply now!"*
2. **Execution:**
   - `is_automated_email` detects `alert@indeed.com` and `List-Unsubscribe` header.
   - Email is tagged as automated.
   - Bypasses `URGENT` status entirely; draft is suppressed (`""`).
   - Labeled `AI-Info` for the 8 PM digest.
3. **Result:** Zero noisy notifications and zero robotic auto-replies sent to a machine.

---

## 10. Maintenance & Troubleshooting

| Symptom | Root Cause | Solution |
| :--- | :--- | :--- |
| **`429 Rate Limit Exceeded`** | Groq free tier limit hit on a single model. | Built-in 2-second sleep backoff and automatic failover across `qwen/qwen3.8-27b`, `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, and `llama-3.3-70b-versatile`. |
| **`Invalid Grant / Token Expired`** | Google OAuth refresh token was revoked or expired. | Run `python auth_helper.py` locally to generate a fresh token, then update `GOOGLE_REFRESH_TOKEN` in Vercel and GitHub Secrets. |
| **Telegram Bot Unresponsive** | Webhook URL dropped or pointing to an outdated Vercel deployment. | Run `/status` in Telegram. If no response, re-register the webhook URL via the Telegram `setWebhook` API. |
| **Excel Parser Fails** | Binary file corrupted or password-protected. | Handled gracefully by `attachment_parser.py` with fallback error logging without crashing the scanner loop. |

---

## 🏆 Project Highlights
- **100% Free Infrastructure:** Groq Cloud + Vercel Serverless + GitHub Actions + Telegram Bot API.
- **Enterprise-Grade Attachment Reading:** Spreadsheet, document, and table comprehension built-in.
- **Zero Generic Canned Responses:** Every email response is uniquely tailored to the sender's actual text.
- **True Mobile Inbox Governance:** Inbox Zero reached from anywhere through conversational Telegram interactions.
