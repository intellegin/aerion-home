# Pi-5 AI Communicator

A lightweight Python project that turns a Raspberry Pi 5 into an AI-powered conversational device.  It combines simple rule-based responses (the current `command_handler.py`) with the option to fall back to an OpenAI Large Language Model (LLM) for anything more complex.

---

## 1. Features

• **Keyword commands** — Immediate replies for hard-coded phrases (e.g. "hello").

• **LLM fallback** — When no keyword matches, the user's text is sent to OpenAI Chat Completion (GPT-3.5-Turbo by default).

• **Voice-only input** — Records microphone audio, converts speech → text with OpenAI Whisper.

• **CLI first, voice ready** — The starter loop runs in a terminal, but the architecture is ready for you to plug in speech-to-text (Whisper/Vosk) and text-to-speech (Piper/Mimic3).

• **Runs at boot** — Optional `systemd` service file lets the Pi launch the chat agent automatically after power-up.

• **Audible replies** — Speaks responses using pyttsx3, `say` (macOS), or `espeak`.

---

## 2. Repository Layout

```text
.
├── audio_in.py            # Record + transcribe voice (OpenAI Whisper)
├── command_handler.py     # Rule-based keywords → canned replies
├── main.py                # Voice-only main loop
├── requirements.txt       # Python dependencies
├── README.md              # This document
└── systemd/
    └── ai_communicator.service  # (optional) Boot service
```

> **Note**  `main.py` and the `systemd/` file are not created yet; the README shows the recommended structure.

---

## 3. Hardware Requirements

1. Raspberry Pi 5 (4 GB or 8 GB RAM recommended)
2. micro-SD card with Raspberry Pi OS (64-bit)
3. Internet connectivity (Ethernet or Wi-Fi)
4. OPTIONAL for voice:
   • USB microphone or ReSpeaker HAT
   • Speakers or 3.5 mm audio output

---

## 4. Software Setup (Python ≥ 3.9)

### 4.1. Clone & create a virtual environment

```bash
sudo apt update && sudo apt install python3-venv git -y

git clone https://github.com/yourname/pi5-ai-communicator.git
cd pi5-ai-communicator

python3 -m venv venv
source venv/bin/activate
```

### 4.2. Install dependencies

```bash
pip install -r requirements.txt
```

*The key packages are: `openai` (LLM access) and `python-dotenv` (loads environment variables from a `.env` file).*

### 4.3. Configure your OpenAI key

Create a file named `.env` in the project root:

```env
OPENAI_API_KEY="sk-…your_key…"
OPENAI_MODEL="gpt-3.5-turbo"  # optional override
```

**Never commit your API key to version control.**

---

## 5. Running the chat agent (VOICE MODE)

```bash
python main.py
```

You'll be prompted with a 5-second recording window. Speak, wait for transcription, then read the AI response.

---

## 6. Extending the Project

| Area               | Quick Start |
|--------------------|-------------|
| Voice input        | Already built-in (audio_in.py → OpenAI Whisper). |
| Text-to-Speech     | Already built-in via pyttsx3; install `say` (mac), or `espeak` on Linux if needed. |
| Wake-word          | Try Porcupine (`pip install pvporcupine`). |
| Web UI             | Add a Flask or FastAPI endpoint, then serve with a lightweight frontend (HTMX/Alpine). |

---

## 7. Autostart with systemd (optional)

1. Copy `systemd/ai_communicator.service` to `/etc/systemd/system/`.
2. Edit `User=` and paths if different.
3. Enable & start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai_communicator
sudo systemctl start ai_communicator
```

---

## 8. Troubleshooting

• **`ModuleNotFoundError`** — Ensure you activated the venv: `source venv/bin/activate`.

• **`openai.error.AuthenticationError`** — Double-check `OPENAI_API_KEY` in `.env`.

• **Audio glitches** — Increase `dtparam=audio=on`, tweak ALSA volumes, or use a USB audio dongle.

---

## 9. License

MIT License © 2024 Your Name

Feel free to fork and improve.  PRs welcome! 