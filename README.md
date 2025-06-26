# Pi-5 AI Voice Assistant

This project transforms a computer (originally a Raspberry Pi 5, now platform-agnostic) into a sophisticated, voice-controlled AI assistant. It features a modular architecture with a decoupled frontend and backend, real-time communication, and integrations with external services like Google and ElevenLabs.

---

## Architecture Overview

The system is split into two main processes that communicate in real time:

1.  **Web UI (`web_ui.py`)**: A Flask application that serves as the control panel and process manager. It provides a web interface to start/stop the assistant, manage settings, and handle authentication.
2.  **Assistant (`main.py`)**: The core voice assistant logic. It handles wake-word detection, audio transcription, command processing via an LLM, and text-to-speech responses.

Communication between the frontend (browser), the web UI server, and the assistant process is handled by **Socket.IO**, enabling real-time status updates and commands (e.g., voice-based UI navigation).

```mermaid
graph TD
    subgraph Browser
        A[Web UI - index.html]
    end

    subgraph Web Server (Flask)
        B(web_ui.py)
        C{settings.json}
        D{google_token.json}
    end
    
    subgraph Assistant Process
        E(main.py)
        F[Wake Word]
        G[Audio Transcription]
        H[LLM Command Handler]
        I[Tools - Google, Web, etc.]
        J[Text-to-Speech]
    end

    A -- HTTP/Socket.IO --> B
    B -- Manages --> E
    B -- Reads/Writes --> C
    B -- Manages --> D

    E -- Socket.IO --> B
    B -- Socket.IO --> A

    E --> F
    F --> G
    G --> H
    H --> I
    H --> J
    I -- response --> H
```

---

## Key Components

-   **`web_ui.py`**: Flask-based web server.
    -   Starts/stops the `main.py` process.
    -   Serves the HTML/CSS/JS frontend.
    -   Handles Google OAuth2 authentication flow.
    -   Provides API endpoints for settings and voice model management.
    -   Uses Socket.IO to push real-time status updates to the browser.

-   **`main.py`**: The main assistant loop.
    -   Connects to the `web_ui.py` server via a Socket.IO client.
    -   **Wake Word**: Uses `pvporcupine` to listen for a wake word (e.g., "Jarvis").
    -   **Transcription**: Captures microphone audio and transcribes it locally using **Picovoice Leopard** for fast, on-device performance.
    -   **Command Handling (`command_handler.py`)**: Sends the transcribed text and conversation history to an OpenAI LLM.
    -   **Text-to-Speech (`speak.py`)**: Synthesizes the LLM's response into audio using **ElevenLabs**.
    -   **Crash Resilience**: Automatically restarts its main loop upon encountering an error.

-   **`tools.py`**: A collection of functions the LLM can call to interact with the outside world.
    -   `search_web`: Searches the web with DuckDuckGo.
    -   `get_all_upcoming_events`: Fetches Google Calendar events.
    -   `search_contacts`: Fuzzy-searches Google Contacts.
    -   `create_email_draft`, `send_email`: Manages Gmail.
    -   `navigate_ui`: Sends a command via Socket.IO to change the active tab in the web UI.

-   **`socket_client.py`**: A shared Socket.IO client instance to prevent circular import errors between `main.py` and `tools.py`.

-   **`templates/index.html`**: A single-page application that serves as the frontend.
    -   Displays the assistant's status (running/stopped) and the currently selected voice.
    -   Provides a UI to select and save an ElevenLabs voice (`settings.json`).
    -   Handles the Google authentication process.
    -   Receives real-time updates and navigation commands from the backend via Socket.IO.

-   **`database.py`**: Logs all conversations to a Supabase PostgreSQL database for history and analysis.

---

## Setup and Installation

### 1. Prerequisites
- Python 3.9+
- An internet connection

### 2. Clone the repository and install dependencies:
```bash
git clone <your-repo-url>
cd <repository-name>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root and add the following keys. You can get these from their respective services.

```env
# OpenAI for the language model
OPENAI_API_KEY="sk-..."

# ElevenLabs for Text-to-Speech
ELEVEN_API_KEY="..."
VOICE_NAME="..." # Optional: Default voice ID

# Picovoice for on-device wake-word and transcription
PICOVOICE_ACCESS_KEY="..."

# Supabase for logging conversations (Optional)
SUPABASE_URL="..."
SUPABASE_KEY="..."
```

### 4. Google Authentication
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project.
3.  Enable the **Google Calendar API**, **Gmail API**, and **People API**.
4.  Create an "OAuth 2.0 Client ID" credential for a "Web application".
5.  Under "Authorized redirect URIs", add `http://127.0.0.1:5001/google/callback`.
6.  Download the JSON credentials file and save it as `credentials.json` in the project's root directory.

---

## How to Run

1.  **Start the Web UI and Process Manager**:
    ```bash
    python web_ui.py
    ```
    This will start the Flask server. Open your browser to `http://127.0.0.1:5001`.

2.  **Authenticate with Google**:
    -   Navigate to the "Auth" tab in the web UI.
    -   Click the "Sign in with Google" button and complete the OAuth flow. A `google_token.json` file will be created.

3.  **Start the Assistant**:
    -   Click the microphone button in the header of the web UI. This will start the `main.py` assistant process in the background. The button will turn green to indicate it's running.

4.  **Talk to the Assistant**:
    -   Say the wake word (e.g., "Jarvis").
    -   After the activation sound, speak your command.
    -   The assistant will process the command and respond with voice.

You can stop the assistant at any time by clicking the microphone button again.

---

## Deploying to Vercel

The web UI portion of this application can be deployed to Vercel. However, there are significant limitations due to Vercel's serverless architecture:

-   **The voice assistant (`main.py`) will NOT run.** Vercel does not support the kind of long-running background processes required for wake-word detection.
-   **Local file storage is ephemeral.** Settings and tokens are not persisted. For a full deployment, you would need to adapt the code to use a database (like Supabase or Vercel's own storage solutions) for `settings.json` and `token.json`.

This deployment is best for previewing the web interface or using it as a settings manager if the state were externalized.

### Deployment Steps

1.  **Fork this repository** and connect it to your Vercel account.

2.  **Configure Environment Variables** in your Vercel project settings. You will need:
    -   `SERVER_NAME`: The domain of your Vercel app (e.g., `aerion-home.vercel.app`).
    -   `OPENAI_API_KEY`
    -   `ELEVEN_API_KEY`
    -   `PICOVOICE_ACCESS_KEY`
    -   `SUPABASE_URL`
    -   `SUPABASE_KEY`
    -   Also, copy the contents of your `credentials.json` into a Vercel environment variable named `GOOGLE_CREDENTIALS_JSON`. The application is configured to look for this if `credentials.json` is not found.

3.  **Check Build Settings (Optional)**:
    -   You can leave the Build & Development Settings in the Vercel UI as their defaults. The `vercel.json` file in this repository will automatically override them.
    -   **Install Command**: It will use `pip install -r requirements-vercel.txt` as specified in `vercel.json`.
    -   **Build Command & Output Directory**: These are handled automatically by the `@vercel/python` builder.

4.  **Deploy**. Vercel will use the `vercel.json` file to build and route the application correctly using the lightweight requirements.

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

---

## 10. Database Schema

The application can log all conversations to a Supabase database. The table is named `messages` and has the following schema:

| Column          | Type      | Description                                                                 |
|-----------------|-----------|-----------------------------------------------------------------------------|
| `id`            | `int4`    | Primary key, auto-incrementing.                                             |
| `platform`      | `text`    | The platform the message originated from. Hardcoded to `"raspberry"`.         |
| `source_id`     | `text`    | Nullable. Not currently used.                                               |
| `from_user`     | `text`    | Identifier for the sender (`"user"` or `"jarvis"`).                           |
| `to_user`       | `text`    | Identifier for the recipient (`"jarvis"` or `"user"`).                          |
| `content`       | `text`    | The text content of the message.                                            |
| `direction`     | `text`    | `"outbound"` for user -> AI, `"inbound"` for AI -> user.                     |
| `method`        | `text`    | The method of communication. Hardcoded to `"voice"`.                          |
| `agent_id`      | `int4`    | Nullable. Not currently used.                                               |
| `email_id`      | `int4`    | Nullable. Not currently used.                                               |
| `prompt_log_id` | `int4`    | Nullable. Not currently used.                                               |
| `is_handled`    | `bool`    | Hardcoded to `true`.                                                        |
| `message_type`  | `text`    | The type of message. Hardcoded to `"conversation"`.                         |
| `created_at`    | `timestamp` | Automatically set to the time of insertion.                               |
| `user_id`       | `int8`    | Nullable. Not currently used.                                               |
| `chat_session_id` | `int4`    | A unique integer ID for each conversation session.                          | 