import os
import sys
import json
import base64
import asyncio
import tempfile
import socket
import logging
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
from groq import Groq

# Ensure local modules can be loaded cleanly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import tars_agent
import check_emails

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TARS_Voice_Sentinel")

# Load environment variables
env_path = os.path.join(CURRENT_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'\"")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

VOICE_NAME = os.environ.get("TARS_VOICE", "en-US-GuyNeural")  # Crisp, deep natural male voice

app = FastAPI(title="TARS Voice Sentinel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(CURRENT_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ConnectionManager:
    """Manages active mobile and desktop WebSocket connections."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"📱 Phone connected! Active mobile devices ready to ring: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Phone disconnected. Remaining connected devices: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                dead_connections.append(connection)
        for dc in dead_connections:
            self.disconnect(dc)


manager = ConnectionManager()
active_call_context: Dict[str, Any] = {}
processed_email_ids = set()


async def synthesize_speech_base64(text: str) -> str:
    """Generate MP3 audio via Edge-TTS and return as Base64 string."""
    try:
        communicate = edge_tts.Communicate(text, VOICE_NAME)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"Speech synthesis error: {e}")
        return ""


def transcribe_audio_chunk(audio_base64: str) -> str:
    """Transcribes user voice audio chunk using Groq Whisper API (<200ms)."""
    if not groq_client:
        return ""
    try:
        audio_data = base64.b64decode(audio_base64)
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                language="en",
                response_format="text"
            )
        
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        text = transcription.strip() if isinstance(transcription, str) else getattr(transcription, "text", "").strip()
        logger.info(f"🎤 Transcribed from Phone: '{text}'")
        return text
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        return ""


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serves the mobile Incoming Call & Sentinel UI."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>TARS Voice Sentinel: static/index.html not found</h1>"


@app.post("/api/trigger-call")
async def trigger_call(request: Request):
    """Trigger an incoming call on connected phones (manual test or webhook)."""
    data = await request.json()
    sender = data.get("sender", "Dean of Academics (ISL)")
    subject = data.get("subject", "Urgent: Project Showcase Rescheduled")
    voice_script = data.get("voice_script", "Commander, urgent notice from Dean's office regarding schedule. Should I draft an approval?")
    email_id = data.get("email_id", "manual_test")

    global active_call_context
    active_call_context = {
        "id": email_id,
        "sender": sender,
        "subject": subject,
        "voice_script": voice_script
    }

    call_payload = {
        "type": "INCOMING_CALL",
        "id": email_id,
        "sender": sender,
        "subject": subject,
        "voice_script": voice_script
    }

    logger.info(f"🚨 TRIGGERING CALL to {len(manager.active_connections)} connected phone(s)...")
    await manager.broadcast(call_payload)
    return {"status": "call_broadcasted", "connected_phones": len(manager.active_connections)}


@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket):
    """Full-duplex WebSocket channel between mobile phone and TARS Voice Agent."""
    await manager.connect(websocket)
    try:
        while True:
            raw_data = await websocket.receive_text()
            msg = json.loads(raw_data)
            msg_type = msg.get("type")

            if msg_type == "CALL_ACCEPTED":
                logger.info("🟢 User answered call on mobile! TARS speaking brief...")
                email_data = msg.get("email_data") or active_call_context
                script = email_data.get("voice_script", "Commander, an urgent email has arrived that needs your attention. How would you like me to respond?")
                
                audio_b64 = await synthesize_speech_base64(script)
                await websocket.send_json({
                    "type": "AUDIO_RESPONSE",
                    "text": script,
                    "audio_base64": audio_b64
                })

            elif msg_type == "USER_AUDIO_CHUNK":
                audio_b64 = msg.get("audio_base64", "")
                if audio_b64:
                    user_text = transcribe_audio_chunk(audio_b64)
                    if user_text:
                        # Check for hangup intents
                        lower_text = user_text.lower()
                        if any(phrase in lower_text for phrase in ["bye", "goodbye", "hang up", "that's it", "that is all", "no thanks", "nothing else"]):
                            farewell = "Understood. Hanging up now, Commander."
                            farewell_b64 = await synthesize_speech_base64(farewell)
                            await websocket.send_json({
                                "type": "AUDIO_RESPONSE",
                                "text": farewell,
                                "audio_base64": farewell_b64
                            })
                            await asyncio.sleep(2)
                            await websocket.send_json({"type": "END_CALL"})
                            continue

                        # Execute action via TARS brain
                        await websocket.send_json({
                            "type": "STATUS_UPDATE",
                            "status": "TARS Drafting Reply in Gmail..."
                        })

                        prompt = (
                            f"[Live Voice Call from Mohammed Suhail]. "
                            f"Context - Urgent email from: '{active_call_context.get('sender', 'Unknown')}', "
                            f"Subject: '{active_call_context.get('subject', 'Unknown')}'. "
                            f"Suhail verbally commanded: \"{user_text}\". "
                            f"Execute the appropriate tool (e.g. create_draft_email, search_emails, reply_to_emails). "
                            f"Respond in 1 to 2 sharp spoken sentences max, like TARS in Interstellar."
                        )

                        tars_reply = tars_agent.chat_with_tars(prompt)
                        tars_spoken = tars_reply.replace("*", "").replace("#", "").strip()

                        audio_b64 = await synthesize_speech_base64(tars_spoken)
                        await websocket.send_json({
                            "type": "AUDIO_RESPONSE",
                            "text": tars_spoken,
                            "audio_base64": audio_b64
                        })

            elif msg_type == "CALL_DECLINED":
                logger.info("🔴 Call declined by user on phone.")

            elif msg_type == "HANGUP":
                logger.info("Call ended by user on phone.")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def background_gmail_watcher():
    """Continuously monitors Gmail inbox every 15s; triggers incoming call when URGENT email arrives."""
    logger.info("✅ Background Gmail Watcher active (Polling every 15 seconds)...")
    await asyncio.sleep(3)  # Brief warm up
    
    # Pre-populate already seen emails to avoid ringing for old emails
    try:
        init_service = check_emails.get_gmail_service()
        if init_service:
            existing_res = init_service.users().messages().list(userId='me', q='label:INBOX', maxResults=15).execute()
            for m in existing_res.get('messages', []):
                processed_email_ids.add(m['id'])
            logger.info(f"Initialized inbox baseline. Existing messages indexed: {len(processed_email_ids)}")
    except Exception as e:
        logger.warning(f"Could not initialize inbox baseline: {e}")

    while True:
        try:
            gmail = check_emails.get_gmail_service()
            if gmail:
                results = gmail.users().messages().list(
                    userId='me',
                    q='is:unread label:INBOX -category:promotions -category:social',
                    maxResults=5
                ).execute()
                messages = results.get('messages', [])
                
                for msg_meta in messages:
                    m_id = msg_meta['id']
                    if m_id not in processed_email_ids:
                        processed_email_ids.add(m_id)
                        logger.info(f"📩 NEW UNREAD EMAIL DETECTED (ID: {m_id})! Analyzing urgency...")

                        # Fetch message details
                        msg_detail = gmail.users().messages().get(userId='me', id=m_id, format='full').execute()
                        headers = check_emails.clean_email_headers(msg_detail)
                        payload = msg_detail.get('payload', {})
                        body = check_emails.parse_email_body(payload)

                        sender = headers.get('From', 'Unknown Sender')
                        raw_subject = headers.get('Subject', '').strip()
                        subject = raw_subject if raw_subject else f"Direct message from {sender.split('<')[0].strip()}"
                        body_preview = body[:2000]

                        # Classify with Groq
                        prompt = f"""You are TARS, executive email assistant.
Analyze this newly arrived email:
From: {sender}
Subject: {subject}
Content: {body_preview}

Should this trigger an urgent incoming phone call to Suhail?
Mark 'is_urgent: true' if it involves an interview, schedule change, hackathon selection, exam, emergency, resume request, or direct personal question requiring rapid reply.
Mark 'is_urgent: false' for newsletters, advertisements, automated verification codes, or general marketing.

Respond ONLY with valid JSON:
{{
  "is_urgent": true or false,
  "reason": "short explanation",
  "voice_script": "One natural spoken sentence (under 25 words) like TARS speaking on phone to Suhail explaining who emailed and what they need."
}}"""
                        if groq_client:
                            analysis = None
                            for m in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
                                try:
                                    resp = groq_client.chat.completions.create(
                                        model=m,
                                        messages=[{"role": "user", "content": prompt}],
                                        response_format={"type": "json_object"}
                                    )
                                    analysis = json.loads(resp.choices[0].message.content)
                                    break
                                except Exception as model_err:
                                    logger.warning(f"Model {m} failed: {model_err}, trying next...")
                            if not analysis:
                                analysis = {"is_urgent": False, "reason": "Classification failed"}
                            is_urgent = analysis.get("is_urgent", False)
                            # Safeguard: if someone asks for resume, interview, meeting, shortlist, or direct inquiry
                            body_lower = body.lower()
                            if any(k in body_lower for k in ["resume", "interview", "meeting", "shortlist", "hackathon", "urgent", "schedule", "data science"]):
                                is_urgent = True
                                logger.info("⚡ Safeguard triggered: Personal opportunity/resume request -> is_urgent=True")
                            voice_script = analysis.get("voice_script", f"Commander, urgent email from {sender} regarding {subject}.")

                            logger.info(f"Email Analysis for '{subject}': is_urgent={is_urgent} ({analysis.get('reason')})")

                            if is_urgent:
                                logger.info(f"🚨 URGENT EMAIL CONFIRMED! INITIATING PHONE CALL NOW...")
                                global active_call_context
                                active_call_context = {
                                    "id": m_id,
                                    "sender": sender,
                                    "subject": subject,
                                    "voice_script": voice_script
                                }

                                call_payload = {
                                    "type": "INCOMING_CALL",
                                    "id": m_id,
                                    "sender": sender,
                                    "subject": subject,
                                    "voice_script": voice_script
                                }
                                await manager.broadcast(call_payload)

                                # Trigger native Android lockscreen SIP push call
                                try:
                                    import sip_caller
                                    sip_caller.trigger_urgent_call_async(
                                        subject=subject,
                                        sender=sender,
                                        reason=analysis.get("reason", ""),
                                        email_id=m_id,
                                        body=body
                                    )
                                except Exception as sip_err:
                                    logger.warning(f"SIP caller error: {sip_err}")

        except Exception as e:
            logger.warning(f"Gmail watch cycle error: {e}")

        await asyncio.sleep(15)  # Poll every 15 seconds for rapid detection


@app.on_event("startup")
async def startup_event():
    """Launches the background Gmail watcher when the server starts."""
    asyncio.create_task(background_gmail_watcher())


def get_local_ip() -> str:
    """Finds the local network Wi-Fi IP address so the user can open it on their phone."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8080
    print("\n" + "=" * 65)
    print("      🚀 TARS VOICE SENTINEL SERVER READY FOR ACTION")
    print("=" * 65)
    print(f" • Local PC Browser:     http://localhost:{port}")
    print(f" • Mobile Phone (Wi-Fi): http://{local_ip}:{port}")
    print("=" * 65)
    print(" 1. Open the Mobile Phone link on your phone (Chrome/Safari)")
    print(" 2. Tap 'Enable Mobile Mic & Audio'")
    print(" 3. Send your test email -> Watch your phone ring!\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
