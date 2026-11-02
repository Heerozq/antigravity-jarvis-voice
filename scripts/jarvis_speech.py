import sys
import os
import json
import re
import hashlib
import urllib.request
import urllib.error
import subprocess
import tempfile
import time
import glob

SETTINGS_FILE = r"C:\Users\Admin\.gemini\config\jarvis_settings.json"
TEMP_DIR = tempfile.gettempdir()
LOG_FILE = os.path.join(TEMP_DIR, "antigravity_jarvis.log")
RAW_AUDIO_PATH = os.path.join(TEMP_DIR, "antigravity_jarvis_raw.mp3")
READY_AUDIO_PATH = os.path.join(TEMP_DIR, "antigravity_jarvis_ready.wav")
CACHE_FILE = os.path.join(TEMP_DIR, "antigravity_jarvis_last_hash.txt")
TRANSCRIPT_TRACK_FILE = os.path.join(TEMP_DIR, "antigravity_jarvis_last_transcript.txt")

PYTHON_BACKEND_PATH = r"D:\VoiceStudio\project\.venv\Scripts\python.exe"
PROJECT_DIR = r"D:\VoiceStudio\project"
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPLAY_PATH = r"C:\ffmpeg\bin\ffplay.exe"

def load_settings():
    defaults = {"enabled": True, "speed": 1.2, "voice": "Atul Kapoor"}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def ensure_licenses_accepted():
    """Ensure OmniVoice and Higgs-Audio tokenizer licenses are recorded as accepted."""
    try:
        script = """
import sys
sys.path.insert(0, r"D:\\VoiceStudio\\project\\backend")
from services import model_acceptance
licenses = [
    ('k2-fsa/OmniVoice', 'v2:d938ea928581624d5732507057d8530320f638ac61426165cbd5abe67be5c9bc'),
    ('eustlb/higgs-audio-v2-tokenizer', 'v2:6b442e435fd392f7726e7c44a30da71bba23adecaabe4c8da725cb30579ecff1')
]
for repo, fp in licenses:
    try:
        model_acceptance.accept(repo, fp)
    except Exception:
        pass
"""
        subprocess.run(
            [PYTHON_BACKEND_PATH, "-c", script],
            cwd=PROJECT_DIR,
            capture_output=True,
            timeout=10,
            check=False
        )
        log("Verified model licenses accepted")
    except Exception as e:
        log(f"License acceptance check error: {e}")

def ensure_backend_running():
    try:
        with urllib.request.urlopen("http://127.0.0.1:3900/health", timeout=1):
            return True
    except Exception:
        pass

    if os.path.exists(PYTHON_BACKEND_PATH):
        log("Auto-starting headless VoiceStudio Python backend...")
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            [
                PYTHON_BACKEND_PATH, "-m", "uvicorn", "main:app",
                "--app-dir", "backend", "--host", "127.0.0.1", "--port", "3900"
            ],
            cwd=PROJECT_DIR,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True
        )
        for _ in range(16):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:3900/health", timeout=1):
                    log("Headless backend is now ready!")
                    ensure_licenses_accepted()
                    return True
            except Exception:
                pass
    return False

def clean_text_for_speech(text):
    if not text:
        return ""
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove markdown links, keep text label
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove tables (lines starting or ending with |)
    text = re.sub(r'^\s*\|.*\|.*$', '', text, flags=re.MULTILINE)
    # Remove header markings
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    # Remove blockquotes
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Remove bold / italic
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)
    # Remove inline backticks
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove bullet markers (- or * or numbered list)
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove excessive horizontal rules
    text = re.sub(r'^\s*[-=_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove emojis & unusual unicode symbols to keep speech clear
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Collapse multiple whitespaces/newlines
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    
    # Ensure clean trailing sentence closure
    if text and not text[-1] in '.!?':
        text += '.'
        
    return text

def split_text_into_chunks(text, max_chunk=3800):
    if len(text) <= max_chunk:
        return [text]
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_chunk:
            current += (" " if current else "") + s
        else:
            if current:
                chunks.append(current)
            current = s
    if current:
        chunks.append(current)
    return chunks

def find_latest_transcript():
    """Find the most recently modified transcript file."""
    if os.path.exists(TRANSCRIPT_TRACK_FILE):
        try:
            with open(TRANSCRIPT_TRACK_FILE, "r", encoding="utf-8") as f:
                path = f.read().strip()
                if path and os.path.exists(path):
                    return path
        except Exception:
            pass

    pattern = r"C:\Users\Admin\.gemini\antigravity\brain\*\.system_generated\logs\transcript.jsonl"
    matches = glob.glob(pattern)
    if matches:
        matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return matches[0]
    return None

def extract_latest_response(transcript_path):
    """Extract the latest assistant PLANNER_RESPONSE from the transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        return ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        for entry in reversed(lines):
            if entry.get("type") == "PLANNER_RESPONSE" and entry.get("content"):
                return entry["content"]
    except Exception as e:
        log(f"Error reading transcript: {e}")
    return ""

def play_audio(speed):
    """Bake speed adjustment and silence tail, then play with ffplay."""
    if not os.path.exists(FFPLAY_PATH):
        log("ffplay not found")
        return False

    # Stop any currently active playback
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe"], capture_output=True)
    except Exception:
        pass

    if os.path.exists(RAW_AUDIO_PATH) and os.path.exists(FFMPEG_PATH):
        af_filter = f"atempo={speed},apad=pad_dur=1.5"
        log(f"Baking audio via ffmpeg: {af_filter}")
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", RAW_AUDIO_PATH,
            "-af", af_filter,
            READY_AUDIO_PATH
        ], capture_output=True, check=False)

        log(f"Playing baked audio with ffplay at {speed}x")
        subprocess.run([
            FFPLAY_PATH, "-nodisp", "-autoexit", "-loglevel", "quiet",
            READY_AUDIO_PATH
        ], check=False)
        log("Playback finished successfully")
        return True
    elif os.path.exists(READY_AUDIO_PATH):
        subprocess.run([
            FFPLAY_PATH, "-nodisp", "-autoexit", "-loglevel", "quiet",
            READY_AUDIO_PATH
        ], check=False)
        return True
    return False

def synthesize_speech(cleaned_speech, voice, speed):
    """Call VoiceStudio backend to generate raw audio, then play."""
    ensure_backend_running()

    log(f"Synthesizing {len(cleaned_speech)} chars: {cleaned_speech[:60]}...")
    api_url = "http://127.0.0.1:3900/v1/audio/speech"
    chunks = split_text_into_chunks(cleaned_speech)
    combined_audio = b""

    for i, chunk in enumerate(chunks):
        log(f"Sending chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
        data = {
            "model": "omnivoice",
            "voice": voice,
            "input": chunk,
            "speed": 1.0  # Preserve native baritone timbre; speed adjusted via atempo
        }

        retried = False
        while True:
            try:
                req = urllib.request.Request(
                    api_url,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(data).encode("utf-8")
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    chunk_audio = resp.read()
                    combined_audio += chunk_audio
                    log(f"Chunk {i+1} received: {len(chunk_audio)} bytes")
                    break
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                log(f"HTTP Error {e.code}: {err_body}")
                if e.code == 403 and "model_licence_required" in err_body and not retried:
                    log("Auto-accepting model licenses and retrying...")
                    ensure_licenses_accepted()
                    retried = True
                    time.sleep(1)
                    continue
                return False
            except Exception as e:
                log(f"TTS synthesis network error: {e}")
                return False

    if combined_audio:
        with open(RAW_AUDIO_PATH, "wb") as f:
            f.write(combined_audio)
        return True
    return False

def replay_last():
    log("Replay requested")
    settings = load_settings()
    speed = float(settings.get("speed", 1.2))
    voice = settings.get("voice", "Atul Kapoor")
    log(f"Replay parameters: speed={speed}x, voice={voice}")

    transcript_path = find_latest_transcript()
    latest_response = extract_latest_response(transcript_path)
    cleaned_speech = clean_text_for_speech(latest_response)

    if cleaned_speech and len(cleaned_speech) >= 3:
        raw_hash = hashlib.sha256(cleaned_speech.encode("utf-8")).hexdigest()
        
        # Check if RAW_AUDIO_PATH already contains the audio for this latest response
        last_recorded_hash = ""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    last_recorded_hash = f.read().strip().split("_")[0]
            except Exception:
                pass

        if os.path.exists(RAW_AUDIO_PATH) and last_recorded_hash == raw_hash:
            log("Replay: RAW_AUDIO_PATH matches latest response. Re-baking at current speed.")
            play_audio(speed)
            return

        log("Replay: RAW_AUDIO_PATH is stale or missing. Re-synthesizing latest response...")
        if synthesize_speech(cleaned_speech, voice, speed):
            # Record hash
            try:
                with open(CACHE_FILE, "w") as f:
                    f.write(f"{raw_hash}_{speed}_{voice}")
            except Exception:
                pass
            play_audio(speed)
            return

    # Fallback to playing whatever audio exists
    if os.path.exists(RAW_AUDIO_PATH) or os.path.exists(READY_AUDIO_PATH):
        log("Replay fallback: playing existing audio buffer")
        play_audio(speed)
    else:
        log("Replay: No audio available to play")

def main():
    if "--replay" in sys.argv:
        replay_last()
        print("{}")
        return

    settings = load_settings()
    if not settings.get("enabled", True):
        log("J.A.R.V.I.S. speech is muted in settings")
        print("{}")
        return

    speed = float(settings.get("speed", 1.2))
    voice = settings.get("voice", "Atul Kapoor")

    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception as e:
        log(f"Error parsing stdin: {e}")
        payload = {}

    transcript_path = payload.get("transcriptPath")
    if transcript_path and os.path.exists(transcript_path):
        try:
            with open(TRANSCRIPT_TRACK_FILE, "w", encoding="utf-8") as f:
                f.write(transcript_path)
        except Exception:
            pass
    else:
        transcript_path = find_latest_transcript()

    if not transcript_path or not os.path.exists(transcript_path):
        log(f"Transcript not found: {transcript_path}")
        print("{}")
        return

    response_text = extract_latest_response(transcript_path)
    cleaned_speech = clean_text_for_speech(response_text)
    if not cleaned_speech or len(cleaned_speech) < 3:
        log("Cleaned speech empty or too short")
        print("{}")
        return

    # Check deduplication
    raw_hash = hashlib.sha256(cleaned_speech.encode("utf-8")).hexdigest()
    full_hash = f"{raw_hash}_{speed}_{voice}"

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                if f.read().strip() == full_hash:
                    log("Message already spoken (deduplication hit)")
                    print("{}")
                    return
        except Exception:
            pass

    log(f"Hook invoked (speed={speed}, voice={voice})")

    # Synthesize speech
    if synthesize_speech(cleaned_speech, voice, speed):
        # Save cache hash ONLY after successful synthesis
        try:
            with open(CACHE_FILE, "w") as f:
                f.write(full_hash)
        except Exception:
            pass
        play_audio(speed)

    print("{}")

if __name__ == "__main__":
    main()
