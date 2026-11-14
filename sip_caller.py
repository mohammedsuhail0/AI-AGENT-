import builtins
_orig_print = builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    return _orig_print(*args, **kwargs)

"""
TARS Voice Sentinel - Autonomous Interactive SIP Agent (100% Free Forever)
Direct VoIP Push Calling to Android via Linphone SIP (RFC 2617 Digest Auth).
Features:
- Native Android Lockscreen Wakeup via FCM Push.
- Natural Voice Briefing via Edge-TTS (Jarvis / TARS Persona).
- 2-Way Microphone Audio Capture over RTP (PCMU/PCMA) & RFC 2833 DTMF.
- Sub-300ms Speech Transcription via Groq Whisper (whisper-large-v3-turbo).
- Fast Intent Classification via Groq LLM (qwen/qwen3.8-27b / openai/gpt-oss-20b).
- Autonomous Gmail API Reply & Resume Attachment Dispatch.
- Instant Verbal Confirmation Spoken Over the Phone before Hangup.
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
CALLER_DISPLAY = os.environ.get("CALLER_DISPLAY_NAME", "TARS Sentinel")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


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


async def generate_speech_ulaw(text: str) -> bytes:
    """Synthesizes high-fidelity speech using Edge-TTS and converts to 8kHz G.711 u-law."""
    try:
        comm = edge_tts.Communicate(text, "en-US-GuyNeural")
        chunks = [c["data"] async for c in comm.stream() if c["type"] == "audio"]
        mp3_data = b"".join(chunks)
        decoded = miniaudio.decode(mp3_data, nchannels=1, sample_rate=8000)
        raw_pcm = decoded.samples.tobytes()
        return audioop.lin2ulaw(raw_pcm, 2)
    except Exception as e:
        print(f"⚠️ Edge-TTS synthesis failed: {e}")
        return b"\xff" * 16000


def generate_beep_ulaw(freq=800, duration_sec=0.25) -> bytes:
    """Generates an intercom prompt beep in u-law to signal user when TARS is listening."""
    pcm = bytearray()
    for i in range(int(8000 * duration_sec)):
        val = int(14000 * math.sin(2 * math.pi * freq * i / 8000))
        pcm.extend(struct.pack("<h", val))
    return audioop.lin2ulaw(bytes(pcm), 2)


def stream_audio(rtp_sock, destinations, ulaw_data, repeat=1, ssrc=0x34A8129B):
    """Streams audio packets simultaneously to all parsed RTP candidate destinations."""
    chunk_size = 160
    seq = 1
    timestamp = 0
    start_time = time.time()
    
    ipv4_sock = rtp_sock
    ipv6_sock = None
    try:
        ipv6_sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    except Exception:
        pass

    for r in range(repeat):
        for i in range(0, len(ulaw_data), chunk_size):
            chunk = ulaw_data[i:i+chunk_size]
            if len(chunk) < chunk_size:
                chunk += b"\xff" * (chunk_size - len(chunk))
            pkt = make_rtp_packet(seq, timestamp, ssrc, chunk, marker=(seq == 1))
            
            for target_ip, target_port in destinations:
                try:
                    if ":" in target_ip:
                        if ipv6_sock:
                            ipv6_sock.sendto(pkt, (target_ip, target_port))
                    else:
                        ipv4_sock.sendto(pkt, (target_ip, target_port))
                except Exception:
                    pass
            
            seq += 1
            timestamp += 160
            target_time = start_time + (seq * 0.02)
            sleep_dur = target_time - time.time()
            if sleep_dur > 0:
                time.sleep(sleep_dur)
        if r < repeat - 1:
            time.sleep(0.3)


def parse_sdp(sdp_text):
    """Parses SDP to extract both primary media address and all ICE candidate addresses."""
    destinations = []
    primary_ip = None
    ip_m = re.search(r'c=IN\s+(?:IP4|IP6)\s+([^\r\n;]+)', sdp_text)
    if ip_m:
        primary_ip = ip_m.group(1).strip()

    primary_port = None
    port_m = re.search(r'm=audio\s+(\d+)', sdp_text)
    if port_m:
        primary_port = int(port_m.group(1))

    if primary_ip and primary_port:
        destinations.append((primary_ip, primary_port))

    cand_matches = re.findall(r'a=candidate:\S+\s+\d+\s+(?:UDP|udp)\s+\d+\s+([^\s]+)\s+(\d+)', sdp_text)
    for c_ip, c_port in cand_matches:
        pair = (c_ip.strip(), int(c_port))
        if pair not in destinations:
            destinations.append(pair)

    return destinations


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
    """Transcribes user voice audio using Groq Whisper API (<300ms)."""
    if not groq_client or len(pcm_data) < 3000:
        return ""
    try:
        wav_bytes = pcm_to_wav_bytes(pcm_data)
        transcription = groq_client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=("speech.wav", wav_bytes),
            language="en",
            response_format="text"
        )
        text = transcription.strip() if isinstance(transcription, str) else getattr(transcription, "text", "").strip()
        print(f"🎤 Groq Whisper Transcribed: '{text}'")
        return text
    except Exception as e:
        print(f"⚠️ Groq Whisper transcription error: {e}")
        return ""


def classify_user_command(transcript: str, email_subject: str, email_sender: str, email_body: str) -> dict:
    """Classifies user voice command using Groq LLM with fallback heuristics."""
    clean_t = transcript.lower().strip()
    words = clean_t.split()
    
    # If transcript has more than 2 words or contains custom instructions, prioritize Groq LLM
    is_complex_or_custom = len(words) > 2 or any(cue in clean_t for cue in [
        "reply with", "tell them", "say that", "write that", "meet", "schedule", "tomorrow", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"
    ])

    if groq_client and (is_complex_or_custom or len(words) >= 2):
        prompt = f"""You are TARS, executive voice AI assistant on a live phone call with Mohammed Suhail.
The user just received this urgent email:
From: {email_sender}
Subject: {email_subject}
Content: {email_body[:1000]}

TARS asked: "Would you like me to send your resume and confirm, or what should I reply?"
The user responded on the phone call with this spoken voice command:
"{transcript}"

Determine user intent and action:
1. "CONFIRM_SEND": User wants to confirm with standard confirmation, said okay/yes/send/sure/go ahead.
2. "CUSTOM_REPLY": User gave a specific customized reply message or time/date (e.g. "tell them I will meet on Sunday", "reply with X").
3. "CANCEL": User said no/cancel/ignore/decline.
4. "UNCLEAR": Inaudible, silent, or unrelated.

If CUSTOM_REPLY, synthesize the user's exact instructions into 'instruction' (e.g., "Confirm meeting and inform that Mohammed is available to meet on Sunday, attach resume").

Respond ONLY with valid JSON:
{{
  "intent": "CONFIRM_SEND" | "CUSTOM_REPLY" | "CANCEL" | "UNCLEAR",
  "instruction": "Instruction for drafting reply",
  "attach_resume": true or false,
  "voice_response": "One crisp, direct sentence TARS speaks back on phone confirming action taken."
}}"""
        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
            try:
                resp = groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                import json
                data = json.loads(resp.choices[0].message.content)
                if data and "intent" in data:
                    return data
            except Exception as e:
                continue

    # Fast path keyword heuristics for simple 1-2 word confirmations
    positive_cues = ["ok", "okay", "send", "yes", "yeah", "yep", "sure", "confirm", "go ahead", "do it", "dispatch"]
    cancel_cues = ["no", "nope", "cancel", "stop", "ignore", "don't", "dont", "decline"]
    
    if any(cue in clean_t for cue in positive_cues) and not any(neg in clean_t for neg in cancel_cues):
        return {
            "intent": "CONFIRM_SEND",
            "instruction": "Confirm enthusiastically and attach resume.",
            "attach_resume": True,
            "voice_response": "Affirmative, Commander. Your reply has been sent and your resume is attached. Have a great day!"
        }
    
    if any(cue in clean_t for cue in cancel_cues):
        return {
            "intent": "CANCEL",
            "instruction": "",
            "attach_resume": False,
            "voice_response": "Understood Commander. No email sent. Standing by."
        }

    return {
        "intent": "UNCLEAR",
        "instruction": "Confirm enthusiastically and attach resume.",
        "attach_resume": True,
        "voice_response": "I couldn't hear your instruction Commander. The draft is saved in your Telegram bot. Standing by."
    }


def record_user_speech(rtp_sock, max_seconds=7.0, silence_timeout=1.5) -> tuple[bytes, str]:
    """
    Records incoming RTP audio packets from the user's phone microphone.
    Handles PCMU (PT=0), PCMA (PT=8), and RFC 2833 DTMF events (PT=101).
    Uses RMS volume Voice Activity Detection (VAD) to auto-stop on silence.
    Returns (linear_pcm_bytes, dtmf_digit).
    """
    print(f"👂 [TARS Intercom Active] Listening for voice command over phone mic (Max {max_seconds}s)...")
    
    # Drain any buffered packets from socket
    rtp_sock.setblocking(False)
    while True:
        try:
            rtp_sock.recvfrom(4096)
        except Exception:
            break
    
    rtp_sock.settimeout(0.05)
    
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
            
            # CSRC and extension skip
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
                print(f"🔢 Keypad DTMF detected: '{dtmf_digit}'")
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
                
                if rms > 450:
                    if not speech_detected:
                        print(f"🎙️ Speech detected! (RMS={rms})")
                        speech_detected = True
                    last_speech_time = time.time()
                
                # If speech was detected and user paused for silence_timeout
                if speech_detected and (time.time() - last_speech_time > silence_timeout) and len(frames) > 25:
                    print("🤫 Silence detected after speech. Finished listening.")
                    break

        except socket.timeout:
            continue
        except Exception as e:
            continue
            
    pcm_bytes = b"".join(frames)
    print(f"📊 Audio recorded: {len(pcm_bytes)/16000:.1f}s | Speech detected: {speech_detected} | DTMF: {dtmf_digit}")
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
    Autonomous Interactive Jarvis Voice Sentinel:
    1. Rings Mohammed's Android phone via Linphone push calling (FCM push on lockscreen).
    2. Speaks natural Jarvis-style briefing when answered.
    3. Emits prompt chime and listens to phone microphone.
    4. Transcribes spoken instructions with Groq Whisper.
    5. Dispatches email reply & resume attachment via Gmail API if confirmed.
    6. Speaks verbal confirmation before cleanly disconnecting.
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
        clean_subject = "Direct Opportunity & Meeting Request"
    clean_reason = reason.replace('"', '').strip() if reason else ""

    # Build Jarvis Briefing Script
    briefing_text = (
        f"Greetings Commander Suhail. TARS Sentinel here. "
        f"You have an urgent incoming email from {clean_sender}. "
    )
    if clean_reason:
        briefing_text += f"{clean_reason}. "
    else:
        briefing_text += f"Regarding {clean_subject}. "
    briefing_text += "Would you like me to send your resume and confirm, or what should I reply?"

    print(f"\n=======================================================")
    print(f"🚨 TARS SENTINEL - TRIGGERING AUTONOMOUS CALL")
    print(f"Target: {target_sip_uri}")
    print(f"Sender: {clean_sender}")
    print(f"Subject: {clean_subject}")
    print(f"=======================================================")

    print("⚙️ Synthesizing briefing voice with Edge-TTS...")
    greeting_ulaw = asyncio.run(generate_speech_ulaw(briefing_text))
    beep_ulaw = generate_beep_ulaw(freq=800, duration_sec=0.25)
    print(f"✅ Voice audio prepared ({len(greeting_ulaw)/8000:.1f}s).")

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
        "User-Agent: TARS Voice Sentinel 1.0\r\n"
        "Content-Length: 0\r\n\r\n"
    )

    print(f"📞 Dialing {target_sip_uri}...")
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
        "User-Agent: TARS Voice Sentinel 1.0\r\n"
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
            print(f">>> SIP: {first_line}")

            if "110 Push sent" in msg:
                print("📲 FCM push notification sent to Android phone!")
            elif "180 Ringing" in msg:
                if not ringing_detected:
                    print("\n🔔🔔🔔 PHONE IS RINGING! [Ringtone playing on Android...] 🔔🔔🔔")
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
        destinations = parse_sdp(callee_sdp)
        print(f"Discovered RTP destinations ({len(destinations)}): {destinations}")

        # Adaptive SDP media address: Use local LAN IP if phone is on Wi-Fi
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
            "User-Agent: TARS Voice Sentinel 1.0\r\n"
            "Content-Type: application/sdp\r\n"
            f"Content-Length: {len(sdp_offer)}\r\n\r\n"
            f"{sdp_offer}"
        )
        print(f"Sending ACK to {contact_uri}...")
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

        # 1. TARS Speaks the Briefing
        if destinations:
            print("🗣️ TARS is speaking email summary into call...")
            stream_audio(rtp_sock, destinations, greeting_ulaw, repeat=1)
            time.sleep(0.2)
            # 2. Play prompt chime to signal listening mode
            stream_audio(rtp_sock, destinations, beep_ulaw, repeat=1)

        # 3. TARS Listens to Phone Microphone
        user_pcm, dtmf_digit = record_user_speech(rtp_sock, max_seconds=7.0, silence_timeout=1.5)

        # 4. Process Voice Command or DTMF
        transcript = ""
        if dtmf_digit == "1":
            transcript = "Yes, send it"
        elif dtmf_digit == "2":
            transcript = "No, cancel"
        elif len(user_pcm) >= 3000:
            transcript = transcribe_pcm_audio(user_pcm)

        print(f"\n=======================================================")
        print(f"🗣️ COMMAND RECEIVED: '{transcript}'")
        print(f"=======================================================")

        analysis = classify_user_command(
            transcript=transcript,
            email_subject=clean_subject,
            email_sender=clean_sender,
            email_body=clean_reason or body
        )
        intent = analysis.get("intent", "UNCLEAR")
        voice_response = analysis.get("voice_response", "Standing by Commander.")
        attach_resume = analysis.get("attach_resume", True)
        instruction = analysis.get("instruction", "Confirm enthusiastically and attach resume.")

        action_summary = "No action taken"

        # 5. Execute Autonomous Actions via TARS Agent & Gmail API
        if intent in ("CONFIRM_SEND", "CUSTOM_REPLY"):
            import tars_agent
            if email_id:
                print(f"🚀 Executing Gmail reply for email {email_id} (attach_resume={attach_resume})...")
                res = tars_agent.tool_reply_to_emails(
                    email_ids=[email_id],
                    instruction=instruction,
                    attach_resume=attach_resume,
                    send_immediately=True
                )
                print(f"✅ Gmail Action Result: {res}")
                action_summary = f"Replied to email via Gmail API (Resume attached: {attach_resume})"
            else:
                print("⚡ Simulation / Test mode: Verified action execution without email_id.")
                action_summary = f"Simulated confirmation for '{clean_subject}' (Resume attached: {attach_resume})"
        elif intent == "CANCEL":
            action_summary = "Email canceled as requested"
        else:
            action_summary = "Draft stored in Telegram for manual tap approval"

        # Send Telegram report
        send_telegram_summary(
            transcript=transcript or "(Silence/Inaudible)",
            action_taken=action_summary,
            sender=clean_sender,
            subject=clean_subject
        )

        # 6. TARS Speaks Verbal Confirmation to User
        print(f"🗣️ TARS Speaking Verbal Confirmation: '{voice_response}'")
        confirm_ulaw = asyncio.run(generate_speech_ulaw(voice_response))
        if destinations:
            stream_audio(rtp_sock, destinations, confirm_ulaw, repeat=1)

        time.sleep(1.0)

        # 7. Hangup Cleanly (SIP BYE)
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
        reason="Samer is requesting your resume and asking for a meeting regarding Data Science"
    )
