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
import random
import re
import time
import struct
import threading
import asyncio
import math
import wave
import json
import requests
import ctypes
import edge_tts
import miniaudio
import audioop
from groq import Groq
import base64
import hmac
import zlib
try:
    import pylibsrtp
    HAVE_SRTP = True
except ImportError:
    HAVE_SRTP = False

def handle_stun_packet(data: bytes, addr: tuple, sock: socket.socket, ice_pwd: str = "tarspassword12345678") -> bool:
    """
    RFC 5389 / RFC 5245 STUN Binding Success Responder.
    Instantly satisfies WebRTC / Linphone ICE connectivity checks on the RTP socket!
    """
    if len(data) < 20:
        return False
    msg_type, msg_len = struct.unpack("!HH", data[:4])
    magic = data[4:8]
    if msg_type == 0x0001 and magic == b"\x21\x12\xa4\x42":
        trans_id = data[8:20]
        try:
            ip_parts = [int(p) for p in addr[0].split(".")]
            raw_ip = (ip_parts[0] << 24) | (ip_parts[1] << 16) | (ip_parts[2] << 8) | ip_parts[3]
            x_port = addr[1] ^ 0x2112
            x_ip = raw_ip ^ 0x2112A442
            xor_mapped = struct.pack("!HHBBHII", 0x0020, 8, 0, 1, x_port, (x_ip >> 16) & 0xFFFF, x_ip & 0xFFFF)
            
            attr_len_with_mi = len(xor_mapped) + 24
            header_for_mi = struct.pack("!HHI", 0x0101, attr_len_with_mi, 0x2112A442) + trans_id
            msg_to_sign = header_for_mi + xor_mapped
            mi_hash = hmac.new(ice_pwd.encode(), msg_to_sign, hashlib.sha1).digest()
            mi_attr = struct.pack("!HH", 0x0008, 20) + mi_hash
            
            full_body = xor_mapped + mi_attr
            attr_len_with_fp = len(full_body) + 8
            header_final = struct.pack("!HHI", 0x0101, attr_len_with_fp, 0x2112A442) + trans_id
            msg_for_fp = header_final + full_body
            crc = (zlib.crc32(msg_for_fp) & 0xFFFFFFFF) ^ 0x5354554e
            fp_attr = struct.pack("!HHI", 0x8028, 4, crc)
            
            resp = header_final + full_body + fp_attr
            sock.sendto(resp, addr)
            print(f"⚡ Replied to STUN Binding Request from {addr} (ICE check passed!)")
            return True
        except Exception as e:
            print(f"⚠️ STUN handler error: {e}")
    return False

# Set Windows multimedia timer resolution to 1ms for studio-grade low jitter
try:
    winmm = ctypes.WinDLL('winmm')
    winmm.timeBeginPeriod(1)
except Exception:
    pass

# Load environment
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

LINPHONE_USERNAME = os.environ.get("TARS_SIP_USERNAME", os.environ.get("LINPHONE_USERNAME", "suhail_tars"))
LINPHONE_PASSWORD = os.environ.get("TARS_SIP_PASSWORD", os.environ.get("LINPHONE_PASSWORD", "iD_6W_6kZyC#Tnp"))
LINPHONE_DOMAIN = os.environ.get("TARS_SIP_DOMAIN", os.environ.get("LINPHONE_DOMAIN", "sip.linphone.org"))
LINPHONE_TARGET = os.environ.get("USER_SIP_URI", os.environ.get("LINPHONE_TARGET_URI", "sip:mohammed_suhail@sip.linphone.org"))
CALLER_DISPLAY = os.environ.get("CALLER_DISPLAY_NAME", "TARS")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

VOICE_MODEL = "en-GB-RyanNeural"  # Young, crisp British voice (eliminates old-man sound)
VOICE_PITCH = "-1Hz"              # Refined mid-baritone resonance
VOICE_RATE = "-2%"                # Composed, unflappable Jarvis cadence
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_audio_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
_SIP_CALL_LOCK = threading.Lock()
_CACHED_PUBLIC_IP = None
_LAST_PUBLIC_IP_CHECK = 0
_active_inbound_call_id = None
_active_inbound_lock = threading.Lock()


def get_public_ip(force_refresh=False) -> str:
    """Finds the external public WAN IP address with auto-refresh on network changes."""
    global _CACHED_PUBLIC_IP, _LAST_PUBLIC_IP_CHECK
    now = time.time()
    if not force_refresh and _CACHED_PUBLIC_IP and (now - _LAST_PUBLIC_IP_CHECK < 120):
        return _CACHED_PUBLIC_IP
    for url in ["https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"]:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200 and r.text.strip():
                _CACHED_PUBLIC_IP = r.text.strip()
                _LAST_PUBLIC_IP_CHECK = now
                return _CACHED_PUBLIC_IP
        except Exception:
            continue
    return _CACHED_PUBLIC_IP or "106.195.65.85"


def get_local_ip() -> str:
    """Finds the local network Wi-Fi IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"



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


def clean_spoken_text(text: str) -> str:
    """Sanitizes text for speech synthesis: strips markdown, bullets, URLs, and enforces strictly 1-3 spoken sentences with natural punctuation."""
    if not text:
        return ""
    # Convert markdown links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]*\)', r'\1', text)
    # Strip standalone URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    # Strip markdown formatting: *, _, #, `, ~, >, |, bullet symbols
    text = re.sub(r'[*_#`~>|•]', ' ', text)
    # Remove bullet list markers like "- ", "+ " at start of lines or after punctuation
    text = re.sub(r'(?:^|(?<=[.!?:\s]))[-+*]\s+', '', text)
    # Remove numbering like "1. ", "2) " anywhere after start of line or punctuation/whitespace
    text = re.sub(r'(?:^|(?<=[.!?:\s]))\d+[\.\)]\s+', '', text)
    # Convert double dashes or em-dashes to commas for breathing pauses
    text = re.sub(r'—|–|--', ', ', text)
    # Normalize multiple whitespace and clean up punctuation spacing
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s+([,.!?])', r'\1', text)
    # Enforce strictly 1-3 sentences maximum
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if len(sentences) > 3:
        text = " ".join(sentences[:3])
    return text


async def generate_speech_ulaw(text: str, rate: str = VOICE_RATE, pitch: str = VOICE_PITCH) -> bytes:
    """Synthesizes high-fidelity speech using Edge-TTS configured for Marvel's JARVIS (en-GB-RyanNeural) and converts to 8kHz u-law."""
    try:
        text = clean_spoken_text(text)
        comm = edge_tts.Communicate(text, VOICE_MODEL, rate=rate, pitch=pitch)
        chunks = [c["data"] async for c in comm.stream() if c["type"] == "audio"]
        mp3_data = b"".join(chunks)
        decoded = miniaudio.decode(mp3_data, nchannels=1, sample_rate=8000)
        raw_pcm = decoded.samples.tobytes()
        # Scale to 85% to eliminate digital clipping and harsh DAC distortion on phone speakers
        scaled_pcm = audioop.mul(raw_pcm, 2, 0.85)
        return audioop.lin2ulaw(scaled_pcm, 2)
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
    ulaw = asyncio.run(generate_speech_ulaw(text, rate=VOICE_RATE, pitch=VOICE_PITCH))
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
    """Maintains RFC 3550 / RFC 3551 continuous wall-clock timestamps and monotonic sequence numbers with sub-millisecond frame pacing."""
    def __init__(self, rtp_sock, destinations, ssrc=0x34A8129B, srtp_session=None):
        self.rtp_sock = rtp_sock
        self.destinations = list(destinations) if destinations else []
        self.ssrc = ssrc if ssrc is not None else 0x34A8129B
        self.srtp_session = srtp_session
        self.seq = random.randint(1000, 25000)
        self.session_t0 = time.perf_counter()
        self.base_ts = random.randint(10000, 200000)
        self._silence_running = False
        self._silence_thread = None

    def start_silence_stream(self):
        """Streams continuous RFC 3550 silence frames (20ms, 0xFF u-law) during listening periods so Linphone's quality bar stays full green."""
        if self._silence_running:
            return
        self._silence_running = True
        def _silence_worker():
            chunk = b"\xff" * 160
            while self._silence_running:
                t_now = time.perf_counter()
                elapsed_sec = t_now - self.session_t0
                frame_ts = (self.base_ts + int(elapsed_sec * 8000)) & 0xFFFFFFFF
                pkt = make_rtp_packet(self.seq, frame_ts, self.ssrc, chunk, marker=False)
                if self.srtp_session:
                    try:
                        pkt = self.srtp_session.protect(pkt)
                    except Exception:
                        pass
                for target_ip, target_port in list(self.destinations):
                    try:
                        self.rtp_sock.sendto(pkt, (target_ip, target_port))
                    except Exception:
                        pass
                self.seq = (self.seq + 1) & 0xFFFF
                time.sleep(0.020)
        self._silence_thread = threading.Thread(target=_silence_worker, daemon=True, name="RTP-Silence-Stream")
        self._silence_thread.start()

    def stop_silence_stream(self):
        self._silence_running = False
        t = getattr(self, '_silence_thread', None)
        if t and t.is_alive():
            t.join(timeout=0.04)

    def play(self, ulaw_data):
        if not ulaw_data or not self.destinations:
            return
        self.stop_silence_stream()
        chunk_size = 160
        chunks_count = (len(ulaw_data) + chunk_size - 1) // chunk_size
        
        # In RFC 3550 Section 5.1, the timestamp reflects the true wall-clock sampling instant (8000Hz).
        # Aligning the start timestamp with elapsed real time completely eliminates Linphone's jitter buffer
        # panic, keeping the call quality bar solid GREEN (4 bars) and preventing fast/choppy playback!
        t_start = time.perf_counter()
        elapsed_sec = t_start - self.session_t0
        start_ts = (self.base_ts + int(elapsed_sec * 8000)) & 0xFFFFFFFF
        
        for idx in range(chunks_count):
            start = idx * chunk_size
            chunk = ulaw_data[start:start + chunk_size]
            if len(chunk) < chunk_size:
                chunk += b"\xff" * (chunk_size - len(chunk))
                
            frame_ts = (start_ts + (idx * 160)) & 0xFFFFFFFF
            # Marker bit (M) set to 1 on the first packet of a talkspurt per RFC 3551 Section 4.1
            pkt = make_rtp_packet(self.seq, frame_ts, self.ssrc, chunk, marker=(idx == 0))
            if self.srtp_session:
                try:
                    pkt = self.srtp_session.protect(pkt)
                except Exception as e:
                    pass

            for target_ip, target_port in self.destinations:
                try:
                    self.rtp_sock.sendto(pkt, (target_ip, target_port))
                except Exception:
                    pass

            self.seq = (self.seq + 1) & 0xFFFF

            # Precision pacing: exactly 20.0ms per frame
            target_time = t_start + (0.020 * (idx + 1))
            while True:
                rem = target_time - time.perf_counter()
                if rem <= 0:
                    break
                if rem > 0.002:
                    time.sleep(0.001)

        # Resume comfort silence immediately so peer buffer stays continuously primed & green
        self.start_silence_stream()


def stream_audio(rtp_sock, destinations, ulaw_data, repeat=1, ssrc=0x34A8129B):
    """Convenience wrapper for legacy calls."""
    player = RTPPlayer(rtp_sock, destinations, ssrc=ssrc)
    for _ in range(repeat):
        player.play(ulaw_data)


def select_best_rtp_destination(sdp_text: str) -> list[tuple[str, int]]:
    """
    Parses SDP to extract audio stream endpoints.
    Returns prioritized destinations [LAN, WAN] so initial talkspurts arrive immediately,
    while symmetric RTP automatically locks onto the active socket once packets flow.
    """
    audio_section = sdp_text
    m_audio = re.search(r'(m=audio\s+[^\r\n]+(?:[\r\n]+(?!m=)[^\r\n]+)*)', sdp_text, re.IGNORECASE)
    if m_audio:
        audio_section = m_audio.group(1)

    cand_matches = re.findall(r'a=candidate:\S+\s+1\s+(?:UDP|udp)\s+\d+\s+([^\s]+)\s+(\d+)', audio_section)
    destinations = [(ip.strip(), int(port)) for ip, port in cand_matches]

    # Connection IP: check audio section first, fallback to session level
    c_ip = re.search(r'c=IN\s+(?:IP4|IP6)\s+([^\r\n;]+)', audio_section)
    if not c_ip:
        c_ip = re.search(r'c=IN\s+(?:IP4|IP6)\s+([^\r\n;]+)', sdp_text)

    m_port = re.search(r'm=audio\s+(\d+)', audio_section)
    if c_ip and m_port:
        pair = (c_ip.group(1).strip(), int(m_port.group(1)))
        if pair not in destinations:
            destinations.append(pair)

    lan_dests = [d for d in destinations if d[0].startswith(("192.168.", "10.", "172."))]
    wan_dests = [d for d in destinations if not d[0].startswith(("192.168.", "10.", "172."))]

    res = []
    if lan_dests:
        res.append(lan_dests[0])
    if wan_dests:
        res.append(wan_dests[0])
    if not res and destinations:
        res = destinations[:1]

    print(f"🎯 Audio RTP initial endpoints: {res} (Direct + Relay dual-armed)")
    return res


def build_sdp_offer(local_ip: str, public_ip: str, local_rtp_port: int, is_lan: bool = True) -> str:
    """
    Constructs an RFC 3264 / RFC 3551 compliant Early Offer SDP.
    Offers audio only with PCMU (0), PCMA (8), and telephone-event (101).
    Includes direct host/srflx candidates without bidirectional ICE overhead.
    """
    adv_ip = local_ip if is_lan else public_ip
    sdp = (
        "v=0\r\n"
        f"o=tars 123456 123456 IN IP4 {adv_ip}\r\n"
        "s=TARS Sentinel\r\n"
        f"c=IN IP4 {adv_ip}\r\n"
        "t=0 0\r\n"
        f"m=audio {local_rtp_port} RTP/AVP 0 8 101\r\n"
        f"c=IN IP4 {adv_ip}\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=rtpmap:8 PCMA/8000\r\n"
        "a=rtpmap:101 telephone-event/8000\r\n"
        f"a=rtcp:{local_rtp_port}\r\n"
        "a=rtcp-mux\r\n"
        "a=ssrc:883438235 cname:tars\r\n"
        f"a=candidate:1 1 UDP 2130706431 {local_ip} {local_rtp_port} typ host\r\n"
        f"a=candidate:2 1 UDP 1694498815 {public_ip} {local_rtp_port} typ srflx\r\n"
        "a=sendrecv\r\n"
    )
    return sdp


def build_sdp_answer(offer_sdp: str, local_ip: str, public_ip: str, local_rtp_port: int, is_lan: bool = True) -> tuple[str, any, any]:
    """
    Constructs an RFC 3264 / RFC 4568 compliant SDP answer matching the exact number and order of m= lines in the offer.
    Supports SRTP (RTP/SAVPF) with direct Wi-Fi host candidate and instant STUN response support.
    Returns (sdp_answer_str, tx_srtp_session, rx_srtp_session).
    """
    adv_ip = local_ip if is_lan else public_ip
    sdp_lines = [
        "v=0",
        f"o=tars 123456 123456 IN IP4 {adv_ip}",
        "s=TARS Sentinel",
        f"c=IN IP4 {adv_ip}",
        "t=0 0"
    ]

    # Check for SRTP in offer (AES_CM_128_HMAC_SHA1_80)
    tx_srtp, rx_srtp = None, None
    crypto_answer_line = None
    crypto_match = re.search(r'a=crypto:(\d+)\s+(AES_CM_128_HMAC_SHA1_80)\s+inline:([A-Za-z0-9+/=]+)', offer_sdp)
    if crypto_match and HAVE_SRTP:
        tag, suite, rem_b64 = crypto_match.groups()
        rem_b64_clean = rem_b64.split("|")[0].strip()
        try:
            rem_key = base64.b64decode(rem_b64_clean)
            if len(rem_key) == 30:
                loc_key = os.urandom(30)
                loc_b64 = base64.b64encode(loc_key).decode()
                crypto_answer_line = f"a=crypto:{tag} {suite} inline:{loc_b64}"
                rx_policy = pylibsrtp.Policy(key=rem_key, ssrc_type=pylibsrtp.Policy.SSRC_ANY_INBOUND)
                rx_srtp = pylibsrtp.Session(policy=rx_policy)
                tx_policy = pylibsrtp.Policy(key=loc_key, ssrc_type=pylibsrtp.Policy.SSRC_ANY_OUTBOUND)
                tx_srtp = pylibsrtp.Session(policy=tx_policy)
                print(f"🔒 SRTP Negotiated successfully with suite {suite} (Tag: {tag})")
        except Exception as e:
            print(f"⚠️ SRTP setup error: {e}")

    # Find telephone-event payload type strictly at 8000Hz from offer
    te_match = re.search(r'a=rtpmap:(\d+)\s+telephone-event/8000', offer_sdp, re.IGNORECASE)
    te_pt = te_match.group(1) if te_match else None

    # Parse all m= blocks in the offer to maintain 1-to-1 correspondence
    m_blocks = re.findall(r'm=(\w+)\s+(\d+)\s+([^\r\n]+)', offer_sdp)
    if not m_blocks:
        m_blocks = [("audio", "0", "RTP/AVP 0 8")]

    for m_type, m_port, m_rest in m_blocks:
        parts = m_rest.split()
        proto = parts[0] if parts else "RTP/AVP"
        if m_type.lower() == "audio":
            # Echo proto: RTP/SAVPF if SRTP negotiated, else RTP/AVP
            ans_proto = proto if (crypto_answer_line and "SAVP" in proto) else "RTP/AVP"
            codecs = ["0", "8"]
            if te_pt:
                codecs.append(te_pt)
            codecs_str = " ".join(codecs)
            sdp_lines.append(f"m=audio {local_rtp_port} {ans_proto} {codecs_str}")
            sdp_lines.append(f"c=IN IP4 {adv_ip}")
            if crypto_answer_line:
                sdp_lines.append(crypto_answer_line)
            sdp_lines.append("a=rtpmap:0 PCMU/8000")
            sdp_lines.append("a=rtpmap:8 PCMA/8000")
            if te_pt:
                sdp_lines.append(f"a=rtpmap:{te_pt} telephone-event/8000")
            sdp_lines.append(f"a=rtcp:{local_rtp_port}")
            if "a=rtcp-mux" in offer_sdp:
                sdp_lines.append("a=rtcp-mux")
            sdp_lines.append("a=ssrc:883438235 cname:tars")
            sdp_lines.append(f"a=candidate:1 1 UDP 2130706431 {local_ip} {local_rtp_port} typ host")
            sdp_lines.append(f"a=candidate:2 1 UDP 1694498815 {public_ip} {local_rtp_port} typ srflx")
            sdp_lines.append("a=sendrecv")
        else:
            # Reject non-audio stream (e.g. video) with port 0 and c=IN IP4 0.0.0.0 per RFC 3264
            fmts = " ".join(parts[1:]) if len(parts) > 1 else "0"
            sdp_lines.append(f"m={m_type} 0 {proto} {fmts}")
            sdp_lines.append("c=IN IP4 0.0.0.0")

    return "\r\n".join(sdp_lines) + "\r\n", tx_srtp, rx_srtp


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
        prompt = f"""You are TARS, executive voice AI assistant speaking on a live phone call with Mohammed Suhail. Always address him naturally as 'boss'. Keep it completely natural, crisp, and direct (no sci-fi jargon).
Incoming email from: {email_sender}
Subject: {email_subject}
Content: {email_body[:600]}

The boss dictated this instruction on the call:
"{transcript}"

Do TWO tasks in valid JSON:
1. 'spoken_confirmation': A crisp, natural sentence TARS speaks back to Suhail to verify before sending (e.g. "Got it boss. I'll let {clean_first_name} know you can meet Sunday, and attach your resume. Should I send it now, boss?").
2. 'drafted_body': The professional, concise reply email body (plain text, no placeholder brackets) signed 'Best regards,\nMohammed Suhail'.

Respond ONLY with valid JSON:
{{
  "intent": "CUSTOM_REPLY" | "CONFIRM_SEND" | "CANCEL",
  "instruction": "Summary of user command",
  "attach_resume": true or false,
  "spoken_confirmation": "Short natural question asking to confirm, addressing Suhail as boss",
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
        "spoken_confirmation": f"Got it boss. I'll reply with your instructions and attach your resume. Should I send it now, boss?",
        "drafted_body": fallback_body
    }


def classify_confirmation_or_correction(transcript: str, dtmf: str = None) -> tuple[str, str]:
    """
    Distinguishes pure confirmation ('CONFIRM'), pure cancellation ('CANCEL'),
    or user dictating an update/correction ('UPDATE', correction_text).
    """
    if dtmf == "1":
        return "CONFIRM", ""
    if dtmf == "2":
        return "CANCEL", ""
    clean = transcript.lower().strip()
    if not clean:
        return "CANCEL", ""
    if clean in ["cancel", "no", "stop", "don't send", "dont send", "never mind", "nevermind", "exit"]:
        return "CANCEL", ""
    positive = ["yes", "yeah", "yep", "send", "send it", "go ahead", "okay", "ok", "confirm", "do it", "sure", "dispatch", "looks good", "perfect"]
    has_pos = any(p in clean.split() or clean.startswith(p) for p in positive)
    has_mod = any(neg in clean for neg in ["change", "instead", "don't", "dont", "make it", "actually", "rather", "next", "say", "tell", "after"])
    if has_pos and not has_mod:
        return "CONFIRM", ""
    if has_mod or len(clean.split()) >= 3:
        return "UPDATE", transcript
    return "CANCEL", ""


def is_user_confirming_send(transcript: str, dtmf: str = None) -> bool:
    """Checks if user confirmed dispatching the email (or pressed 1)."""
    decision, _ = classify_confirmation_or_correction(transcript, dtmf)
    return decision == "CONFIRM"


def record_user_speech(rtp_sock, max_seconds=15.0, silence_timeout=1.8, player=None, srtp_session=None) -> tuple[bytes, str]:
    """
    Records incoming RTP audio packets from the user's phone microphone.
    Natural 1.8s silence timeout gives comfortable room for conversational pauses without cutting user off.
    Supports symmetric RTP: automatically locks onto the sender's transmitting port.
    Supports SRTP decryption when srtp_session is provided.
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
    
    pkt_cnt = 0
    while time.time() - start_time < max_seconds:
        try:
            data, sender_addr = rtp_sock.recvfrom(2048)
            # Handle WebRTC / Linphone ICE STUN checks instantly
            if handle_stun_packet(data, sender_addr, rtp_sock):
                continue

            # Filter RTCP multiplexed control packets (RFC 5761 PT 200..206)
            if len(data) >= 2 and (data[1] & 0x7F) in (200, 201, 202, 203, 204, 205, 206):
                continue

            if srtp_session:
                try:
                    dec = srtp_session.unprotect(data)
                    data = dec
                except Exception:
                    # Fallback: if raw packet is already valid unencrypted RTP version 2
                    if len(data) >= 12 and (data[0] >> 6) == 2 and (data[1] & 0x7F) in (0, 8, 96, 97, 98, 100, 101):
                        pass
                    else:
                        continue

            if len(data) < 12:
                continue
            
            pkt_cnt += 1
            byte0, byte1, seq, ts, ssrc = struct.unpack("!BBHII", data[:12])
            pt = byte1 & 0x7F

            if pkt_cnt == 1:
                print(f"📦 First RTP audio packet received from {sender_addr}: len={len(data)}, pt={pt}")

            # Symmetric RTP: ensure response packets route to actual transmitting endpoint
            if player and sender_addr and (not player.destinations or sender_addr != player.destinations[0]):
                player.destinations = [sender_addr]
                print(f"🎯 Symmetric RTP locked onto transmitting client endpoint: {sender_addr}")
            
            cc = byte0 & 0x0F
            header_len = 12 + (cc * 4)
            if (byte0 >> 4) & 0x01 and len(data) >= header_len + 4:
                _, ext_len = struct.unpack("!HH", data[header_len:header_len+4])
                header_len += 4 + (ext_len * 4)
            
            payload = data[header_len:]
            if not payload:
                continue
            
            # 1. Check for DTMF (telephone-event)
            if pt in (100, 101):
                event_code = payload[0]
                if event_code <= 9:
                    dtmf_digit = str(event_code)
                elif event_code == 10:
                    dtmf_digit = "*"
                elif event_code == 11:
                    dtmf_digit = "#"
                print(f"🔢 Keypad DTMF: '{dtmf_digit}'")
                break

            # 2. Decode audio payload (PCMU 0, PCMA 8, or raw fallback)
            linear = None
            if pt == 0:  # PCMU
                linear = audioop.ulaw2lin(payload, 2)
            elif pt == 8:  # PCMA
                linear = audioop.alaw2lin(payload, 2)
            elif pt not in (101,):
                try:
                    linear = audioop.ulaw2lin(payload, 2)
                except Exception:
                    pass
            
            if linear:
                frames.append(linear)
                rms = audioop.rms(linear, 2)
                
                if rms > 180:
                    if not speech_detected:
                        speech_detected = True
                        print(f"🎙️ User speech detected on microphone (rms={rms})")
                    last_speech_time = time.time()
                
                # Natural silence detection (1.2s) gives enough room for natural sentence pauses
                if speech_detected and (time.time() - last_speech_time > silence_timeout) and len(frames) > 20:
                    print(f"⏹️ Speech pause detected after {len(frames)*0.02:.1f}s")
                    break

        except socket.timeout:
            continue
        except Exception:
            continue
            
    pcm_bytes = b"".join(frames)
    print(f"📊 Audio segment captured: {len(frames)} frames ({len(frames)*0.02:.2f}s, {len(pcm_bytes)} bytes, {pkt_cnt} RTP pkts)")
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


def send_telegram_status(message: str):
    """Sends immediate status alerts to Suhail's Telegram so he always knows TARS is active."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"⚠️ Telegram status alert error: {e}")


def _trigger_urgent_call_impl(
    subject: str = "Urgent Email",
    sender: str = "",
    reason: str = "",
    email_id: str = None,
    body: str = "",
    ring_timeout: int = 60
) -> bool:
    server = LINPHONE_DOMAIN
    server_port = 5060
    username = LINPHONE_USERNAME
    password = LINPHONE_PASSWORD
    target_sip_uri = LINPHONE_TARGET
    public_ip = get_public_ip()
    local_ip = get_local_ip()

    clean_sender = sender.split("<")[0].strip().replace('"', '') if sender else "an important contact"
    clean_subject = subject.replace('"', '').strip()
    if not clean_subject:
        clean_subject = "Meeting Request"
    clean_reason = reason.replace('"', '').strip() if reason else ""

    # Crisp, punchy Marvel JARVIS Briefing Script (under 16 words = ~3.5s speaking time)
    briefing_text = (
        f"Hello boss, we got an email from {clean_sender}. "
        f"{clean_reason or clean_subject}. What should we reply?"
    )

    print(f"\n=======================================================")
    print(f"🚨 TARS CALLER - EXECUTIVE SENTINEL ENGINE")
    print(f"Caller ID: {CALLER_DISPLAY}")
    print(f"Target: {target_sip_uri}")
    print(f"Sender: {clean_sender}")
    print(f"Subject: {clean_subject}")
    print(f"Voice: British Executive ({VOICE_NAME}, rate={VOICE_RATE})")
    print(f"=======================================================")

    # Load pre-cached static filler assets instantly (0.001s)
    ack_drafting_ulaw = get_or_create_cached_audio("ack_drafting", "On it boss, drafting that now.")
    ack_sending_ulaw = get_or_create_cached_audio("ack_sending", "Sending it right now, boss.")
    farewell_ulaw = get_or_create_cached_audio("farewell", "All done boss! Email sent with your resume attached. Have a great day!")
    beep_ulaw = generate_beep_ulaw(freq=800, duration_sec=0.18)

    # Start synthesizing custom briefing audio in parallel thread
    greeting_holder = [None]
    def _synth_worker():
        greeting_holder[0] = asyncio.run(generate_speech_ulaw(briefing_text, rate=VOICE_RATE, pitch=VOICE_PITCH))
    synth_t = threading.Thread(target=_synth_worker, daemon=True)
    synth_t.start()

    sip_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sip_sock.settimeout(2.0)
    sip_sock.bind(("0.0.0.0", 0))
    local_sip_port = sip_sock.getsockname()[1]

    rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtp_sock.bind(("0.0.0.0", 0))
    local_rtp_port = rtp_sock.getsockname()[1]
    sdp_offer = build_sdp_offer(local_ip, public_ip, local_rtp_port, is_lan=True)

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
        "Content-Type: application/sdp\r\n"
        f"Content-Length: {len(sdp_offer)}\r\n\r\n"
        f"{sdp_offer}"
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
        "Content-Type: application/sdp\r\n"
        f"Content-Length: {len(sdp_offer)}\r\n\r\n"
        f"{sdp_offer}"
    )

    print("🔐 Authenticating with Flexisip server (Early Offer)...")
    sip_sock.sendto(invite2.encode(), (server, server_port))

    ringing_detected = False
    call_answered = False
    callee_sdp = ""
    callee_tag = ""
    routes = []

    resp_addr = None
    ring_start = time.time()
    while time.time() - ring_start < ring_timeout:
        try:
            data, resp_addr = sip_sock.recvfrom(4096)
            msg = data.decode("utf-8", errors="ignore")

            first_line = msg.splitlines()[0] if msg.splitlines() else "EMPTY"

            if "110 Push sent" in msg:
                print("📲 FCM push notification sent to Android phone! Waking up device...")
                ring_start = time.time()  # Give full timeout window from the moment push is transmitted
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
            "Content-Length: 0\r\n\r\n"
        )
        sip_sock.sendto(ack2.encode(), (server, server_port))
        if resp_addr and resp_addr != (server, server_port):
            try:
                sip_sock.sendto(ack2.encode(), resp_addr)
            except Exception:
                pass

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

        # -------------------------------------------------------------
        # SYMMETRIC RTP PRE-LOCK: Lock onto phone's incoming RTP endpoint before playing frame 1
        # Linphone transmits RTP packets immediately upon answering.
        # Locking here prevents playing the initial greeting into a WAN blackhole or causing jitter gaps!
        # -------------------------------------------------------------
        rtp_sock.settimeout(0.05)
        prelock_start = time.time()
        while time.time() - prelock_start < 0.5:
            try:
                data, s_addr = rtp_sock.recvfrom(2048)
                if len(data) >= 12 and s_addr:
                    print(f"🎯 Symmetric RTP pre-locked onto active phone endpoint: {s_addr}")
                    destinations = [s_addr]
                    break
            except Exception:
                pass

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
        # TURN 2: USER DICTATES INSTRUCTIONS (Natural 1.8s Silence Cut, up to 15s)
        # -------------------------------------------------------------
        user_pcm, dtmf_digit = record_user_speech(rtp_sock, max_seconds=15.0, silence_timeout=1.8, player=player)

        # Instant 0ms filler audio: No dead silence!
        if destinations:
            player.play(ack_drafting_ulaw)

        transcript = ""
        if dtmf_digit == "1":
            transcript = "Confirm and send resume"
        elif dtmf_digit == "2":
            transcript = "Cancel, don't send"
        elif len(user_pcm) >= 1500:
            transcript = transcribe_pcm_audio(user_pcm)

        if not transcript:
            # One retry if quiet
            retry_prompt = asyncio.run(generate_speech_ulaw("I'm listening boss, what should I tell them?", rate=VOICE_RATE, pitch=VOICE_PITCH))
            if destinations:
                player.play(retry_prompt)
                player.play(beep_ulaw)
            user_pcm, dtmf_digit = record_user_speech(rtp_sock, max_seconds=10.0, silence_timeout=1.8, player=player)
            transcript = transcribe_pcm_audio(user_pcm) if len(user_pcm) >= 1500 else ""

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
        spoken_confirmation = analysis.get("spoken_confirmation", "Shall I send this now, boss?")
        drafted_body = analysis.get("drafted_body", "")

        # -------------------------------------------------------------
        # TURN 3: VERIFY WITH USER BEFORE SENDING (Supports Corrections!)
        # -------------------------------------------------------------
        if intent == "CANCEL":
            cancel_audio = get_or_create_cached_audio("cancel", "No problem boss, canceled.")
            if destinations:
                player.play(cancel_audio)
            action_summary = "Email canceled as requested"
        else:
            print(f"🗣️ TARS Confirming with User: '{spoken_confirmation}'")
            confirm_q_ulaw = asyncio.run(generate_speech_ulaw(spoken_confirmation, rate=VOICE_RATE, pitch=VOICE_PITCH))
            if destinations:
                player.play(confirm_q_ulaw)
                player.play(beep_ulaw)

            # Listen for confirmation or modification (allow 1.5s natural pause)
            confirm_pcm, confirm_dtmf = record_user_speech(rtp_sock, max_seconds=7.0, silence_timeout=1.5, player=player)
            confirm_transcript = transcribe_pcm_audio(confirm_pcm) if len(confirm_pcm) >= 1500 else ""
            decision, update_text = classify_confirmation_or_correction(confirm_transcript, confirm_dtmf)
            print(f"🗣️ USER CONFIRMATION: '{confirm_transcript}' | Decision: {decision}")

            if decision == "UPDATE":
                print(f"🔄 Boss requested adjustment: '{update_text}' - Updating draft...")
                revised_analysis = parse_user_intent_and_draft(
                    transcript=f"Original: {transcript}. Modification from user: {update_text}",
                    email_subject=clean_subject,
                    email_sender=clean_sender,
                    email_body=clean_reason or body
                )
                drafted_body = revised_analysis.get("drafted_body", drafted_body)
                attach_resume = revised_analysis.get("attach_resume", attach_resume)
                spoken_confirmation = revised_analysis.get("spoken_confirmation", "Got it boss. I updated the email as requested. Should I send it now?")
                print(f"🗣️ TARS Re-confirming: '{spoken_confirmation}'")
                rev_q_ulaw = asyncio.run(generate_speech_ulaw(spoken_confirmation, rate=VOICE_RATE, pitch=VOICE_PITCH))
                if destinations:
                    player.play(rev_q_ulaw)
                    player.play(beep_ulaw)
                rev_pcm, rev_dtmf = record_user_speech(rtp_sock, max_seconds=6.0, silence_timeout=1.2, player=player)
                rev_transcript = transcribe_pcm_audio(rev_pcm) if len(rev_pcm) >= 1500 else ""
                rev_dec, _ = classify_confirmation_or_correction(rev_transcript, rev_dtmf)
                user_confirmed = (rev_dec == "CONFIRM" or "yes" in rev_transcript.lower() or "send" in rev_transcript.lower())
            else:
                user_confirmed = (decision == "CONFIRM")

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
                farewell_cancel = get_or_create_cached_audio("cancel", "No problem boss, canceled.")
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
    elif not call_answered:
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
        if ringing_detected:
            print("🔕 Ringing timed out. CANCEL sent.")
        else:
            print("🔕 Push delivered, but phone did not ring. CANCEL sent.")

        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                alert_txt = (
                    f"⚠️ *TARS Voice Call Missed / Unanswered*\n"
                    f"👤 *Sender:* `{clean_sender}`\n"
                    f"📌 *Subject:* `{clean_subject}`\n"
                    f"📱 *Status:* Call was not answered. Please check Linphone app permissions."
                )
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": alert_txt, "parse_mode": "Markdown"}, timeout=4)
            except Exception:
                pass

    sip_sock.close()
    rtp_sock.close()
    return ringing_detected or call_answered


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
    - Speaks concise briefing (<4s) addressing user as "boss".
    - Two-way confirmation loop verifies draft before sending.
    - Dispatches pre-drafted email in 300ms upon confirmation.
    """
    if not _SIP_CALL_LOCK.acquire(blocking=False):
        print("⚠️ Another SIP call is currently active. Dropping duplicate call request.")
        return False
    try:
        return _trigger_urgent_call_impl(
            subject=subject,
            sender=sender,
            reason=reason,
            email_id=email_id,
            body=body,
            ring_timeout=ring_timeout
        )
    finally:
        _SIP_CALL_LOCK.release()


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



# =====================================================================
# INBOUND AI CALL SENTINEL (YOU CAN CALL TARS TO DICTATE EMAILS!)
# =====================================================================

KNOWN_CONTACTS = {
    "samer": "mohammadsameer.1@gmail.com",
    "sameer": "mohammadsameer.1@gmail.com",
    "bilal": "mohammad.bilal24it@gmail.com",
    "kaizen": "studiokaizen03@gmail.com",
    "webclient": "webclient07@gmail.com",
    "suhail": "mdsuhail.tab.1@gmail.com",
    "tab": "mohammadsameer.1@gmail.com",
}


def resolve_contact_email(name_query: str) -> str:
    """Resolves a dictated name or email to an actual email address using contacts.json and tars_agent."""
    try:
        import tars_agent
        resolved, _ = tars_agent.resolve_recipient_email(name_query)
        if resolved:
            return resolved
    except Exception as e:
        print(f"⚠️ Contact resolver fallback: {e}")

    if not name_query:
        return "mohammadsameer.1@gmail.com"
    clean = name_query.lower().strip()
    for k, v in KNOWN_CONTACTS.items():
        if k in clean:
            return v
    return clean if "@" in clean else "mohammadsameer.1@gmail.com"


def parse_inbound_email_dictation(transcript: str) -> dict:
    """Parses user's spoken command when they call TARS (e.g. 'Mail Samer that I am free Sunday and attach my resume')."""
    if groq_client:
        prompt = f"""You are TARS, executive voice AI assistant speaking on a live phone call with Mohammed Suhail.
Suhail called you and dictated this instruction:
"{transcript}"

Analyze what Suhail wants to send:
1. 'recipient_name': The person or name mentioned (e.g. 'Samer', 'Sameer').
2. 'subject': A professional, concise subject line.
3. 'drafted_body': The full, professional email body signed 'Best regards,\nMohammed Suhail'.
4. 'attach_resume': true if he mentions resume, CV, or job opportunity, else false.
5. 'spoken_confirmation': A crisp, natural sentence TARS speaks back to Suhail addressing him as 'boss' (e.g. "Got it boss. I'll email Samer saying you're available on Sunday, and attach your resume. Should I send it now, boss?").

Respond ONLY with valid JSON:
{{
  "recipient_name": "name",
  "subject": "subject",
  "drafted_body": "body",
  "attach_resume": true or false,
  "spoken_confirmation": "confirmation question addressing Suhail as boss"
}}"""
        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
            try:
                resp = groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                data = json.loads(resp.choices[0].message.content)
                if data and "drafted_body" in data:
                    return data
            except Exception:
                continue

    return {
        "recipient_name": "Samer",
        "subject": "Regarding our conversation",
        "drafted_body": f"Hi Samer,\n\nFollowing up on our conversation: {transcript}.\n\nPlease find my resume attached for your review.\n\nBest regards,\nMohammed Suhail",
        "attach_resume": True,
        "spoken_confirmation": "Got it boss. I'll draft the email to Samer with your resume attached. Should I send it now, boss?"
    }


VOICE_AGENT_SYSTEM_PROMPT = """You are TARS, executive voice AI assistant speaking live on a telephone call with Mohammed Suhail. Always address him naturally as 'boss'.
You have full real-time access to his Gmail via tools (search_emails, get_recent_unread_emails, read_email, create_draft_email, send_email, clean_promotions, archive_emails, trash_emails, etc.).

VIP RECIPIENTS DIRECTORY (ALWAYS USE THESE VERIFIED ADDRESSES):
- Samer / Sameer / Tab: mohammadsameer.1@gmail.com
- Bilal: mohammad.bilal24it@gmail.com
- Kaizen: studiokaizen03@gmail.com
- Web Client: webclient07@gmail.com
- Suhail (Self): mdsuhailtab.1@gmail.com

CRITICAL RECIPIENT RULE:
When Suhail asks to email someone by name (e.g. 'send email to Samer' or 'mail Bilal'), ALWAYS match them to the VIP directory above. NEVER guess or hallucinate an email address. If a contact is not in the directory, search past emails first to find their real address.

CRITICAL SPOKEN VOICE RULES:
1. Spoken Audio Only: Output PURE SPOKEN ENGLISH. NEVER output markdown symbols (no asterisks **, no bold, no bullet points, no headers, no emojis, no URLs).
2. Strictly 1 to 3 Sentences: Keep all spoken responses strictly between 1 and 3 concise sentences so Suhail can digest it easily over the phone.
3. Natural Punctuation & Contractions: Use spoken punctuation (commas for breathing pauses) and natural contractions (such as "I've", "it's", "you're", "we've", "don't").
4. Live Gmail RAG: When Suhail asks if he received any emails (e.g. from Samer, unread emails, interview updates), call search_emails or get_recent_unread_emails, extract key info (who, when, subject, summary), and report it clearly.
5. Next Steps: Always conclude by asking the natural next action (e.g. 'Would you like me to read the full message, or draft a reply with your resume attached?').
6. Dictating & Sending Emails: When Suhail asks to draft or send an email:
   - Always call create_draft_email first to securely create the draft in Gmail.
   - In your spoken response, clearly read back the recipient address so Suhail can verify the exact spelling (e.g. "I've drafted that to s-a-m-e-e-r at gmail dot com. Shall I send that now, boss?").
   - If Suhail corrects the spelling or email address on the next turn, immediately update the draft and confirm.
7. Confirming Send: If Suhail confirms ('yes', 'send it', 'do it'), call send_email or send_draft immediately, and confirm: 'Sent boss! Anything else I can help with?'.
8. Farewell: If Suhail says 'that is all', 'thanks', 'goodbye', or 'bye', reply with a warm closing like 'Always at your service boss, have a great day!' and append '[HANGUP]'.
"""


def execute_voice_rag_turn(user_query: str, history: list = None) -> tuple[str, bool]:
    """
    Executes an autonomous multi-turn voice RAG turn with live tool calling over Gmail.
    Returns (spoken_text, should_hangup).
    """
    if history is None:
        history = []
    
    clean_q = user_query.lower().strip()
    if any(farewell in clean_q for farewell in ["goodbye", "bye", "that's all", "thats all", "nothing else", "no thanks", "all good", "i'm good", "hang up", "end call"]):
        return "Always at your service boss. Have a wonderful day!", True

    # Sliding window memory: retain last 10 messages so unlimited conversational turns stay instant without token overflow
    trimmed_history = history[-10:] if len(history) > 10 else history
    messages = [{"role": "system", "content": VOICE_AGENT_SYSTEM_PROMPT}] + trimmed_history + [{"role": "user", "content": user_query}]
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    voice_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    import tars_agent

    for model in voice_models:
        try:
            curr_messages = list(messages)
            for step in range(3):
                payload = {
                    "model": model,
                    "messages": curr_messages,
                    "tools": tars_agent.TARS_TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.3
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=12)
                if resp.status_code != 200:
                    break
                
                resp_json = resp.json()
                choice = resp_json.get("choices", [{}])[0].get("message", {})
                tool_calls = choice.get("tool_calls", [])
                
                if not tool_calls:
                    content = choice.get("content", "").strip()
                    # Strip any markdown or special formatting
                    clean_spoken = re.sub(r'[*_#`~]', '', content)
                    clean_spoken = re.sub(r'\[.*?\]\(.*?\)', '', clean_spoken)
                    clean_spoken = " ".join(clean_spoken.split())
                    should_hangup = "[HANGUP]" in content or "[hangup]" in content.lower()
                    clean_spoken = clean_spoken.replace("[HANGUP]", "").replace("[hangup]", "").strip()
                    return clean_spoken, should_hangup

                curr_messages.append(choice)
                for tc in tool_calls:
                    fn_name = tc.get("function", {}).get("name")
                    fn_args_raw = tc.get("function", {}).get("arguments", "{}")
                    try:
                        fn_args = json.loads(fn_args_raw)
                    except Exception:
                        fn_args = {}
                    
                    print(f"Executing voice tool: {fn_name}({fn_args})")
                    handler = tars_agent.TOOL_MAP.get(fn_name)
                    if handler:
                        tool_res = handler(**fn_args)
                    else:
                        tool_res = {"error": f"Unknown tool {fn_name}"}
                    
                    curr_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", "call_0"),
                        "name": fn_name,
                        "content": json.dumps(tool_res)
                    })
        except Exception as e:
            print(f"Model {model} voice exception: {e}")
            continue

    return "I ran into a momentary hitch accessing your inbox boss. Could you repeat that?", False


def handle_inbound_voice_session(rtp_sock, destinations, call_id, from_tag, to_tag, contact_uri, caller_ip, caller_port, sip_sock, local_ip, local_port, routes=None, tx_srtp=None, rx_srtp=None):
    """
    Full Autonomous Conversational Voice RAG Engine (Telegram Agent on Phone Call):
    - Greets boss: 'Hello boss, TARS online. How can I help you today?'
    - Multi-turn conversational loop:
        1. Records user's speech via mic with 1.8s silence detection (up to 15s).
        2. Transcribes with Groq Whisper.
        3. If quiet on Turn 1, prompts once. If farewell ('that's all', 'bye'), concludes warmly and hangs up.
        4. Plays fast 0ms acknowledgment filler ('Checking that for you now, boss.') so there is no dead silence.
        5. Executes live Gmail tools via execute_voice_rag_turn (search_emails, read_email, get_recent_unread_emails, clean_promotions, create_draft_email, send_email, etc.).
        6. Converts answer to natural spoken audio (en-GB-RyanNeural -1Hz -2% rate).
        7. Plays spoken response over RTP with continuous wall-clock timestamps (solid green bars!).
        8. If the turn had [HANGUP], ends the call; otherwise listens for boss's next question or command!
    """
    def is_current_call():
        with _active_inbound_lock:
            return _active_inbound_call_id == call_id

    # Pre-lock symmetric RTP: wait up to 0.8s for the phone's audio channel to open upon pickup
    rtp_sock.settimeout(0.08)
    prelock_start = time.time()
    while time.time() - prelock_start < 0.8:
        if not is_current_call():
            rtp_sock.close()
            return
        try:
            data, s_addr = rtp_sock.recvfrom(2048)
            if handle_stun_packet(data, s_addr, rtp_sock):
                continue
            if len(data) >= 12 and s_addr:
                print(f"🎯 Symmetric RTP pre-locked onto active inbound endpoint: {s_addr}")
                destinations = [s_addr]
                break
        except Exception:
            pass

    if not is_current_call():
        rtp_sock.close()
        return

    player = RTPPlayer(rtp_sock, destinations, srtp_session=tx_srtp)
    beep_ulaw = generate_beep_ulaw(freq=800, duration_sec=0.18)
    inbound_greeting = get_or_create_cached_audio("inbound_greeting", "Hello boss, TARS online. How can I help you today?")
    ack_checking_ulaw = get_or_create_cached_audio("ack_checking", "Checking that for you now, boss.")
    farewell_ulaw = get_or_create_cached_audio("farewell", "Always at your service boss. Have a wonderful day!")

    # 1. Greet Boss
    print("🗣️ Inbound TARS: Greeting boss with live conversational RAG agent...")
    # Send 300ms comfort silence (15 frames) to warm up phone DAC and lock jitter buffer to green
    silence_20ms = b"\xff" * 160
    player.play(silence_20ms * 15)
    player.play(inbound_greeting)
    player.play(beep_ulaw)

    conversation_history = []
    turn = 0
    all_transcripts = []
    consecutive_silence = 0

    while is_current_call():
        turn += 1
        print(f"\n--- INBOUND VOICE TURN {turn} ---")

        # Record boss's speech (up to 30s speaking time, 1.8s silence pause detection)
        user_pcm, dtmf_digit = record_user_speech(rtp_sock, max_seconds=30.0, silence_timeout=1.8, player=player, srtp_session=rx_srtp)
        if not is_current_call():
            break

        transcript = transcribe_pcm_audio(user_pcm) if len(user_pcm) >= 1500 else ""
        print(f"🗣️ BOSS: '{transcript}'")

        if not transcript:
            consecutive_silence += 1
            if consecutive_silence < 3:
                prompt_text = "I'm listening boss, what would you like me to check?" if consecutive_silence == 1 else "I'm still here boss, let me know if you need anything."
                retry_prompt = asyncio.run(generate_speech_ulaw(prompt_text, rate=VOICE_RATE, pitch=VOICE_PITCH))
                if is_current_call():
                    player.play(retry_prompt)
                    player.play(beep_ulaw)
                continue
            else:
                # Conclude politely after 3 consecutive silent prompts
                print("⏳ Prolonged silence detected - concluding call.")
                break

        # Reset silence counter
        consecutive_silence = 0
        all_transcripts.append(transcript)

        # Check if user says goodbye / farewell / hangup
        clean_q = transcript.lower().strip()
        if any(w in clean_q for w in ["goodbye", "bye", "that's all", "thats all", "nothing else", "no thanks", "all good", "i'm good", "hang up", "end call"]):
            player.play(farewell_ulaw)
            break

        # Instant acoustic filler while RAG runs (0ms perceived latency)
        player.play(ack_checking_ulaw)

        # Execute live RAG over Gmail
        spoken_response, should_hangup = execute_voice_rag_turn(transcript, conversation_history)
        print(f"🤖 TARS: '{spoken_response}' (hangup={should_hangup})")

        # Save to conversation memory
        conversation_history.append({"role": "user", "content": transcript})
        conversation_history.append({"role": "assistant", "content": spoken_response})

        # Synthesize & play response
        speech_ulaw = asyncio.run(generate_speech_ulaw(spoken_response, rate=VOICE_RATE, pitch=VOICE_PITCH))
        if not is_current_call():
            break

        player.play(speech_ulaw)
        player.play(beep_ulaw)

        if should_hangup:
            break

    # Send summary of call to Telegram bot
    if all_transcripts:
        send_telegram_summary(
            transcript=" | ".join(all_transcripts),
            action_taken=f"Inbound voice session completed ({turn} turns)",
            sender="Mohammed Suhail (Inbound Voice Call)",
            subject="Live Voice RAG Consultation"
        )

    # Conclude call
    player.stop_silence_stream()
    time.sleep(0.5)
    _send_inbound_bye(sip_sock, contact_uri, local_ip, local_port, to_tag, from_tag, call_id, caller_ip, caller_port, routes)
    rtp_sock.close()
    print("📴 Inbound call ended cleanly.")


def _send_inbound_bye(sip_sock, contact_uri, local_ip, local_port, to_tag, from_tag, call_id, caller_ip, caller_port, routes=None):
    route_hdr = ""
    if routes:
        route_hdr = "Route: " + ", ".join(list(reversed(routes))) + "\r\n"
    bye = (
        f"BYE {contact_uri} SIP/2.0\r\n"
        f"Via: SIP/2.0/UDP {local_ip}:{local_port};branch=z9hG4bK{uuid.uuid4().hex[:20]};rport\r\n"
        + route_hdr +
        f'From: <sip:{LINPHONE_USERNAME}@{LINPHONE_DOMAIN}>;tag={to_tag}\r\n'
        f"To: <{contact_uri}>;tag={from_tag}\r\n"
        f"Call-ID: {call_id}\r\n"
        f"CSeq: 3 BYE\r\n"
        "Max-Forwards: 70\r\n"
        "Content-Length: 0\r\n\r\n"
    )
    try:
        sip_sock.sendto(bye.encode(), (caller_ip, caller_port))
    except Exception:
        pass


def run_inbound_sip_server(port=5060):
    """
    Persistent Linphone SIP Cloud & LAN Sentinel:
    - Registers suhail_tars with sip.linphone.org on startup.
    - Sends 280s keep-alive refresh so phone can call from anywhere (Wi-Fi or cellular).
    - Accepts calls to suhail_tars, briefs Suhail, takes voice command, and sends email.
    """
    global _active_inbound_call_id
    server = LINPHONE_DOMAIN
    server_port = 5060
    username = LINPHONE_USERNAME
    password = LINPHONE_PASSWORD
    initial_pub_ip = get_public_ip(force_refresh=True)
    initial_loc_ip = get_local_ip()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        print(f"🎧 TARS Inbound SIP Server bound on {initial_loc_ip}:{port} (Public IP: {initial_pub_ip})")
    except Exception as e:
        print(f"⚠️ Could not bind inbound SIP listener on port {port}: {e}")
        return

    reg_state = {
        "call_id": uuid.uuid4().hex + "@" + initial_pub_ip,
        "from_tag": uuid.uuid4().hex[:8],
        "cseq": 0,
        "registered": False,
        "last_reg_sent": 0,
        "last_success": 0,
        "public_ip": initial_pub_ip,
        "local_ip": initial_loc_ip
    }

    def _send_initial_register():
        curr_pub_ip = get_public_ip(force_refresh=True)
        curr_loc_ip = get_local_ip()
        if curr_pub_ip != reg_state.get("public_ip"):
            print(f"🌐 Dynamic Public IP change detected: {reg_state.get('public_ip')} -> {curr_pub_ip}")
            reg_state["public_ip"] = curr_pub_ip
            reg_state["call_id"] = uuid.uuid4().hex + "@" + curr_pub_ip
            reg_state["cseq"] = 0
            reg_state["registered"] = False
        reg_state["local_ip"] = curr_loc_ip

        reg_state["cseq"] += 1
        branch = "z9hG4bK" + uuid.uuid4().hex[:20]
        cur_ip = reg_state["public_ip"]
        reg_packet = (
            f"REGISTER sip:{server} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {cur_ip}:{port};branch={branch};rport\r\n"
            f"From: <sip:{username}@{server}>;tag={reg_state['from_tag']}\r\n"
            f"To: <sip:{username}@{server}>\r\n"
            f"Call-ID: {reg_state['call_id']}\r\n"
            f"CSeq: {reg_state['cseq']} REGISTER\r\n"
            f"Contact: <sip:{username}@{cur_ip}:{port};transport=UDP>;expires=600\r\n"
            "Max-Forwards: 70\r\n"
            f"User-Agent: {CALLER_DISPLAY}\r\n"
            "Content-Length: 0\r\n\r\n"
        )
        try:
            sock.sendto(reg_packet.encode(), (server, server_port))
            reg_state["last_reg_sent"] = time.time()
            print(f"📡 Sent initial REGISTER request (CSeq: {reg_state['cseq']}) for {username}@{server} on {cur_ip}...")
        except Exception as se:
            print(f"⚠️ Failed to send REGISTER: {se}")

    # Registration & NAT Keep-Alive Thread (RFC 5626)
    def _reg_keeper():
        time.sleep(2)
        while True:
            try:
                # 1. Send double-CRLF NAT keepalive ping every 25 seconds
                sock.sendto(b"\r\n\r\n", (server, server_port))

                # 2. Check if we need to refresh registration (every 180s) or retry failed registration (>30s)
                now = time.time()
                needs_refresh = (now - reg_state.get("last_reg_sent", 0) >= 180) or (
                    not reg_state.get("registered", False) and (now - reg_state.get("last_reg_sent", 0) >= 30)
                )
                if needs_refresh:
                    print("🔄 Refreshing SIP registration with Linphone Flexisip...")
                    _send_initial_register()
            except Exception as re_err:
                print(f"⚠️ Registration keepalive error: {re_err}")
            time.sleep(25)

    # Send initial registration before loop
    _send_initial_register()

    reg_thread = threading.Thread(target=_reg_keeper, daemon=True, name="SIP-Reg-Keeper")
    reg_thread.start()

    print(f"📡 Registering as sip:{username}@{server} on port {port} (NAT keepalive active)...")
    print(f"👉 Once registered, you can dial '{username}' from Linphone on your phone anytime!\n")

    sock.settimeout(None)
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            if not data or not data.strip():
                continue
            msg = data.decode("utf-8", errors="ignore")
            if not msg.strip():
                continue
            first_line = msg.splitlines()[0] if msg.splitlines() else ""

            # --- SIP Authentication Challenge Handler (401 / 407) ---
            if any(code in first_line for code in ("401", "407")) and ("REGISTER" in msg or "WWW-Authenticate" in msg or "Proxy-Authenticate" in msg):
                auth_header_name = "Proxy-Authenticate" if "407" in msg else "WWW-Authenticate"
                auth_req_name = "Proxy-Authorization" if "407" in msg else "Authorization"
                challenge = parse_auth_challenge(msg, auth_header_name)
                if challenge and challenge.get("nonce"):
                    reg_state["cseq"] += 1
                    branch2 = "z9hG4bK" + uuid.uuid4().hex[:20]
                    cur_ip = reg_state.get("public_ip", initial_pub_ip)
                    auth_val = compute_digest(
                        username=username,
                        password=password,
                        realm=challenge["realm"],
                        nonce=challenge["nonce"],
                        method="REGISTER",
                        uri=f"sip:{server}",
                        qop=challenge.get("qop"),
                        opaque=challenge.get("opaque")
                    )
                    reg2 = (
                        f"REGISTER sip:{server} SIP/2.0\r\n"
                        f"Via: SIP/2.0/UDP {cur_ip}:{port};branch={branch2};rport\r\n"
                        f"From: <sip:{username}@{server}>;tag={reg_state['from_tag']}\r\n"
                        f"To: <sip:{username}@{server}>\r\n"
                        f"Call-ID: {reg_state['call_id']}\r\n"
                        f"CSeq: {reg_state['cseq']} REGISTER\r\n"
                        f"Contact: <sip:{username}@{cur_ip}:{port};transport=UDP>;expires=600\r\n"
                        f"{auth_req_name}: {auth_val}\r\n"
                        "Max-Forwards: 70\r\n"
                        f"User-Agent: {CALLER_DISPLAY}\r\n"
                        "Content-Length: 0\r\n\r\n"
                    )
                    sock.sendto(reg2.encode(), (server, server_port))
                    print(f"📡 Responded to 401 challenge with authenticated REGISTER (CSeq: {reg_state['cseq']})")
                continue

            # --- SIP Registration Successful (200 OK) ---
            elif ("200 Registration successful" in msg) or ("200 OK" in first_line and "REGISTER" in msg):
                first_success = not reg_state.get("registered", False)
                reg_state["registered"] = True
                reg_state["last_success"] = time.time()
                print(f"✅ Linphone Registration Confirmed: 200 OK for {username}@{server}!")
                print(f"👉 Ready for inbound calls! Dial '{username}' from Linphone app.\n")
                if first_success:
                    send_telegram_status(
                        f"🟢 *TARS Voice Sentinel is ONLINE*\n"
                        f"📡 Registered: `{username}@{server}`\n"
                        f"🌐 Public IP: `{reg_state.get('public_ip')}`\n"
                        f"📞 Ready for inbound phone calls anytime, boss!"
                    )
                continue
            first_line = msg.splitlines()[0] if msg.splitlines() else ""

            if first_line.startswith("INVITE"):
                print(f"\n=======================================================")
                print(f"📞 INBOUND CALL RECEIVED FROM {addr[0]}:{addr[1]}!")
                print(f"=======================================================")
                call_id_m = re.search(r'Call-ID:\s*([^\r\n]+)', msg, re.IGNORECASE)
                call_id = call_id_m.group(1).strip() if call_id_m else ""
                with _active_inbound_lock:
                    _active_inbound_call_id = call_id
                from_m = re.search(r'From:\s*([^\r\n]+)', msg, re.IGNORECASE)
                from_hdr = from_m.group(1).strip() if from_m else ""
                from_tag_m = re.search(r'tag=([^\r\n;]+)', from_hdr)
                from_tag = from_tag_m.group(1) if from_tag_m else ""
                to_m = re.search(r'To:\s*([^\r\n]+)', msg, re.IGNORECASE)
                to_hdr = to_m.group(1).strip() if to_m else f"<sip:{username}@{server}>"
                via_lines = re.findall(r'(Via:\s*[^\r\n]+)', msg, re.IGNORECASE)
                via_headers_str = "".join(f"{vl.strip()}\r\n" for vl in via_lines)
                cseq_m = re.search(r'CSeq:\s*([^\r\n]+)', msg, re.IGNORECASE)
                cseq = cseq_m.group(1).strip() if cseq_m else "1 INVITE"
                contact_m = re.search(r'Contact:\s*<([^>]+)>', msg, re.IGNORECASE)
                contact_uri = contact_m.group(1).strip() if contact_m else f"sip:{username}@{server}"

                record_routes = re.findall(r'Record-Route:\s*([^\r\n]+)', msg, re.IGNORECASE)
                route_headers_str = "".join(f"Record-Route: {rr}\r\n" for rr in record_routes)

                to_tag = uuid.uuid4().hex[:8]
                final_to_hdr = to_hdr if "tag=" in to_hdr else f"{to_hdr};tag={to_tag}"

                # Send standard-compliant 100 Trying immediately
                resp_100 = (
                    "SIP/2.0 100 Trying\r\n"
                    f"{via_headers_str}"
                    f"From: {from_hdr}\r\n"
                    f"To: {to_hdr}\r\n"
                    f"Call-ID: {call_id}\r\n"
                    f"CSeq: {cseq}\r\n"
                    "Content-Length: 0\r\n\r\n"
                )
                sock.sendto(resp_100.encode(), addr)

                sdp_part = msg.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in msg else ""
                print(f"📥 INBOUND SDP OFFER:\n{sdp_part.strip()}\n")
                destinations = select_best_rtp_destination(sdp_part)
                if not destinations:
                    destinations = [(addr[0], 7078)]

                cur_pub_ip = reg_state.get("public_ip", initial_pub_ip)
                cur_loc_ip = reg_state.get("local_ip", initial_loc_ip)
                is_on_lan = any(ip.startswith(("192.168.", "10.", "172.")) for ip, _ in destinations)
                advertised_ip = cur_loc_ip if is_on_lan else cur_pub_ip

                rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                rtp_sock.bind(("0.0.0.0", 0))
                local_rtp_port = rtp_sock.getsockname()[1]

                sdp_answer, tx_srtp, rx_srtp = build_sdp_answer(sdp_part, cur_loc_ip, cur_pub_ip, local_rtp_port, is_lan=is_on_lan)
                print(f"📤 200 OK SDP ANSWER:\n{sdp_answer.strip()}\n")

                resp_200 = (
                    "SIP/2.0 200 OK\r\n"
                    f"{via_headers_str}"
                    f"From: {from_hdr}\r\n"
                    f"To: {final_to_hdr}\r\n"
                    f"Call-ID: {call_id}\r\n"
                    f"CSeq: {cseq}\r\n"
                    f"{route_headers_str}"
                    f"Contact: <sip:{username}@{cur_pub_ip}:{port};transport=UDP>\r\n"
                    f"User-Agent: {CALLER_DISPLAY}\r\n"
                    "Content-Type: application/sdp\r\n"
                    f"Content-Length: {len(sdp_answer)}\r\n\r\n"
                    f"{sdp_answer}"
                )

                sock.sendto(resp_200.encode(), addr)
                print(f"🎉 Answered inbound call with 200 OK! Advertised: {advertised_ip}:{local_rtp_port}")

                t = threading.Thread(
                    target=handle_inbound_voice_session,
                    args=(rtp_sock, destinations, call_id, from_tag, to_tag, contact_uri, addr[0], addr[1], sock, advertised_ip, port, record_routes, tx_srtp, rx_srtp),
                    daemon=True,
                    name="TARS-Inbound-Call"
                )
                t.start()

            elif first_line.startswith("ACK"):
                print(f"🤝 Inbound SIP call ACK confirmed from {addr[0]}:{addr[1]} - Call dialog active!")

            elif first_line.startswith("OPTIONS"):
                via_lines = re.findall(r'(Via:\s*[^\r\n]+)', msg, re.IGNORECASE)
                v_str = "".join(f"{vl.strip()}\r\n" for vl in via_lines)
                f_m = re.search(r'(From:\s*[^\r\n]+)', msg, re.IGNORECASE)
                t_m = re.search(r'(To:\s*[^\r\n]+)', msg, re.IGNORECASE)
                c_m = re.search(r'(Call-ID:\s*[^\r\n]+)', msg, re.IGNORECASE)
                cs_m = re.search(r'(CSeq:\s*[^\r\n]+)', msg, re.IGNORECASE)
                resp_options = (
                    "SIP/2.0 200 OK\r\n"
                    f"{v_str}"
                    + (f"{f_m.group(1)}\r\n" if f_m else "")
                    + (f"{t_m.group(1)}\r\n" if t_m else "")
                    + (f"{c_m.group(1)}\r\n" if c_m else "")
                    + (f"{cs_m.group(1)}\r\n" if cs_m else "")
                    + "Allow: INVITE, ACK, CANCEL, BYE, OPTIONS\r\n"
                    + "Content-Length: 0\r\n\r\n"
                )
                sock.sendto(resp_options.encode(), addr)

            elif first_line.startswith("BYE") or first_line.startswith("CANCEL"):
                bye_call_id_m = re.search(r'Call-ID:\s*([^\r\n]+)', msg, re.IGNORECASE)
                bye_call_id = bye_call_id_m.group(1).strip() if bye_call_id_m else ""
                with _active_inbound_lock:
                    if _active_inbound_call_id == bye_call_id:
                        _active_inbound_call_id = None
                via_lines = re.findall(r'(Via:\s*[^\r\n]+)', msg, re.IGNORECASE)
                v_str = "".join(f"{vl.strip()}\r\n" for vl in via_lines)
                f_m = re.search(r'(From:\s*[^\r\n]+)', msg, re.IGNORECASE)
                t_m = re.search(r'(To:\s*[^\r\n]+)', msg, re.IGNORECASE)
                c_m = re.search(r'(Call-ID:\s*[^\r\n]+)', msg, re.IGNORECASE)
                cs_m = re.search(r'(CSeq:\s*[^\r\n]+)', msg, re.IGNORECASE)
                resp_bye = (
                    "SIP/2.0 200 OK\r\n"
                    f"{v_str}"
                    + (f"{f_m.group(1)}\r\n" if f_m else "")
                    + (f"{t_m.group(1)}\r\n" if t_m else "")
                    + (f"{c_m.group(1)}\r\n" if c_m else "")
                    + (f"{cs_m.group(1)}\r\n" if cs_m else "")
                    + "Content-Length: 0\r\n\r\n"
                )
                sock.sendto(resp_bye.encode(), addr)


        except ConnectionResetError:
            continue
        except Exception as e:
            time.sleep(0.05)


def start_inbound_sip_listener_async(port=5060):
    """Starts the inbound SIP listener in a daemon background thread."""
    t = threading.Thread(target=run_inbound_sip_server, kwargs={"port": port}, daemon=True, name="TARS-Inbound-Listener")
    t.start()
    return t



if __name__ == "__main__":
    trigger_urgent_call(
        subject="Meeting and Resume Request",
        sender="Mohammed Samer uddin ahmed <mdsameeruddintab.1@gmail.com>",
        reason="Samer requested your resume and a meeting regarding Data Science"
    )

