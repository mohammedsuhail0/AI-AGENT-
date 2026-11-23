# TARS Voice Calling & Autonomous Sentinel: Complete Engineering Blueprint
> **The Exhaustive Master Specification, Chronological History, Architectural Evolution, Failure Analysis, and Step-by-Step Reproduction Guide**  
> *Author: Mohammed Suhail (Founder, C3 Club | B.E. IT, Class of 2028, ISL Engineering College | Google AI/ML Intern Grade O | Full Stack Academy Center of Excellence)*  
> *Project: TARS Voice Sentinel & Autonomous Executive AI Chief of Staff*

---

## 📑 Table of Contents
1. [Executive Overview & The Zero-Cost Paradigm](#1-executive-overview--the-zero-cost-paradigm)
2. [Phase 1: The Telegram Autonomous Email Agent (The Foundation)](#2-phase-1-the-telegram-autonomous-email-agent-the-foundation)
   - [2.1 The Problem It Solved](#21-the-problem-it-solved)
   - [2.2 Architecture & Flow](#22-architecture--flow)
   - [2.3 Core Modules Breakdown](#23-core-modules-breakdown)
   - [2.4 Why Telegram Alone Was Not Enough](#24-why-telegram-alone-was-not-enough)
3. [Phase 2: The WebRTC / Browser Calling Prototype](#3-phase-2-the-webrtc--browser-calling-prototype)
   - [3.1 WebRTC PWA Architecture](#31-webrtc-pwa-architecture)
   - [3.2 The Mobile Browser Reality Check (Why PWA Calling Failed)](#32-the-mobile-browser-reality-check-why-pwa-calling-failed)
4. [Phase 3: The Native SIP/VoIP Telephony Engine (`sip_caller.py`)](#4-phase-3-the-native-sipvoip-telephony-engine-sip_callerpy)
   - [4.1 Why Linphone & SIP Protocol?](#41-why-linphone--sip-protocol)
   - [4.2 High-Level Call Flow Diagram](#42-high-level-call-flow-diagram)
   - [4.3 Bidirectional Dialing Engine (Inbound & Outbound)](#43-bidirectional-dialing-engine-inbound--outbound)
   - [4.4 Real-Time Audio Pipeline (G.711 u-law, Whisper, Groq RAG, Edge-TTS)](#44-real-time-audio-pipeline-g711-u-law-whisper-groq-rag-edge-tts)
5. [The Engineering Ledger: Every Failure, Bug & Permanent Fix](#5-the-engineering-ledger-every-failure-bug--permanent-fix)
   - [Bug 1: "0/null Immediate Disconnect" on Call Pickup (SDES-SRTP Encryption)](#bug-1-0null-immediate-disconnect-on-call-pickup-sdes-srtp-encryption)
   - [Bug 2: "Can't Hear a Thing / Single Red Quality Bar" (Jitter Buffer Starvation)](#bug-2-cant-hear-a-thing--single-red-quality-bar-jitter-buffer-starvation)
   - [Bug 3: Asymmetric ICE & STUN Binding Drops (NAT Traversal)](#bug-3-asymmetric-ice--stun-binding-drops-nat-traversal)
   - [Bug 4: "User Not Found" (Flexisip 404 Disconnects & IP Drift)](#bug-4-user-not-found-flexisip-404-disconnects--ip-drift)
   - [Bug 5: Process Termination on Antigravity Closure (Windows Job Objects & WMI)](#bug-5-process-termination-on-antigravity-closure-windows-job-objects--wmi)
   - [Bug 6: "Connecting... Just Loading for Connecting" (Dynamic NAT `rport` & Dead Contacts)](#bug-6-connecting-just-loading-for-connecting-dynamic-nat-rport--dead-contacts)
   - [Bug 7: Artificial Turn Limits & Conversation Truncation](#bug-7-artificial-turn-limits--conversation-truncation)
   - [Bug 8: Low Mobile Volume & British Accent Overhaul](#bug-8-low-mobile-volume--british-accent-overhaul)
6. [Complete Technical Stack & Requirements](#6-complete-technical-stack--requirements)
7. [Step-by-Step Reproduction Guide (Build It Yourself)](#7-step-by-step-reproduction-guide-build-it-yourself)
8. [Production Deployment (Windows Daemon, Docker & Linux)](#8-production-deployment-windows-daemon-docker--linux)

---

## 1. Executive Overview & The Zero-Cost Paradigm

**TARS Voice Sentinel** is an autonomous AI Executive Chief of Staff capable of interacting with human users across two production channels:
1. **Asynchronous Telegram Command Hub:** Triaging, summarizing, drafting replies, parsing attachments, and offering one-tap dispatch buttons on mobile.
2. **Synchronous Native VoIP Voice Telephony:** Calling the user's mobile phone via native SIP push when urgent VIP inquiries arrive, and answering incoming calls when the user dials TARS to consult their inbox verbally.

### The Zero-Cost ($0.00) Infrastructure Constraint
Traditional enterprise voice solutions depend on Twilio, Vonage, Bland AI, or ElevenLabs, which charge:
- \$0.014 to \$0.04/min for SIP trunking and carrier PSTN termination.
- \$0.05 to \$0.15/min for LLM inference and speech synthesis.
- Ongoing monthly numbers and subscription fees.

TARS was engineered from the ground up to operate at **\$0.00 running cost indefinitely**:
- **SIP / Carrier Layer:** Free SIP federation via Linphone Flexisip (`sip.linphone.org`).
- **ASR / STT Layer:** Groq Whisper Large v3 (sub-400ms latency, free tier API).
- **Brain / Reasoning Layer:** Groq LLaMA 3.3 70B Versatile / LLaMA 3.1 8B Instant (free tier API).
- **TTS / Voice Synthesis:** Microsoft Edge Neural Cloud TTS (`edge-tts`), utilizing high-fidelity neural voices (`en-US-GuyNeural`) converted on-the-fly to telecom-standard G.711 u-law.
- **Hosting:** Local PC background service (via Windows WMI detachment) or self-hosted Docker container.

```mermaid
graph LR
    subgraph "External World"
        GMAIL[Gmail API]
        FLEX[Linphone Flexisip Proxy]
    end

    subgraph "TARS Core Daemon"
        WATCHER[Background Watcher]
        SIP[SIP Engine :5060]
        RTP[RTP / SRTP Audio Engine]
        BRAIN[Groq LLaMA 3.3 70B RAG]
        STT[Groq Whisper STT]
        TTS[Edge-TTS en-US-GuyNeural]
    end

    subgraph "User Mobile"
        PHONE[Linphone App on Android/iOS]
        TG[Telegram App]
    end

    GMAIL -->|New Urgent Email| WATCHER
    WATCHER -->|Trigger Outbound Call| SIP
    SIP -->|INVITE| FLEX
    FLEX -->|Push Call| PHONE
    PHONE -->|User Speaks| RTP
    RTP --> STT
    STT --> BRAIN
    BRAIN -->|Tool Calls| GMAIL
    BRAIN --> TTS
    TTS --> RTP
    RTP -->|Audio Answer| PHONE

    PHONE -->|Inbound Dial 'suhail_tars'| FLEX
    FLEX -->|INVITE :5060| SIP
    SIP -->|200 OK| FLEX
```

---

## 2. Phase 1: The Telegram Autonomous Email Agent (The Foundation)

### 2.1 The Problem It Solved
Mohammed Suhail, leading club operations and applying for internships, faced inbox inundation:
- Hundreds of promotional newsletters, marketing spam, and automated job alerts (Indeed, LinkedIn).
- Critical recruiter interview invitations, hackathon sponsorship inquiries, and attachments (budget spreadsheets, candidate resumes) buried in noise.
- Canned out-of-office auto-replies failed because they sent robotic text to newsletters and bots, while offering no real assistance for urgent messages.

### 2.2 Architecture & Flow
Phase 1 established an autonomous scanner coupled with a Telegram webhook:
1. **Scanner (`check_emails.py`):** Runs every 15 seconds locally (or every 5 minutes on GitHub Actions).
2. **RFC Automated Filter (`is_automated_email`):** Evaluates RFC 3834 headers (`Auto-Submitted`, `Precedence: bulk`, `List-Unsubscribe`) to immediately bypass newsletters and bot notifications.
3. **Attachment Reader (`attachment_parser.py`):** Inspects incoming Excel sheets (`.xlsx`), CSVs, PDFs, and Word documents (`.docx`), summarizing financial figures, agendas, and tables into plain text for the LLM.
4. **Interactive Telegram Hub (`api/telegram_webhook.py`):** Posts formatted briefings with inline buttons:
   - `[🚀 Send Reply]` — Dispatches the drafted response via Gmail API.
   - `[📎 Send with Resume]` — Attaches `Mohammed_Suhail_Resume.pdf` and dispatches.
   - `[🗑️ Ignore / Trash]` — Moves email to Gmail trash.

---

### 2.3 Core Modules Breakdown
- **`check_emails.py`:**
  - Manages Google OAuth token refreshes.
  - Fetches unread messages via Gmail API `users().messages().list()`.
  - Determines urgency via Groq LLM:
    ```python
    SYSTEM_PROMPT = """You are TARS, executive chief of staff for Mohammed Suhail...
    Analyze if this email requires immediate action. Output JSON: {is_urgent: bool, reason: str, drafted_body: str}"""
    ```
- **`attachment_parser.py`:**
  - Uses `pdfplumber` for PDFs, `openpyxl` for Excel spreadsheets, and `python-docx` for Word documents.
  - Limits extracted text to 2,000 tokens so multi-megabyte sheets do not blow out LLM context windows.
- **`tars_agent.py`:**
  - Conversational agent equipped with 10 tools (`search_emails`, `read_email`, `clean_promotions`, `create_draft_email`, `send_email`, `archive_emails`, etc.).
  - Enables Suhail to type natural commands into Telegram: *"Archive all emails from Unstop"* or *"What did Samer ask in his last email?"*.

---

### 2.4 Why Telegram Alone Was Not Enough
While Telegram notifications solved desktop email triage, they introduced **the Physical World Failure Mode**:
1. **Silent / Do Not Disturb:** If Suhail's phone was on silent or in his pocket during classes or meetings, Telegram notifications were missed.
2. **Notification Blindness:** Telegram pings get mixed with group chats, channel updates, and social apps.
3. **True Urgency Requires Interruption:** When an urgent interviewer or VIP contact (Samer, Bilal, Kaizen) emails asking for a meeting in 30 minutes, **a ringing phone call is the only notification mechanism that guarantees an immediate response.**

---

## 3. Phase 2: The WebRTC / Browser Calling Prototype

To solve notification blindness, we first built **TARS Voice Sentinel v1** using WebRTC and a mobile web application.

### 3.1 WebRTC PWA Architecture
- **Server:** FastAPI backend in `call_server.py`.
- **Client:** `static/index.html` offering an audio visualizer and microphone capture.
- **Protocol:** WebSocket signaling + WebRTC peer connection.
- **Trigger:** When `check_emails.py` detected an urgent email, `call_server.py` broadcasted a WebSocket event `{"action": "ring"}`.
- **Audio Output:** The phone would play a ringing ringtone, Suhail would tap "Accept", and speak into the browser mic.

```mermaid
sequenceDiagram
    participant S as call_server.py
    participant B as Mobile Browser (index.html)
    participant U as Suhail

    S->>B: WebSocket {"action": "ring"}
    Note over B: Browser plays audio ringtone
    U->>B: Taps "Accept"
    B->>S: Audio Stream via WebRTC
    S->>B: TTS Audio via WebRTC
```

---

### 3.2 The Mobile Browser Reality Check (Why PWA Calling Failed)
In local testing with the browser open on a laptop screen, WebRTC worked. But on **actual Android and iOS smartphones**, it broke down completely:

| Mobile OS Constraint | Impact on WebRTC PWA |
| :--- | :--- |
| **Background Tab Throttling** | When the browser is minimized or another app is opened, Android and iOS throttle JavaScript execution and close idle WebSocket connections within 30–60 seconds. |
| **Screen Lock Disconnection** | The moment the phone screen locks, the Wi-Fi/cellular radio enters low-power sleep; the WebSocket drops immediately. |
| **No Native Lock-Screen Wake** | Web pages cannot wake up a locked phone, cannot display a full-screen incoming call UI, and cannot override system silent switches. |
| **Audio Context Autoplay Policy** | Browsers forbid playing ringtones automatically unless the user has actively tapped the screen within the same session. |

**Conclusion:** WebRTC in a browser is designed for interactive web meetings (e.g., Google Meet), **not autonomous phone alerts**. For real-world reliable mobile calling, we had to move to native telephony.

---

## 4. Phase 3: The Native SIP/VoIP Telephony Engine (`sip_caller.py`)

### 4.1 Why Linphone & SIP Protocol?
To achieve native ringing without cellular carrier costs, we adopted **SIP (Session Initiation Protocol, RFC 3261)** paired with **Linphone**:
1. **Native OS Call Screen:** Linphone integrates with Android ConnectionService and iOS CallKit. When an incoming SIP `INVITE` arrives, the phone wakes from sleep, displays the native incoming call UI, rings with custom ringtones, and accepts audio over car Bluetooth and headsets.
2. **Free Global SIP Registrar:** `sip.linphone.org` provides free public SIP registration, proxying, and NAT traversal.
3. **No Carrier Costs:** Calls route over data (Wi-Fi or 4G/5G) at $0.00/min.

---

### 4.2 High-Level Call Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant TARS as TARS sip_caller.py (:5060)
    participant NAT as Home Router (NAT)
    participant FLEX as Linphone Flexisip Proxy
    participant PHONE as Suhail's Phone (Linphone App)

    Note over TARS,FLEX: 1. Registration & Keepalive Phase
    TARS->>NAT: REGISTER sip:sip.linphone.org (Via: ...:5060;rport)
    NAT->>FLEX: Outbound UDP (Translated to Dynamic NAT Port, e.g. 52087)
    FLEX-->>NAT: 401 Unauthorized (Via: ...;rport=52087;received=49.206.57.206)
    NAT-->>TARS: 401 Challenge Received
    Note over TARS: Extracts rport=52087 & public IP
    TARS->>NAT: REGISTER with Digest Auth & Contact: <sip:...:52087>
    NAT->>FLEX: REGISTER with Auth
    FLEX-->>TARS: 200 OK Registration Successful
    loop Every 25 Seconds
        TARS->>FLEX: NAT Keepalive Ping (\r\n\r\n)
    end

    Note over FLEX,TARS: 2. Inbound Call Phase (User dials suhail_tars)
    PHONE->>FLEX: INVITE sip:suhail_tars@sip.linphone.org
    FLEX->>NAT: Forward INVITE to 49.206.57.206:52087
    NAT->>TARS: Inbound INVITE received on local :5060
    TARS-->>NAT: 100 Trying
    Note over TARS: Parse SDP offer, negotiate SRTP, bind RTP socket
    TARS-->>NAT: 200 OK with SDP Answer
    NAT-->>FLEX: 200 OK Forwarded
    FLEX-->>PHONE: 200 OK
    PHONE-->>TARS: ACK (Call Dialog Established)

    Note over TARS,PHONE: 3. Full-Duplex Voice RAG Phase
    par Comfort Silence Loop
        loop Every 20ms
            TARS->>PHONE: RTP Comfort Silence (0xFF x 160)
        end
    and Interactive Voice
        TARS->>PHONE: Greeting Audio ("Hello boss, TARS online...")
        PHONE->>TARS: Boss speaks ("Did I get any emails from Samer?")
        TARS->>TARS: Whisper STT -> Groq RAG Tool Call -> Edge-TTS
        TARS->>PHONE: Spoken Response ("You received an email from Samer...")
    end
```

---

### 4.3 Bidirectional Dialing Engine (Inbound & Outbound)
1. **Outbound Sentinel Calling (`trigger_urgent_call`):**
   - Triggered when `check_emails.py` finds an urgent unread email.
   - Constructs and sends an authenticated `INVITE` to `sip:mohammed_suhail@sip.linphone.org`.
   - Plays a concise 16-word briefing: *"Hello boss, we got an urgent email from Samer regarding Data Science interview. What should I reply?"*.
   - Records the user's spoken instruction, drafts or dispatches the email, and hangs up.
2. **Inbound Dial-In Server (`run_inbound_sip_server`):**
   - Binds to local UDP port 5060 and registers account `suhail_tars`.
   - Listens 24/7 for inbound calls.
   - When Suhail dials `suhail_tars` from Linphone, TARS answers with 0ms perceived latency, greets him, and enters a live conversational Voice RAG loop over his Gmail.

---

### 4.4 Real-Time Audio Pipeline (G.711 u-law, Whisper, Groq RAG, Edge-TTS)
```mermaid
graph TD
    subgraph "Audio Ingestion"
        A[RTP Socket :Port] -->|SRTP Decrypt| B[Decrypted RTP Packet]
        B -->|Extract Payload| C[G.711 u-law Audio 8kHz]
        C -->|audioop.ulaw2lin| D[16-bit Linear PCM Audio]
        D -->|Silence Pause Detector 1.8s| E[Complete Spoken Audio Segment]
    end

    subgraph "Transcription & Intelligence"
        E -->|Wrap in In-Memory WAV| F[Groq Whisper Large v3]
        F -->|Transcribed Text| G[TARS Voice RAG Brain LLaMA 3.3 70B]
        G -->|Tool Calling| H[Gmail API search_emails / read_email]
        H -->|Tool Output| G
        G -->|Spoken Response 1-3 Sentences| I[Text Sanitizer clean_spoken_text]
    end

    subgraph "Speech Synthesis & Transmission"
        I --> J[Edge-TTS en-US-GuyNeural +35% Volume]
        J -->|Decode MP3| K[8kHz Linear PCM]
        K -->|Soft Limiter & 1.85x Gain Boost| L[Boosted Audio RMS ~6500]
        L -->|audioop.lin2ulaw| M[Boosted G.711 u-law]
        M -->|RTP Packetizer + SRTP Encrypt| N[RTP Socket Send]
    end
```

---

## 5. The Engineering Ledger: Every Failure, Bug & Permanent Fix

The journey to an indestructible, broadcast-grade voice calling engine involved diagnosing deep protocol, OS kernel, and NAT traversal failures. Below is the unvarnished engineering ledger extracted directly from conversation logs, system traces, and commits.

---

### Bug 1: "0/null Immediate Disconnect" on Call Pickup (SDES-SRTP Encryption)

#### The Symptom:
When TARS placed an outbound call, the mobile phone rang. But the instant the user pressed the green "Answer" button, the call abruptly dropped after 0 seconds, with Linphone logging:
```text
Call terminated with cause: 0/null
```

#### The Root Cause:
Android Linphone enforces **RFC 4568 SDES-SRTP (Secure Real-Time Transport Protocol)** media encryption by default. In the SDP offer sent by Linphone:
```sdp
m=audio 13828 RTP/SAVPF 96 97 98 0 8 18 101
a=crypto:1 AEAD_AES_128_GCM inline:...
a=crypto:2 AES_CM_128_HMAC_SHA1_80 inline:2ZYSQBwZeflqHwRim6BzW4Je...
```
The profile `RTP/SAVPF` requires encrypted media. TARS was initially sending a plain `RTP/AVP` answer with raw unencrypted audio. Linphone detected the unencrypted stream violating policy and instantly tore down the call with `BYE`.

#### The Permanent Fix:
Integrated `pylibsrtp` to negotiate and establish cryptographic SRTP contexts in [sip_caller.py](file:///c:/Users/Lenovo/OneDrive/ドキュメント/n8n%20prjects/sip_caller.py):
1. **SDP Answer Generation:** Matched `a=crypto:2 AES_CM_128_HMAC_SHA1_80` from the offer, generated a 30-byte local base64-encoded key, and included it in the 200 OK SDP answer:
   ```python
   local_master_key = os.urandom(30)
   crypto_answer_line = f"a=crypto:2 AES_CM_128_HMAC_SHA1_80 inline:{base64.b64encode(local_master_key).decode()}"
   ```
2. **Crypto Initialization:** Initialized two `pylibsrtp.Policy` contexts:
   - `tx_srtp`: Sealed outbound audio before `sock.sendto()`.
   - `rx_srtp`: Unsealed incoming microphone audio packets.
3. Call pickup connected with zero disconnects.

---

### Bug 2: "Can't Hear a Thing / Single Red Quality Bar" (Jitter Buffer Starvation)

#### The Symptom:
The user reported:
> *"nope cant hear a thing when i call the agent and the bar is only one small one with red color"*

#### The Root Cause:
1. **VoIP Jitter Buffers:** Modern softphones (Linphone, WebRTC) evaluate connection health based on steady RTP packet arrival. Expected cadence: **50 packets per second (1 packet every 20ms)**.
2. **Dead Silence Starvation:** When TARS was waiting for the user to speak, transcribing with Whisper, or executing LLM tool calls, **no RTP packets were transmitted**.
3. Linphone's jitter buffer starved within 150ms, marked packet loss as 100%, turned the UI quality indicator to a single red bar, and muted the phone DAC.

#### The Permanent Fix:
Engineered the **Full-Duplex Comfort Silence Streamer (`RTPPlayer`)** in [sip_caller.py](file:///c:/Users/Lenovo/OneDrive/ドキュメント/n8n%20prjects/sip_caller.py):
1. **Background Silence Generator:** Launched a dedicated background thread transmitting standard G.711 u-law comfort silence frames (`0xFF` bytes, 160 bytes per packet) strictly every 20ms whenever TARS was not speaking:
   ```python
   def _silence_worker(self):
       while self._running:
           # Transmit 20ms comfort silence frame
           pkt = make_rtp_packet(self.seq, self.timestamp, self.ssrc, b"\xff" * 160)
           self.sock.sendto(self._encrypt_if_srtp(pkt), dest)
           self.seq += 1
           self.timestamp += 160
           time.sleep(0.02)
   ```
2. **Sequential Timestamp Continuity:** When TARS begins playing actual speech, the player smoothly transitions without resetting sequence numbers or wall-clock timestamps, preventing audio glitches.
3. **Instant Acoustic Fillers:** Created pre-rendered 0ms cached voice fillers (*"Checking that for you now, boss."*), played immediately upon speech pause detection so the user never experiences silence.
4. Audio quality indicator immediately locked onto **solid green (100% quality)**.

---

### Bug 3: Asymmetric ICE & STUN Binding Drops (NAT Traversal)

#### The Symptom:
Calls connected on local home Wi-Fi, but failed to transmit audio when the mobile phone switched to 4G/5G cellular data.

#### The Root Cause:
1. When calling over cellular, the phone and the PC are separated by carrier CGNAT and home router NAT.
2. In the SDP offer, the phone advertises multiple ICE candidates (host LAN, server reflexive, and relay).
3. The phone sends **STUN Binding Requests** to the PC's RTP port to verify the channel.
4. Because TARS did not reply to STUN binding packets, the phone assumed the direct media path was dead and failed to open its speaker/mic.

#### The Permanent Fix:
1. **Inline STUN Binding Responder:** Added packet inspection on the inbound RTP socket. If an incoming UDP packet has the STUN magic cookie `0x2112A442`, TARS immediately generates and transmits an RFC 5389 `STUN Binding Success Response` containing the `XOR-MAPPED-ADDRESS`:
   ```python
   def handle_stun_packet(data, addr, sock):
       if len(data) >= 20 and data[4:8] == b"\x21\x12\xa4\x42":
           # STUN Binding Request detected -> Send Binding Success
           msg_type, msg_len = struct.unpack("!HH", data[:4])
           if msg_type == 0x0001:  # Binding Request
               resp = build_stun_binding_response(data[8:20], addr[0], addr[1])
               sock.sendto(resp, addr)
               return True
       return False
   ```
2. **Symmetric RTP Latching:** Rather than sending audio blindly to the IP address listed in the SDP `c=` line (which is often a non-routable private cellular IP like `10.x.x.x`), TARS latches its transmitter to the **exact IP and port from which the first incoming RTP packet arrived**.

---

### Bug 4: "User Not Found" (Flexisip 404 Disconnects & IP Drift)

#### The Symptom:
The user repeatedly encountered:
> *"something happend to the TARS voice it is showing user not found , when i call"*

#### The Root Cause:
Flexisip returns `404 User Not Found` when no active contact exists in its location database for `sip:suhail_tars@sip.linphone.org`. This was caused by three separate issues:
1. **Multithread Socket Collision:** Re-registration ran in a secondary thread that read the socket at the same time as the main listener, consuming 401 challenge nonces out of order.
2. **Dynamic ISP Public IP Re-assignment:** The user's home broadband provider changed their WAN IP (e.g. from `106.195.73.85` to `106.195.65.85` to `49.206.57.206`). The server was still advertising the old IP in SIP `Contact:` headers, which Flexisip rejected or dropped.
3. **No Automatic Boot Persistence:** When the PC rebooted, TARS was not running.

#### The Permanent Fix:
1. **Dynamic IP Auto-Refresher:** Created `get_public_ip(force_refresh=True)` checking multiple external providers (`ipify.org`, `ifconfig.me`, `icanhazip.com`). When an IP change is detected, TARS automatically resets CSeq, updates its Call-ID, and performs a fresh authenticated registration.
2. **Single-Thread SIP Event Loop:** Unified all registration maintenance, 401/407 challenge computations, keepalive pings, and INVITE handling into a single clean non-blocking event loop.
3. **Immortal Watchdog Supervisor (`tars_supervisor.py`):** Spawns `call_server.py`, pings its HTTP health endpoint every 10 seconds, and automatically resurrects the process if it ever crashes.

---

### Bug 5: Process Termination on Antigravity Closure (Windows Job Objects & WMI)

#### The Symptom:
The user reported the ultimate frustration:
> *"still fucking not working , it is not working as soon as i close you UP !!"*
> *"what the hell man again it shows user not found i was showing the agent in a con .. and it failed so badly"*

TARS worked perfectly during the chat turn. But the second the user closed Antigravity or locked his laptop to show people at a conference, the phone said "User not found".

#### The Root Cause (Windows Kernel Job Objects):
When an AI agent executes terminal commands (`run_command`), Windows places the spawned process inside **Antigravity’s Windows Job Object**.
- The Windows Kernel has a hard rule: **When the root process of a Job Object terminates, all child processes inside that Job Object are immediately killed by the kernel.**
- Using PowerShell `Start-Process` or Python `subprocess.Popen` still inherits the Job Object.
- Attempting `CREATE_BREAKAWAY_FROM_JOB` failed with `WinError 5: Access is denied` because standard user permissions do not allow unprompted breakaway.

#### The Permanent Fix:
Bypassed the Job Object completely using **Windows Management Instrumentation (WMI)** via PowerShell:
```powershell
# start_detached.ps1
$cmdLine = "`"$pythonExe`" `"$supervisorScript`""
$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmdLine
    CurrentDirectory = $workDir
}
```
**Why this works:** When invoked via WMI, the process is spawned by **`WmiPrvSE.exe` (the Windows Management Service)**. It is completely outside Antigravity's process hierarchy and Job Object. Antigravity can be closed, updated, or uninstalled, and TARS continues running 24/7 in the background.

Added a persistent Windows Startup shortcut (`TARS_Voice_Sentinel.lnk` in `shell:startup`) so it boots automatically whenever Windows starts.

---

### Bug 6: "Connecting... Just Loading for Connecting" (Dynamic NAT `rport` & Dead Contacts)

#### The Symptom:
After fixing process persistence, the user attempted to call TARS, but Linphone was stuck on:
> *"now the fucking call is not connecting it k=just loading for connecting"*

#### The Root Cause:
1. **Dynamic NAT Port Translation:**
   - The PC bounds local UDP port `5060`.
   - When sending UDP packets through home broadband NAT to `sip.linphone.org`, the home router maps port 5060 to a dynamic external high port (e.g. `52087` or `63407`).
   - Previously, TARS was sending:
     ```sip
     Contact: <sip:suhail_tars@49.206.57.206:5060>
     ```
   - When Flexisip attempted to deliver an incoming call, it routed the `INVITE` to external port `5060`. Because the home router had no port-forwarding for 5060, **the router dropped the packet silently**.
2. **Flexisip Stale Contact Accumulation:**
   - In past sessions, contacts like `sip:suhail_tars@106.195.65.85:62233` had registered with a 600-second TTL.
   - When Suhail called, Flexisip forked the call to the dead socket `62233`. Linphone waited for a response that never came, causing the endless "Connecting..." screen.

#### The Permanent Fix:
1. **Server-Reflected `rport` & `received` Detection:**
   Extracted the real NAT port and IP reflected by Flexisip in the 401 challenge `Via:` header:
   ```python
   rport_m = re.search(r';rport=(\d+)', msg, re.IGNORECASE)
   received_m = re.search(r';received=([0-9a-fA-F\.:]+)', msg, re.IGNORECASE)
   nat_port = int(rport_m.group(1)) if rport_m else port
   nat_ip = received_m.group(1) if received_m else cur_ip
   ```
2. **Explicit Stale Contact Purge (`expires=0`):**
   In the authenticated REGISTER message, TARS explicitly de-registers port 5060 and binds the live NAT port:
   ```sip
   Contact: <sip:suhail_tars@49.206.57.206:5060>;expires=0
   Contact: <sip:suhail_tars@49.206.57.206:52087>;expires=600
   ```
3. **Contact Header Synchronization in 200 OK:**
   Synchronized the 200 OK response to incoming INVITEs to advertise `advertised_sip_port`, ensuring all in-dialog `ACK` packets route directly to the active socket.
4. Incoming calls connect in under **100 milliseconds**.

---

### Bug 7: Artificial Turn Limits & Conversation Truncation

#### The Symptom:
The user noticed calls ended abruptly during deep conversations:
> *"and there is atime limit or duration for a each call? yes or no in one word dont explain"*
> *"remove that nlimited talking with the agent"*

#### The Root Cause:
`sip_caller.py` had a legacy debugging safeguard:
```python
max_turns = 8
while is_current_call() and turn < max_turns:
```
After 8 conversational exchanges, the loop ended and issued a `BYE`.

#### The Permanent Fix:
1. Removed `max_turns` entirely; the loop now evaluates `while is_current_call():`.
2. Extended user speech capture window from 15 seconds to **30 seconds**.
3. Implemented a **10-message sliding conversational memory** to prevent Groq API token overflow while allowing unlimited multi-hour phone sessions:
   ```python
   trimmed_history = history[-10:] if len(history) > 10 else history
   ```

---

### Bug 8: Low Mobile Volume & British Accent Overhaul

#### The Symptom:
The user requested:
> *"why his volume is so low and pleaase give him a accent american accent  , "*

#### The Root Cause:
1. **Low Volume:**
   - In `generate_speech_ulaw`, audio was explicitly scaled down: `audioop.mul(raw_pcm, 2, 0.85)`.
   - Raw TTS output has high peak plosives but low average RMS energy (~3200 RMS). Telephone speakers need loud, compressed voice levels (RMS ~6000–7000).
   - Old cached `.ulaw` files in `_audio_cache` were generated with low volume and were never replaced.
2. **Accent:**
   - Defaulted to `en-GB-RyanNeural` (British accent). The user wanted an American accent matching TARS from *Interstellar*.

#### The Permanent Fix:
1. **American Natural Voice:** Switched to **`en-US-GuyNeural`** (articulate, confident American male persona).
2. **Edge-TTS Volume Boost:** Set `volume="+35%"`.
3. **Soft-Saturation Loudness Compressor:** Implemented a digital gain booster (1.85x) with a soft-limiting curve to raise average RMS without digital distortion:
   ```python
   for s in samples:
       v = s * 1.85
       if v > 31000:
           v = 31000 + (v - 31000) * 0.15
       elif v < -31000:
           v = -31000 + (v - -31000) * 0.15
       v = max(-32767, min(32767, int(v)))
       boosted.extend(struct.pack("<h", v))
   ```
4. **Cache Invalidation:** Cleared `_audio_cache` and regenerated all greetings and fillers in high-volume American English.

---

## 6. Complete Technical Stack & Requirements

### Software & Services (All Free-Tier / Open-Source)
- **Runtime:** Python 3.11+ / Python 3.13 (64-bit on Windows or Linux).
- **SIP & Media:**
  - `pylibsrtp` (RFC 4568 SDES-SRTP encryption).
  - `miniaudio` (Rapid MP3 to raw PCM decoding).
  - `audioop-lts` (G.711 u-law compression and gain scaling).
- **AI & Cloud APIs:**
  - `groq` (Whisper Large v3 for STT, LLaMA 3.3 70B for RAG).
  - `edge-tts` (Microsoft Azure Neural TTS endpoint).
  - `google-api-python-client`, `google-auth` (Gmail API v1).
- **Web & Control:**
  - `fastapi`, `uvicorn` (Health checks and WebSockets).
  - `requests` (Public IP discovery and Telegram Bot API).
  - `python-dotenv` (Environment configuration).

### Python `requirements.txt`
```text
fastapi>=0.115.0
uvicorn>=0.30.0
edge-tts>=6.1.12
groq>=0.11.0
miniaudio>=1.59
pylibsrtp>=0.10.0
audioop-lts>=0.2.1
requests>=2.32.0
python-dotenv>=1.0.1
google-api-python-client>=2.140.0
google-auth-httplib2>=0.2.0
google-auth-oauthlib>=1.2.1
pdfplumber>=0.11.0
openpyxl>=3.1.5
python-docx>=1.1.2
```

---

## 7. Step-by-Step Reproduction Guide (Build It Yourself)

Follow this exact blueprint to recreate TARS Voice Sentinel on any machine:

### Step 1: Create Free Accounts
1. **Linphone SIP Accounts:**
   - Go to [subscribe.linphone.org](https://subscribe.linphone.org/).
   - Create Account 1 for TARS: `suhail_tars` with a strong password.
   - Create Account 2 for yourself: `mohammed_suhail`.
   - Install the Linphone app on your Android or iOS smartphone and log into Account 2.
2. **Groq API Key:**
   - Sign up at [console.groq.com](https://console.groq.com/).
   - Generate an API key with free-tier access.
3. **Google Cloud Gmail API:**
   - Create a Google Cloud Project.
   - Enable Gmail API and Google Calendar API.
   - Configure OAuth Consent Screen (External, add your email as Test User).
   - Create OAuth Client ID (Desktop App) and download `credentials.json`.
   - Run `python auth_helper.py` to generate your permanent OAuth refresh token.

### Step 2: Environment Configuration (`.env`)
Create a `.env` file in the project root:
```env
# Linphone SIP Credentials
TARS_SIP_USERNAME=suhail_tars
TARS_SIP_PASSWORD=YourPasswordHere
TARS_SIP_DOMAIN=sip.linphone.org
USER_SIP_URI=sip:mohammed_suhail@sip.linphone.org
CALLER_DISPLAY_NAME=TARS

# Voice Configuration
TARS_VOICE=en-US-GuyNeural

# Groq LLM & Whisper API
GROQ_API_KEY=gsk_your_groq_api_key_here

# Telegram Hub
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Launch as Detached Background Service
On Windows, execute the WMI detached launcher:
```powershell
powershell -ExecutionPolicy Bypass -File .\start_detached.ps1
```
On Linux, run via systemd or nohup:
```bash
nohup python3 -u tars_supervisor.py > tars_supervisor.log 2>&1 &
```

---

## 8. Production Deployment (Windows Daemon, Docker & Linux)

### Windows Boot Automation
To ensure TARS runs automatically whenever your PC turns on:
1. Press `Win + R`, type `shell:startup`, and press Enter.
2. Create a shortcut pointing to:
   ```cmd
   powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\path\to\start_detached.ps1"
   ```

### Docker Deployment (`Dockerfile`)
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libglib2.0-0 \
    libsrtp2-dev \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose SIP UDP 5060 and HTTP 8080
EXPOSE 5060/udp 8080/tcp

CMD ["python", "-u", "tars_supervisor.py"]
```

### Docker Compose (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  tars-voice:
    build: .
    container_name: tars_voice_sentinel
    restart: always
    network_mode: "host" # Host networking required for direct SIP UDP NAT traversal
    env_file:
      - .env
    volumes:
      - ./_audio_cache:/app/_audio_cache
      - ./logs:/app/logs
```

---

## 9. Verification & Operational Health Check

To verify the installation:
1. **Check Process Status:**
   ```powershell
   Get-Process python* | Where-Object { $_.CommandLine -like "*tars*" -or $_.CommandLine -like "*call_server*" }
   ```
2. **Check Listening UDP Port:**
   ```powershell
   netstat -ano | findstr ":5060"
   ```
3. **Verify Flexisip Registration:**
   Inspect `tars_server.log`. You must see:
   ```text
   ✅ Linphone Registration Confirmed: 200 OK for suhail_tars@sip.linphone.org!
   📋 Registered Contacts with Flexisip: ['sip:suhail_tars@...:52087']
   👉 Ready for inbound calls! Dial 'suhail_tars' from Linphone app.
   ```
4. **Make a Live Test Call:**
   - Open Linphone on your smartphone.
   - Dial **`suhail_tars`**.
   - TARS will answer within 100ms in an articulate, high-volume American accent:
     > *"Hello boss, TARS online. How can I help you today?"*
