import builtins
_orig_print = builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    return _orig_print(*args, **kwargs)

"""
TARS Voice Sentinel - Ultra-Fast Conversational SIP Agent (100% Free Forever)
Direct VoIP Push Calling to Android via Linphone SIP (RFC 2617 Digest Auth).

Features:
- Caller ID: "TARS"
- Persona: Executive AI Assistant addressing Mohammed Suhail as "Sir".
- Ultra-Fast (<15s) Multi-Turn Conversational Interaction.
- Spoken Confirmation Loop: Repeats back what you said and verifies before sending.
- Zero Dead Silence: Instant pre-cached audio acknowledgements while processing.
- Clean Studio Voice: en-US-AndrewMultilingualNeural, filtered single-port RTP.
- High-Speed Single-Pass Email Drafting: Pre-drafts email during confirmation for instant 300ms dispatch.
- RFC 2833 DTMF Support: Press 1 on phone keypad to confirm instantly.
"""

import sys
if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import io
import socket
import uuid
import hashlib
import re
import time
import struct
import threading
import asyncio
import math
import wave
import json
import requests
import edge_tts
import miniaudio
import audioop
from groq import Groq

# Load environment
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

LINPHONE_USERNAME = os.environ.get("LINPHONE_USERNAME", "mohammed_suhail")
LINPHONE_PASSWORD = os.environ.get("LINPHONE_PASSWORD", "Suhail2016")
LINPHONE_DOMAIN = os.environ.get("LINPHONE_DOMAIN", "sip.linphone.org")
LINPHONE_TARGET = os.environ.get("LINPHONE_TARGET_URI", f"sip:{LINPHONE_USERNAME}@{LINPHONE_DOMAIN}")
CALLER_DISPLAY = os.environ.get("CALLER_DISPLAY_NAME", "TARS")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

VOICE_MODEL = "en-US-AndrewMultilingualNeural"  # Crisp, warm, human conversational voice
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_audio_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def get_local_ip() -> str:
    """Finds the local network Wi-Fi IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.2"


def parse_auth_challenge(resp, auth_header_name="WWW-Authenticate"):
    m = re.search(auth_header_name + r':\s*Digest\s+(.*)', resp, re.IGNORECASE)
    if not m:
        return None
    header_str = m.group(1)
    
    def get_param(name):
        match = re.search(name + r'="([^"]+)"', header_str)
        if match:
            return match.group(1)
        match_unquoted = re.search(name + r'=([^, ]+)', header_str)
        if match_unquoted:
            return match_unquoted.group(1)
        return ""
        
    return {
        "realm": get_param("realm") or LINPHONE_DOMAIN,
        "nonce": get_param("nonce"),
        "opaque": get_param("opaque"),
        "qop": get_param("qop"),
        "algorithm": get_param("algorithm") or "MD5"
    }


def compute_digest(username, password, realm, nonce, method, uri, qop, opaque, nc="00000001", cnonce=None):
    if not cnonce:
        cnonce = uuid.uuid4().hex[:8]
    HA1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    HA2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    
    if qop and "auth" in qop:
        resp_hash = hashlib.md5(f"{HA1}:{nonce}:{nc}:{cnonce}:auth:{HA2}".encode()).hexdigest()
        auth_val = (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{resp_hash}", algorithm=MD5, '
            f'cnonce="{cnonce}", qop=auth, nc={nc}'
        )
    else:
        resp_hash = hashlib.md5(f"{HA1}:{nonce}:{HA2}".encode()).hexdigest()
        auth_val = (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{resp_hash}", algorithm=MD5'
        )
    if opaque:
        auth_val += f', opaque="{opaque}"'
    return auth_val


def make_rtp_packet(seq, timestamp, ssrc, payload, marker=False, pt=0):
    byte0 = 0x80
    byte1 = (0x80 if marker else 0x00) | (pt & 0x7F)
    header = struct.pack("!BBHII", byte0, byte1, seq & 0xFFFF, timestamp & 0xFFFFFFFF, ssrc)
    return header + payload


async def generate_speech_ulaw(text: str, rate: str = "+15%") -> bytes:
    """Synthesizes high-fidelity speech using Edge-TTS with brisk rate (+15%) and converts to 8kHz u-law."""
    try:
        comm = edge_tts.Communicate(text, VOICE_MODEL, rate=rate)
        chunks = [c["data"] async for c in comm.stream() if c["type"] == "audio"]
        mp3_data = b"".join(chunks)
        decoded = miniaudio.decode(mp3_data, nchannels=1, sample_rate=8000)
        raw_pcm = decoded.samples.tobytes()
        return audioop.lin2ulaw(raw_pcm, 2)
    except Exception as e:
        print(f"⚠️ Edge-TTS synthesis failed: {e}")
        return b"\xff" * 16000


def get_or_create_cached_audio(name: str, text: str) -> bytes:
    """Loads static filler audio from cache in 0.001s, or creates it if missing."""
    path = os.path.join(CACHE_DIR, f"{name}.ulaw")
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            pass
    ulaw = asyncio.run(generate_speech_ulaw(text, rate="+15%"))
    try:
        with open(path, "wb") as f:
            f.write(ulaw)
    except Exception:
        pass
    return ulaw


def generate_beep_ulaw(freq=660, duration_sec=0.15) -> bytes:
    """Generates a pleasant, smooth intercom chime with 12ms cosine fade envelopes to prevent audio pops."""
    pcm = bytearray()
    total_samples = int(8000 * duration_sec)
    fade_len = int(8000 * 0.012)  # 12ms smooth fade in and out
    for i in range(total_samples):
        if i < fade_len:
            env = 0.5 * (1 - math.cos(math.pi * i / fade_len))
        elif i > total_samples - fade_len:
            env = 0.5 * (1 - math.cos(math.pi * (total_samples - i) / fade_len))
        else:
            env = 1.0
        val = int(8000 * env * math.sin(2 * math.pi * freq * i / 8000))
        pcm.extend(struct.pack("<h", val))
    return audioop.lin2ulaw(bytes(pcm), 2)


class RTPPlayer:
    """Maintains continuous monotonic RFC 3550 RTP sequence numbers and timestamps to prevent DAC pops and jitter resets."""
    def __init__(self, rtp_sock, destinations, ssrc=0x34A8129B):
        self.rtp_sock = rtp_sock
        self.destinations = destinations
        self.ssrc = ssrc
        self.seq = 1
        self.timestamp = 0

    def play(self, ulaw_data):
        chunk_size = 160
        start_time = time.time()
        chunks_count = (len(ulaw_data) + chunk_size - 1) // chunk_size
        
        for idx in range(chunks_count):
            start = idx * chunk_size
            chunk = ulaw_data[start:start + chunk_size]
            if len(chunk) < chunk_size:
                chunk += b"\xff" * (chunk_size - len(chunk))
                
            pkt = make_rtp_packet(self.seq, self.timestamp, self.ssrc, chunk, marker=(idx == 0))
            for target_ip, target_port in self.destinations:
                try:
                    self.rtp_sock.sendto(pkt, (target_ip, target_port))
                except Exception:
                    pass

            self.seq = (self.seq + 1) & 0xFFFF
            self.timestamp = (self.timestamp + 160) & 0xFFFFFFFF

            target_time = start_time + (0.02 * (idx + 1))
            sleep_dur = target_time - time.time()
            if sleep_dur > 0:
                time.sleep(sleep_dur)


def stream_audio(rtp_sock, destinations, ulaw_data, repeat=1, ssrc=0x34A8129B):
    """Convenience wrapper for legacy calls."""
    player = RTPPlayer(rtp_sock, destinations, ssrc=ssrc)
    for _ in range(repeat):
        player.play(ulaw_data)


def select_best_rtp_destination(sdp_text: str) -> list[tuple[str, int]]:
    """
    Parses SDP to extract ONLY component 1 (RTP audio, ignoring component 2 RTCP).
    Selects the single best destination to avoid packet duplication, jitter drops, and comb filtering.
    """
    cand_matches = re.findall(r'a=candidate:\S+\s+1\s+(?:UDP|udp)\s+\d+\s+([^\s]+)\s+(\d+)', sdp_text)
    destinations = [(ip.strip(), int(port)) for ip, port in cand_matches]

    c_ip = re.search(r'c=IN\s+(?:IP4|IP6)\s+([^\r\n;]+)', sdp_text)
    m_port = re.search(r'm=audio\s+(\d+)', sdp_text)
    if c_ip and m_port:
        pair = (c_ip.group(1).strip(), int(m_port.group(1)))
        if pair not in destinations:
            destinations.insert(0, pair)

    lan_dests = [d for d in destinations if d[0].startswith(("192.168.", "10.", "172."))]
    if lan_dests:
        print(f"🎯 Selected single Wi-Fi RTP endpoint: {lan_dests[0]} (Zero packet duplication, studio clean)")
        return [lan_dests[0]]

    if destinations:
        print(f"🎯 Selected single WAN RTP endpoint: {destinations[0]}")
        return [destinations[0]]
        
    return []


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 8000) -> bytes:
    """Converts raw 16-bit mono linear PCM to WAV in memory."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def transcribe_pcm_audio(pcm_data: bytes) -> str:
    """Transcribes user voice audio using Groq Whisper API (<250ms) with domain vocabulary prompt."""
    if not groq_client or len(pcm_data) < 2500:
        return ""
    try:
        wav_bytes = pcm_to_wav_bytes(pcm_data)
        vocab_prompt = "Mohammed Suhail, available, meet on Sunday, interview, hackathon, resume, confirm, schedule, email reply."
        transcription = groq_client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=("speech.wav", wav_bytes),
            language="en",
            prompt=vocab_prompt,
            response_format="text"
        )
        text = transcription.strip() if isinstance(transcription, str) else getattr(transcription, "text", "").strip()
        print(f"🎤 Groq Whisper Transcribed: '{text}'")
        return text
    except Exception as e:
        print(f"⚠️ Groq Whisper transcription error: {e}")
        return ""


def parse_user_intent_and_draft(transcript: str, email_subject: str, email_sender: str, email_body: str) -> dict:
    """
    Parses user instructions into structured actions, creates spoken confirmation, AND pre-drafts the full email body in ONE single fast LLM pass (<400ms).
    """
    clean_t = transcript.lower().strip()
    
    if any(neg in clean_t for neg in ["cancel", "no don't send", "dont send", "stop", "ignore", "decline"]):
        return {
            "intent": "CANCEL",
            "instruction": "",
            "attach_resume": False,
            "spoken_confirmation": "Understood sir. Email canceled. Standing by.",
            "drafted_body": ""
        }

    clean_first_name = email_sender.split()[0].replace('"', '') if email_sender else "there"

    if groq_client:
        prompt = f"""You are TARS, executive voice AI assistant on a live phone call with Mohammed Suhail. Address the user as 'sir'.
Incoming email from: {email_sender}
Subject: {email_subject}
Content: {email_body[:600]}

The user dictated this instruction on the call:
"{transcript}"

Do TWO tasks in valid JSON:
1. 'spoken_confirmation': A crisp, ultra-short sentence TARS speaks back to Suhail to verify before sending (e.g. "Understood sir. I'll let {clean_first_name} know you can meet Sunday, and attach your resume. Send it now, sir?").
2. 'drafted_body': The professional, concise reply email body (plain text, no placeholder brackets) signed 'Best regards,\nMohammed Suhail'.

Respond ONLY with valid JSON:
{{
  "intent": "CUSTOM_REPLY" | "CONFIRM_SEND" | "CANCEL",
  "instruction": "Summary of user command",
  "attach_resume": true or false,
  "spoken_confirmation": "Short question asking to confirm, addressing Suhail as sir",
  "drafted_body": "Full professional email reply text"
}}"""
        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
            try:
                resp = groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                data = json.loads(resp.choices[0].message.content)
                if data and "intent" in data and "drafted_body" in data:
                    return data
            except Exception:
                continue

    # Fallback default
    fallback_body = f"Hi {clean_first_name},\n\nThanks for reaching out. Please find my resume attached for your review. I would be happy to connect.\n\nBest regards,\nMohammed Suhail"
    return {
        "intent": "CONFIRM_SEND",
        "instruction": f"Confirm meeting and reply: '{transcript}'. Attach resume.",
        "attach_resume": True,
        "spoken_confirmation": f"Understood sir. I'll reply with your instructions and attach your resume. Send it now, sir?",
        "drafted_body": fallback_body
    }


def is_user_confirming_send(transcript: str, dtmf: str = None) -> bool:
    """Checks if user confirmed dispatching the email (or pressed 1)."""
    if dtmf == "1":
        return True
    if dtmf == "2":
        return False
    clean_t = transcript.lower().strip()
    positive = ["yes", "yeah", "yep", "send", "send it", "go ahead", "okay", "ok", "confirm", "do it", "sure", "dispatch"]
    negative = ["no", "wait", "cancel", "don't", "dont", "stop", "change", "hold"]
    if any(p in clean_t for p in positive) and not any(n in clean_t for n in negative):
        return True
    return False


def record_user_speech(rtp_sock, max_seconds=6.0, silence_timeout=0.8) -> tuple[bytes, str]:
    """
    Records incoming RTP audio packets from the user's phone microphone.
    Rapid 0.8s silence timeout for lightning-fast turn-taking.
    Returns (linear_pcm_bytes, dtmf_digit).
    """
    # Drain any buffered packets from socket
    rtp_sock.setblocking(False)
    while True:
        try:
            rtp_sock.recvfrom(4096)
        except Exception:
            break
    
    rtp_sock.settimeout(0.04)
    
    frames = []
    speech_detected = False
    last_speech_time = 0.0
    dtmf_digit = None
    start_time = time.time()
    
    while time.time() - start_time < max_seconds:
        try:
            data, _ = rtp_sock.recvfrom(2048)
            if len(data) < 12:
                continue
            
            byte0, byte1, seq, ts, ssrc = struct.unpack("!BBHII", data[:12])
            pt = byte1 & 0x7F
            
            cc = byte0 & 0x0F
            header_len = 12 + (cc * 4)
            if (byte0 >> 4) & 0x01 and len(data) >= header_len + 4:
                _, ext_len = struct.unpack("!HH", data[header_len:header_len+4])
                header_len += 4 + (ext_len * 4)
            
            payload = data[header_len:]
            if not payload:
                continue
            
            # 1. Check for DTMF (telephone-event)
            if pt == 101:
                event_code = payload[0]
                if event_code <= 9:
                    dtmf_digit = str(event_code)
                elif event_code == 10:
                    dtmf_digit = "*"
                elif event_code == 11:
                    dtmf_digit = "#"
                print(f"🔢 Keypad DTMF: '{dtmf_digit}'")
                break

            # 2. Decode audio payload
            linear = None
            if pt == 0:  # PCMU
                linear = audioop.ulaw2lin(payload, 2)
            elif pt == 8:  # PCMA
                linear = audioop.alaw2lin(payload, 2)
            
            if linear:
                frames.append(linear)
                rms = audioop.rms(linear, 2)
                
                if rms > 420:
                    if not speech_detected:
                        speech_detected = True
                    last_speech_time = time.time()
                
                # Rapid silence detection (0.8s) for snappy Jarvis pacing
                if speech_detected and (time.time() - last_speech_time > silence_timeout) and len(frames) > 15:
                    break

        except socket.timeout:
            continue
        except Exception:
            continue
            
    pcm_bytes = b"".join(frames)
    return pcm_bytes, dtmf_digit


def send_telegram_summary(transcript: str, action_taken: str, sender: str, subject: str):
    """Sends immediate Telegram execution confirmation to Suhail's bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        text = (
            f"🎙️ *TARS Voice Call Completed*\n"
            f"👤 *Sender:* `{sender}`\n"
            f"📌 *Subject:* `{subject}`\n"
            f"🗣️ *You Said:* \"_{transcript}_\"\n"
            f"⚡ *Action Taken:* {action_taken}\n"
            f"✅ *Status:* Executed via Gmail API"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"⚠️ Telegram notification error: {e}")


def trigger_urgent_call(
    subject: str = "Urgent Email",
    sender: str = "",
    reason: str = "",
    email_id: str = None,
    body: str = "",
    ring_timeout: int = 60
) -> bool:
    """
    Ultra-Fast Autonomous Jarvis Voice Sentinel:
    - Caller ID displays "TARS" on phone screen.
    - Speaks concise briefing (<4s) addressing user as "Sir".
    - Instant pre-cached audio fillers eliminate all dead silence.
    - Two-way confirmation loop verifies draft before sending.
    - Dispatches pre-drafted email in 300ms upon confirmation.
    """
    server = LINPHONE_DOMAIN
    server_port = 5060
    username = LINPHONE_USERNAME
    password = LINPHONE_PASSWORD
    target_sip_uri = LINPHONE_TARGET
    public_ip = "117.99.202.109"
    local_ip = get_local_ip()

    clean_sender = sender.split("<")[0].strip().replace('"', '') if sender else "an important contact"
    clean_subject = subject.replace('"', '').strip()
    if not clean_subject:
        clean_subject = "Meeting Request"
    clean_reason = reason.replace('"', '').strip() if reason else ""

    # Crisp, punchy Jarvis Briefing Script (under 14 words = ~3.5s speaking time)
    briefing_text = (
        f"Hello Suhail sir, TARS here. Urgent email from {clean_sender}: "
        f"{clean_reason or clean_subject}. What should I reply?"
    )

    print(f"\n=======================================================")
    print(f"🚨 TARS CALLER - ULTRA FAST JARVIS ENGINE")
    print(f"Caller ID: {CALLER_DISPLAY}")
    print(f"Target: {target_sip_uri}")
    print(f"Sender: {clean_sender}")
    print(f"Subject: {clean_subject}")
    print(f"=======================================================")

    # Load pre-cached static filler assets instantly (0.001s)
    ack_drafting_ulaw = get_or_create_cached_audio("ack_drafting", "Understood sir, drafting now.")
    ack_sending_ulaw = get_or_create_cached_audio("ack_sending", "Sending now, sir.")
    farewell_ulaw = get_or_create_cached_audio("farewell", "Affirmative sir. Reply dispatched with resume attached. Have a great day!")
    beep_ulaw = generate_beep_ulaw(freq=800, duration_sec=0.18)

    # Start synthesizing custom briefing audio in parallel thread
    greeting_holder = [None]
    def _synth_worker():
        greeting_holder[0] = asyncio.run(generate_speech_ulaw(briefing_text, rate="+15%"))
    synth_t = threading.Thread(target=_synth_worker, daemon=True)
    synth_t.start()

    sip_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sip_sock.settimeout(2.0)
    sip_sock.bind(("0.0.0.0", 0))
    local_sip_port = sip_sock.getsockname()[1]

    rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtp_sock.bind(("0.0.0.0", 0))
    local_rtp_port = rtp_sock.getsockname()[1]

    call_id = uuid.uuid4().hex + "@" + public_ip
    from_tag = uuid.uuid4().hex[:8]
    branch1 = "z9hG4bK" + uuid.uuid4().hex[:20]

    invite1 = (
        f"INVITE {target_sip_uri} SIP/2.0\r\n"
        f"Via: SIP/2.0/UDP {public_ip}:{local_sip_port};branch={branch1};rport\r\n"
        f'From: "{CALLER_DISPLAY}" <sip:{username}@{server}>;tag={from_tag}\r\n'
        f"To: <{target_sip_uri}>\r\n"
        f"Call-ID: {call_id}\r\n"
        f"CSeq: 1 INVITE\r\n"
        f"Contact: <sip:{username}@{public_ip}:{local_sip_port};transport=UDP>\r\n"
        "Max-Forwards: 70\r\n"
        f"User-Agent: {CALLER_DISPLAY}\r\n"
        "Content-Length: 0\r\n\r\n"
    )

    print(f"📞 Dialing {target_sip_uri} as '{CALLER_DISPLAY}'...")
    sip_sock.sendto(invite1.encode(), (server, server_port))

    resp1 = None
    start = time.time()
    while time.time() - start < 6:
        try:
            data, _ = sip_sock.recvfrom(4096)
            text = data.decode("utf-8", errors="ignore")
            if "407 Proxy Authentication Required" in text or "401 Unauthorized" in text:
                resp1 = text
                break
        except socket.timeout:
            continue

    if not resp1:
        print("❌ Server did not respond to initial INVITE.")
        sip_sock.close()
        rtp_sock.close()
        return False

    auth_header_name = "Proxy-Authenticate" if "407" in resp1 else "WWW-Authenticate"
    auth_req_name = "Proxy-Authorization" if "407" in resp1 else "Authorization"

    to_tag_match = re.search(r'To:.*?tag=([^\r\n;]+)', resp1, re.IGNORECASE)
    to_tag = to_tag_match.group(1) if to_tag_match else ""
    ack1 = (
        f"ACK {target_sip_uri} SIP/2.0\r\n"
        f"Via: SIP/2.0/UDP {public_ip}:{local_sip_port};branch={branch1};rport\r\n"
        f'From: "{CALLER_DISPLAY}" <sip:{username}@{server}>;tag={from_tag}\r\n'
        f"To: <{target_sip_uri}>" + (f";tag={to_tag}" if to_tag else "") + "\r\n"
        f"Call-ID: {call_id}\r\n"
        f"CSeq: 1 ACK\r\n"
        "Max-Forwards: 70\r\n"
        "Content-Length: 0\r\n\r\n"
    )
    sip_sock.sendto(ack1.encode(), (server, server_port))

    challenge = parse_auth_challenge(resp1, auth_header_name)
    auth_val = compute_digest(
        username=username,
        password=password,
        realm=challenge["realm"],
        nonce=challenge["nonce"],
        method="INVITE",
        uri=target_sip_uri,
        qop=challenge["qop"],
        opaque=challenge["opaque"]
    )

    branch2 = "z9hG4bK" + uuid.uuid4().hex[:20]
    invite2 = (
        f"INVITE {target_sip_uri} SIP/2.0\r\n"
        f"Via: SIP/2.0/UDP {public_ip}:{local_sip_port};branch={branch2};rport\r\n"
        f'From: "{CALLER_DISPLAY}" <sip:{username}@{server}>;tag={from_tag}\r\n'
        f"To: <{target_sip_uri}>\r\n"
        f"Call-ID: {call_id}\r\n"
        f"CSeq: 2 INVITE\r\n"
        f"Contact: <sip:{username}@{public_ip}:{local_sip_port};transport=UDP>\r\n"
        f"{auth_req_name}: {auth_val}\r\n"
        "Max-Forwards: 70\r\n"
        f"User-Agent: {CALLER_DISPLAY}\r\n"
        "Content-Length: 0\r\n\r\n"
    )

    print("🔐 Authenticating with Flexisip server...")
    sip_sock.sendto(invite2.encode(), (server, server_port))

    ringing_detected = False
    call_answered = False
    callee_sdp = ""
    callee_tag = ""
    routes = []

    ring_start = time.time()
    while time.time() - ring_start < ring_timeout:
        try:
            data, _ = sip_sock.recvfrom(4096)
            msg = data.decode("utf-8", errors="ignore")

            first_line = msg.splitlines()[0] if msg.splitlines() else "EMPTY"

            if "110 Push sent" in msg:
                print("📲 FCM push notification sent to Android phone!")
            elif "180 Ringing" in msg:
                if not ringing_detected:
                    print(f"\n🔔🔔🔔 PHONE IS RINGING! [Caller: {CALLER_DISPLAY}] 🔔🔔🔔")
                    print("👉 PICK UP THE CALL ON YOUR PHONE TO HEAR TARS SPEAK!")
                    ringing_detected = True
                    ring_start = time.time()
            elif re.search(r'SIP/2\.0 200', msg):
                print(f"\n🎉🎉🎉 CALL ANSWERED BY USER! 🎉🎉🎉")
                call_answered = True
                t_match = re.search(r'To:.*?tag=([^\r\n;]+)', msg, re.IGNORECASE)
                if t_match:
                    callee_tag = t_match.group(1)
                
                c_match = re.search(r'Contact:\s*<([^>]+)>', msg, re.IGNORECASE)
                contact_uri = c_match.group(1).strip() if c_match else target_sip_uri
                
                route_matches = re.findall(r'Record-Route:\s*([^\r\n]+)', msg, re.IGNORECASE)
                routes = list(reversed(route_matches))
                if "\r\n\r\n" in msg:
                    callee_sdp = msg.split("\r\n\r\n", 1)[1]
                break
            elif "603 Decline" in msg or "486 Busy" in msg:
                print("\n📴 Call was declined on phone.")
                break
        except socket.timeout:
            continue

    if call_answered:
        destinations = select_best_rtp_destination(callee_sdp)
        print(f"Target RTP Audio Destination: {destinations}")

        is_on_lan = any(ip.startswith(("192.168.", "10.", "172.")) for ip, _ in destinations)
        advertised_ip = local_ip if is_on_lan else public_ip

        sdp_offer = (
            "v=0\r\n"
            f"o=tars 123456 123456 IN IP4 {advertised_ip}\r\n"
            "s=TARS Sentinel\r\n"
            f"c=IN IP4 {advertised_ip}\r\n"
            "t=0 0\r\n"
            f"m=audio {local_rtp_port} RTP/AVP 0 8 101\r\n"
            "a=rtpmap:0 PCMU/8000\r\n"
            "a=rtpmap:8 PCMA/8000\r\n"
            "a=rtpmap:101 telephone-event/8000\r\n"
            f"a=candidate:1 1 UDP 2130706431 {local_ip} {local_rtp_port} typ host\r\n"
            f"a=candidate:2 1 UDP 1694498815 {public_ip} {local_rtp_port} typ srflx\r\n"
            "a=sendrecv\r\n"
        )
        route_hdr = ""
        if routes:
            route_hdr = "Route: " + ", ".join(routes) + "\r\n"

        branch_ack = "z9hG4bK" + uuid.uuid4().hex[:20]
        ack2 = (
            f"ACK {contact_uri} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {public_ip}:{local_sip_port};branch={branch_ack};rport\r\n"
            + route_hdr +
            f'From: "{CALLER_DISPLAY}" <sip:{username}@{server}>;tag={from_tag}\r\n'
            f"To: <{target_sip_uri}>;tag={callee_tag}\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: 2 ACK\r\n"
            "Max-Forwards: 70\r\n"
            f"User-Agent: {CALLER_DISPLAY}\r\n"
            "Content-Type: application/sdp\r\n"
            f"Content-Length: {len(sdp_offer)}\r\n\r\n"
            f"{sdp_offer}"
        )
        sip_sock.sendto(ack2.encode(), (server, server_port))
        if routes:
            m_route = re.search(r'sips?:([^:;>]+)(?::(\d+))?', routes[0])
            if m_route:
                hop_h = m_route.group(1)
                hop_p = int(m_route.group(2)) if m_route.group(2) else 5060
                try:
                    sip_sock.sendto(ack2.encode(), (hop_h, hop_p))
                except Exception:
                    pass

        # Ensure greeting audio is finished synthesizing
        synth_t.join(timeout=8.0)
        greeting_ulaw = greeting_holder[0] or (b"\xff" * 16000)

        # Initialize continuous RTP player for unbroken audio stream (prevents pops/clicks)
        player = RTPPlayer(rtp_sock, destinations)

        # -------------------------------------------------------------
        # TURN 1: FAST BRIEFING (<4s)
        # -------------------------------------------------------------
        if destinations:
            print("🗣️ TARS Speaking Initial Briefing...")
            player.play(greeting_ulaw)
            player.play(beep_ulaw)

        # -------------------------------------------------------------
        # TURN 2: USER DICTATES INSTRUCTIONS (Snappy 0.8s Silence Cut)
        # -------------------------------------------------------------
        user_pcm, dtmf_digit = record_user_speech(rtp_sock, max_seconds=6.0, silence_timeout=0.8)

        # Instant 0ms filler audio: No dead silence!
        if destinations:
            player.play(ack_drafting_ulaw)

        transcript = ""
        if dtmf_digit == "1":
            transcript = "Confirm and send resume"
        elif dtmf_digit == "2":
            transcript = "Cancel, don't send"
        elif len(user_pcm) >= 2500:
            transcript = transcribe_pcm_audio(user_pcm)

        print(f"\n=======================================================")
        print(f"🗣️ USER INSTRUCTION RECEIVED: '{transcript}'")
        print(f"=======================================================")

        # Fast single-pass intent + email drafting in one LLM call
        analysis = parse_user_intent_and_draft(
            transcript=transcript or "Confirm and send resume",
            email_subject=clean_subject,
            email_sender=clean_sender,
            email_body=clean_reason or body
        )
        intent = analysis.get("intent", "CUSTOM_REPLY")
        attach_resume = analysis.get("attach_resume", True)
        spoken_confirmation = analysis.get("spoken_confirmation", "Shall I send this now, sir?")
        drafted_body = analysis.get("drafted_body", "")

        # -------------------------------------------------------------
        # TURN 3: VERIFY WITH USER BEFORE SENDING
        # -------------------------------------------------------------
        if intent == "CANCEL":
            cancel_audio = get_or_create_cached_audio("cancel", "Understood sir. Email canceled. Standing by.")
            if destinations:
                player.play(cancel_audio)
            action_summary = "Email canceled as requested"
        else:
            print(f"🗣️ TARS Confirming with User: '{spoken_confirmation}'")
            confirm_q_ulaw = asyncio.run(generate_speech_ulaw(spoken_confirmation, rate="+15%"))
            if destinations:
                player.play(confirm_q_ulaw)
                player.play(beep_ulaw)

            # Listen for quick confirmation (0.6s silence timeout)
            confirm_pcm, confirm_dtmf = record_user_speech(rtp_sock, max_seconds=4.0, silence_timeout=0.6)
            confirm_transcript = transcribe_pcm_audio(confirm_pcm) if len(confirm_pcm) >= 2000 else ""
            user_confirmed = is_user_confirming_send(confirm_transcript, confirm_dtmf)

            print(f"🗣️ USER CONFIRMATION: '{confirm_transcript}' | Decision: {user_confirmed}")

            # -------------------------------------------------------------
            # TURN 4: INSTANT DISPATCH VIA GMAIL & CLEAN FAREWELL
            # -------------------------------------------------------------
            if user_confirmed:
                if destinations:
                    player.play(ack_sending_ulaw)

                import tars_agent
                if email_id and drafted_body:
                    print(f"🚀 Instant Gmail reply with pre-drafted body (attach_resume={attach_resume})...")
                    res = tars_agent.tool_reply_to_emails(
                        email_ids=[email_id],
                        body=drafted_body,
                        attach_resume=attach_resume,
                        send_immediately=True
                    )
                    print(f"✅ Gmail Action Result: {res}")
                    action_summary = f"Replied to email via Gmail API: '{transcript}' (Resume attached: {attach_resume})"
                else:
                    action_summary = f"Simulated dispatch for '{clean_subject}'"

                if destinations:
                    player.play(farewell_ulaw)
            else:
                farewell_cancel = get_or_create_cached_audio("cancel", "Understood sir. Email canceled. Standing by.")
                if destinations:
                    player.play(farewell_cancel)
                action_summary = "Held for manual review in Telegram bot"

        send_telegram_summary(
            transcript=transcript or "(Silence/Inaudible)",
            action_taken=action_summary,
            sender=clean_sender,
            subject=clean_subject
        )

        time.sleep(0.5)

        # -------------------------------------------------------------
        # CLEAN DISCONNECT (SIP BYE)
        # -------------------------------------------------------------
        bye = (
            f"BYE {target_sip_uri} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {public_ip}:{local_sip_port};branch=z9hG4bK{uuid.uuid4().hex[:20]};rport\r\n"
            + route_hdr +
            f'From: "{CALLER_DISPLAY}" <sip:{username}@{server}>;tag={from_tag}\r\n'
            f"To: <{target_sip_uri}>;tag={callee_tag}\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: 3 BYE\r\n"
            "Max-Forwards: 70\r\n"
            "Content-Length: 0\r\n\r\n"
        )
        sip_sock.sendto(bye.encode(), (server, server_port))
        print("📴 Call concluded cleanly. BYE sent.")
    elif ringing_detected:
        cancel = (
            f"CANCEL {target_sip_uri} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {public_ip}:{local_sip_port};branch={branch2};rport\r\n"
            f'From: "{CALLER_DISPLAY}" <sip:{username}@{server}>;tag={from_tag}\r\n'
            f"To: <{target_sip_uri}>\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: 2 CANCEL\r\n"
            "Max-Forwards: 70\r\n"
            "Content-Length: 0\r\n\r\n"
        )
        sip_sock.sendto(cancel.encode(), (server, server_port))
        print("🔕 Ringing timed out. CANCEL sent.")

    sip_sock.close()
    rtp_sock.close()
    return ringing_detected or call_answered


def trigger_urgent_call_async(
    subject: str = "Urgent Email",
    sender: str = "",
    reason: str = "",
    email_id: str = None,
    body: str = "",
    ring_timeout: int = 60
):
    """Fires the SIP call in a detached background thread so it never blocks execution."""
    t = threading.Thread(
        target=trigger_urgent_call,
        kwargs={
            "subject": subject,
            "sender": sender,
            "reason": reason,
            "email_id": email_id,
            "body": body,
            "ring_timeout": ring_timeout
        },
        daemon=True,
        name="TARS-SIP-Caller"
    )
    t.start()
    return t


if __name__ == "__main__":
    trigger_urgent_call(
        subject="Meeting and Resume Request",
        sender="Mohammed Samer uddin ahmed <mdsameeruddintab.1@gmail.com>",
        reason="Samer requested your resume and a meeting regarding Data Science"
    )
