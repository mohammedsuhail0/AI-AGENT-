# PRD — Product Requirements Document

## 1. Introduction & Background
As a student in India, important academic, internship, and scholarship opportunities are often missed because email inboxes are cluttered with spam, promotions, and newsletter noise. Students do not check their emails regularly, relying instead on messaging apps like WhatsApp or Telegram. 

This product is a **Personal Email AI Agent** designed to monitor a Gmail inbox, filter out the noise, identify high-value opportunities, draft intelligent responses using local/personal context (like a calendar or resume), and present them to the user for instant authorization via a Telegram bot.

---

## 2. Problem Statement
1. **Inbox Clutter:** The ratio of spam/promotional emails to genuine, action-oriented opportunities is extremely high, causing students to experience "email fatigue."
2. **Delayed Response:** Important emails (e.g., interview invites, deadlines) require fast response times, but students check email too infrequently.
3. **Drafting Friction:** Writing professional, context-aware emails (e.g., suggesting calendar availability) takes time and effort.

---

## 3. Goals & User Persona
### User Persona
* **Name:** Aravind (Indian College Student)
* **Behavior:** Checks WhatsApp/Telegram dozens of times a day; checks Gmail once a week.
* **Pain Point:** Missed a scholarship deadline and a placement cell interview invitation last semester.

### Product Goals
* **Zero Missed Opportunities:** Ensure 100% of high-priority emails trigger an instant mobile notification.
* **Zero Cost:** The system must run entirely on free-tier platforms without any monthly costs.
* **Frictionless Approval:** Replying to a critical email must be as simple as tapping a single button on a phone.
* **Data Privacy:** Keep authentication credentials and email data personal and secure.

---

## 4. Scope & Feature List

### Feature 1: Intelligent Scanner
* **Gmail Integration:** Connect to the user's Gmail inbox via OAuth 2.0.
* **Label-Based State Management:** Mark scanned emails with a Gmail label (`AI-Scanned`) to avoid duplicate processing.
* **Gemini-Powered Categorization:** Categorize emails into:
  * `URGENT` (Immediate action required: interviews, official announcements, deadlines).
  * `INFO` (No action required, but good to know: class notes, grades).
  * `SPAM` (Promotional, newsletters, ignore).

### Feature 2: Automated Drafter (Gemini AI)
* **Contextual Drafting:** Draft a professional reply using:
  * The original email context.
  * Your personal profile (resume text, typical tone of voice).
* **Calendar Scheduling:** Scan your Google Calendar to find free slots if the email asks for availability, and insert them into the draft.

### Feature 3: Telegram Interface
* **Push Notifications:** Instant notification on your phone via Telegram Bot when an `URGENT` email is received.
* **Interactive Inline Buttons:**
  * `[ ✅ Approve & Send ]` - Sends the draft immediately.
  * `[ 📝 Edit Draft ]` - Allows modifying the reply before sending.
  * `[ ❌ Ignore ]` - Archives the email.
* **Daily Digest:** A daily summary sent at 8:00 PM listing all `INFO` category emails received during the day.

---

## 5. Non-Functional Requirements (NFRs)
* **Cost:** $0.00 USD/month.
* **Response Latency:** Webhook approval response time must be under 3 seconds (achieved via Vercel Serverless).
* **Reliability:** GitHub Actions runs consistently every 15 minutes to scan mail.
* **Portability:** Easy to redeploy for other personal email accounts.
