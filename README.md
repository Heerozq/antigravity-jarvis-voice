# J.A.R.V.I.S. Offline Voice Pipeline for Antigravity IDE

A complete, 100% private, offline, GPU-accelerated voice assistant pipeline for **Google Antigravity IDE** and **VS Code**. 

Replaces cloud subscription services (**Wispr Flow** and **ElevenLabs**) with local models running on your NVIDIA GPU, featuring the iconic voice of **Atul Kapoor** (the official Indian voice actor for J.A.R.V.I.S. in the MCU and the voice of *Bigg Boss*).

---

## Features

- **100% Offline & Private:** Audio never leaves your local machine. No monthly subscriptions or API tokens required.
- **RTX 4070 GPU Acceleration:** Near-instant neural voice generation via PyTorch & CUDA.
- **Atul Kapoor Voice Timbre:** Authentic deep baritone voice speaking fluent English.
- **Smart Markdown Cleaner:** Automatically filters out raw code snippets, tables, backticks, and markdown hashes so speech remains conversational.
- **Antigravity Status Bar Controls:**
  - `$(unmute) JARVIS: ON / OFF` (Mute toggle)
  - `$(debug-stop) Stop` (Instant stop switch)
  - `$(dashboard) 1.35x` (Interactive speed dropdown from 1.0x to 2.0x)
  - `$(history) Replay` (Re-reads last response with current speed)
- **Headless Auto-Daemon:** Silently launches the local Python FastAPI backend upon Antigravity IDE startup without keeping any Electron desktop app open.
- **Pitch-Preserved Speedup:** Uses FFmpeg `atempo` time-stretching so accelerating speech doesn't distort pitch into a chipmunk voice.
- **Buffer Tail Protection:** Pre-bakes a 1.5-second silence tail into playback audio to prevent Windows sound driver buffers from truncating the final words.

---

## Architecture Overview

```
User Voice Input (Handy / Parakeet TDT 0.6B)
                  │
                  ▼
         Antigravity IDE
                  │
         AI Generates Turn
                  │
                  ▼
         Stop Lifecycle Hook (hooks.json)
                  │
                  ▼
     Text Cleaner (jarvis_speech.py)
                  │
                  ▼
 VoiceStudio Local Server (FastAPI on Port 3900)
                  │ (k2-fsa/OmniVoice on CUDA)
                  ▼
       Raw Audio Synthesized
                  │
                  ▼
  FFmpeg Processing (atempo + apad tail buffer)
                  │
                  ▼
 ffplay Audio Playback -> Speakers / Headphones
```

---

## Directory Structure

```
antigravity-jarvis-voice/
├── config/
│   └── jarvis_settings.json               # Live configuration (speed, enabled, voice)
├── extension/                             # VS Code / Antigravity IDE UI Extension
│   ├── package.json
│   └── extension.js
├── plugin/                                # Native Antigravity Plugin
│   ├── plugin.json
│   └── hooks.json
└── scripts/
    └── jarvis_speech.py                   # Core TTS pipeline & audio playback bridge
```

---

## Quick Installation

### 1. Prerequisites
- Windows 10/11 (64-bit) with an NVIDIA GPU.
- **FFmpeg** installed and accessible via PATH (`ffmpeg.exe`, `ffplay.exe`).
- **Handy** desktop app (for speech-to-text dictation).
- **VoiceStudio** installed with the `k2-fsa/OmniVoice` model.

### 2. Deploy Extension
Copy the `extension/` folder to your Antigravity IDE extensions directory:
```powershell
Copy-Item -Path "extension" -Destination "$env:USERPROFILE\.antigravity-ide\extensions\jarvis-voice-controls" -Recurse -Force
```

### 3. Deploy Plugin & Scripts
Copy the plugin, script, and configuration files to your Antigravity global config:
```powershell
Copy-Item -Path "scripts\jarvis_speech.py" -Destination "$env:USERPROFILE\.gemini\config\scripts\" -Force
Copy-Item -Path "config\jarvis_settings.json" -Destination "$env:USERPROFILE\.gemini\config\" -Force
Copy-Item -Path "plugin\*" -Destination "$env:USERPROFILE\.gemini\config\plugins\jarvis-voice\" -Recurse -Force
```

### 4. Reload Antigravity IDE
Press `Ctrl + Shift + P` and execute `Developer: Reload Window`.
The J.A.R.V.I.S. controls will appear in your bottom-right status bar and auto-boot the local voice engine.

---

## License
MIT License.

