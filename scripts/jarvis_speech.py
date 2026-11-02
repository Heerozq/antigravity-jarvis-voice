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

SETTINGS_FILE = r"C:\Users\Admin\.gemini\config\jarvis_settings.json"
LOG_FILE = os.path.join(tempfile.gettempdir(), "antigravity_jarvis.log")
RAW_AUDIO_PATH = os.path.join(tempfile.gettempdir(), "antigravity_jarvis_raw.mp3")
READY_AUDIO_PATH = os.path.join(tempfile.gettempdir(), "antigravity_jarvis_ready.wav")
PYTHON_BACKEND_PATH = r"D:\VoiceStudio\project\.venv\Scripts\python.exe"
PROJECT_DIR = r"D:\VoiceStudio\project"

def load_settings():
    defaults = {"enabled": True, "speed": 1.35, "voice": "Atul Kapoor"}
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
        for _ in range(12):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:3900/health", timeout=1):
                    log("Headless backend is now ready!")
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

def replay_last():
    log("Replay requested")
    settings = load_settings()
    speed = float(settings.get("speed", 1.35))
    log(f"Replaying with current speed: {speed}x")

    ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"
    ffplay_path = r"C:\ffmpeg\bin\ffplay.exe"

    if not os.path.exists(ffplay_path):
        log("ffplay not found")
        return

    # Stop any current playback
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe"], capture_output=True)
    except Exception:
        pass

    # If raw audio exists, re-bake at the current speed!
    if os.path.exists(RAW_AUDIO_PATH) and os.path.exists(ffmpeg_path):
        af_filter = f"atempo={speed},apad=pad_dur=1.5"
        log(f"Re-baking audio for replay with: {af_filter}")
        subprocess.run([
            ffmpeg_path, "-y", "-i", RAW_AUDIO_PATH,
            "-af", af_filter,
            READY_AUDIO_PATH
        ], capture_output=True, check=False)
        
        log(f"Playing re-baked audio at {speed}x")
        subprocess.run([
            ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet",
            READY_AUDIO_PATH
        ], check=False)
    elif os.path.exists(READY_AUDIO_PATH):
        subprocess.run([
            ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet",
            READY_AUDIO_PATH
        ], check=False)

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

    speed = float(settings.get("speed", 1.35))
    voice = settings.get("voice", "Atul Kapoor")

    # Ensure headless backend is alive
    ensure_backend_running()

    log(f"Hook invoked (speed={speed}, voice={voice})")
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception as e:
        log(f"Error parsing stdin: {e}")
        payload = {}

    transcript_path = payload.get("transcriptPath")
    if not transcript_path or not os.path.exists(transcript_path):
        log(f"Transcript not found: {transcript_path}")
        print("{}")
        return

    # Find the latest user-facing assistant response
    response_text = ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        for entry in reversed(lines):
            if entry.get("type") == "PLANNER_RESPONSE" and entry.get("content"):
                response_text = entry["content"]
                break
    except Exception as e:
        log(f"Error reading transcript: {e}")
        print("{}")
        return

    cleaned_speech = clean_text_for_speech(response_text)
    if not cleaned_speech or len(cleaned_speech) < 3:
        log("Cleaned speech empty or too short")
        print("{}")
        return

    # Check deduplication to avoid repeating the exact same message
    msg_hash = hashlib.sha256((cleaned_speech + str(speed) + voice).encode("utf-8")).hexdigest()
    cache_file = os.path.join(tempfile.gettempdir(), "antigravity_jarvis_last_hash.txt")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                if f.read().strip() == msg_hash:
                    log("Message already spoken (deduplication hit)")
                    print("{}")
                    return
        except Exception:
            pass

    # Save current hash
    try:
        with open(cache_file, "w") as f:
            f.write(msg_hash)
    except Exception:
        pass

    log(f"Synthesizing {len(cleaned_speech)} chars: {cleaned_speech[:60]}...")

    # Call VoiceStudio API with NATIVE speed 1.0 (preserves true neural bass and pitch)
    try:
        api_url = "http://127.0.0.1:3900/v1/audio/speech"
        chunks = split_text_into_chunks(cleaned_speech)
        combined_audio = b""

        for i, chunk in enumerate(chunks):
            log(f"Sending chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
            data = {
                "model": "omnivoice",
                "voice": voice,
                "input": chunk,
                "speed": 1.0  # Keep model output pristine
            }
            req = urllib.request.Request(
                api_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(data).encode("utf-8")
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                chunk_audio = resp.read()
                combined_audio += chunk_audio
                log(f"Chunk {i+1} received: {len(chunk_audio)} bytes")

        with open(RAW_AUDIO_PATH, "wb") as f:
            f.write(combined_audio)

        # Stop any previous playback so sounds don't overlap
        try:
            subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe"], capture_output=True)
        except Exception:
            pass

        # Bake speed adjustment and a physical 1.5s silence tail into the final WAV
        ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"
        ffplay_path = r"C:\ffmpeg\bin\ffplay.exe"

        if os.path.exists(ffmpeg_path) and os.path.exists(ffplay_path):
            af_filter = f"atempo={speed},apad=pad_dur=1.5"
            log(f"Baking audio via ffmpeg: {af_filter}")
            subprocess.run([
                ffmpeg_path, "-y", "-i", RAW_AUDIO_PATH,
                "-af", af_filter,
                READY_AUDIO_PATH
            ], capture_output=True, check=False)

            log(f"Playing baked audio with ffplay at {speed}x")
            subprocess.run([
                ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet",
                READY_AUDIO_PATH
            ], check=False)
            log("Playback finished successfully")
        elif os.path.exists(ffplay_path):
            subprocess.run([
                ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet",
                RAW_AUDIO_PATH
            ], check=False)
    except Exception as e:
        log(f"TTS or playback error: {e}")

    print("{}")

if __name__ == "__main__":
    main()
