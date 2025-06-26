# Pi-5 AI Voice Assistant

This project transforms a computer (originally a Raspberry Pi 5, now platform-agnostic) into a sophisticated, voice-controlled AI assistant. It features a modular architecture, a web-based UI for control and real-time feedback, and an extensible tool system that allows the AI to interact with external services like Google Calendar, web search, and more.

---

## Architecture Overview

The system is split into two main processes that communicate in real time:

1.  **Web UI (`web_ui.py`)**: A Flask application that serves as the control panel and process manager. It provides a web interface to start/stop the assistant, manage settings, and view the conversation in real time.
2.  **Assistant (`main.py`)**: The core voice assistant logic. It handles wake-word detection, audio transcription, command processing via an LLM, and text-to-speech responses.

Communication between the browser, the web UI server, and the assistant process is handled by **Socket.IO**, enabling real-time status updates, conversation display, and commands.

```mermaid
graph TD
    subgraph Browser
        A[Web UI - home.html]
    end

    subgraph Web Server (Flask)
        B(web_ui.py)
        C{settings.json}
    end
    
    subgraph Assistant Process
        E(main.py)
        F[Wake Word]
        G[VAD & Transcription]
        H[LLM Command Handler]
        I[Modular Tools]
        J[Text-to-Speech]
    end

    A -- HTTP/Socket.IO --> B
    B -- Manages --> E
    B -- Reads/Writes --> C

    E -- Socket.IO --> B
    B -- Socket.IO --> A

    E --> F
    F --> E
    E -- State Change --> G
    G --> H
    H --> I
    I -- Result --> H
    H --> J
```

---

## Key Components

-   **`web_ui.py`**: Flask-based web server.
    -   Starts/stops the `main.py` assistant process.
    -   Serves the HTML/CSS/JS frontend.
    -   Handles Google OAuth2 authentication flow for tools.
    -   Provides a settings page to configure the wake word, microphone, and speaker.
    -   Uses Socket.IO to push real-time status, state, and dialogue updates to the browser.

-   **`main.py`**: The main assistant loop.
    -   Connects to the `web_ui.py` server via a Socket.IO client.
    -   **Wake Word (`wake_word_listener.py`)**: Uses `pvporcupine` to listen for a wake word (e.g., "Jarvis").
    -   **Audio Input (`audio_in.py`)**: Uses `webrtcvad` for Voice Activity Detection to determine when the user has finished speaking, then transcribes the captured audio using **Picovoice Leopard** for fast, on-device performance.
    -   **Command Handling (`command_handler.py`)**: Sends the transcribed text and conversation history to an OpenAI LLM to get a response or a tool call.
    -   **Text-to-Speech (`speak.py`)**: Synthesizes the LLM's response into audio using **ElevenLabs**.

-   **`tools/`**: A directory containing the assistant's tools.
    -   Each tool is a separate `.py` file containing a `run()` function and a `description` variable.
    -   The `__init__.py` file dynamically loads all tools, making them available to the `command_handler`.
    -   This modular design allows for easy extension. The assistant can even create new tools for itself using the `create_new_tool` function.

-   **`socket_client.py`**: A shared Socket.IO client instance used by `main.py` and other components to communicate with the `web_ui.py` server.

-   **`templates/home.html`**: The main page of the web UI.
    -   Displays the assistant's status (running/stopped) and state (listening, processing, speaking).
    -   Provides a button to start/stop the assistant.
    -   Shows a real-time transcript of the conversation between the user and the AI.
    -   Links to the settings page.

-   **`database.py`**: Logs all conversations to a local SQLite database for history and analysis.

---

## Setup and Installation

### 1. Prerequisites
- Python 3.9+
- An internet connection
- For voice I/O: a microphone and speakers

### 2. Clone the repository and install dependencies:
```bash
git clone <your-repo-url>
cd <repository-name>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root and add the following keys.

```env
# OpenAI for the language model
OPENAI_API_KEY="sk-..."

# ElevenLabs for Text-to-Speech
ELEVEN_API_KEY="..."

# Picovoice for on-device wake-word and transcription
PICOVOICE_ACCESS_KEY="..."
```

### 4. Google Authentication (Optional, for Google Tools)
If you want to use tools that interact with Google services (like Calendar), you must authenticate.

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project.
3.  Enable the **Google Calendar API**, **Gmail API**, and **People API**.
4.  Create an "OAuth 2.0 Client ID" credential for a "Web application".
5.  Under "Authorized redirect URIs", add `http://127.0.0.1:5001/google/callback`.
6.  Download the JSON credentials file and save it as `credentials.json` in the project's root directory.

---

## How to Run

1.  **Start the Web UI**:
    ```bash
    python web_ui.py
    ```
    This will start the Flask server. Open your browser to `http://127.0.0.1:5001`.

2.  **Configure Settings**:
    - Click the settings icon in the top right.
    - Set your desired wake word (e.g., "jarvis").
    - Select your microphone and speaker devices from the dropdowns and save.

3.  **Authenticate with Google (if needed)**:
    - On the settings page, click the "Sign in with Google" button and complete the OAuth flow. A `token.json` file will be created.

4.  **Start the Assistant**:
    -   Navigate back to the home page.
    -   Click the large microphone button. It will turn green to indicate the assistant is running and listening for the wake word.

5.  **Talk to the Assistant**:
    -   Say the wake word.
    -   The UI will update to show "Listening...". Speak your command.
    -   The conversation will appear in real-time on the screen.

You can stop the assistant at any time by clicking the large button again.

---

## Creating a New Tool

The assistant can create new tools for itself. The process is as follows:

1.  **Request**: Ask the assistant to create a new tool. For example: "Create a tool that tells me a joke."
2.  **Execution**: The assistant will use the `create_new_tool` function. This function writes a new Python file into the `tools/` directory (e.g., `tools/tell_joke.py`).
3.  **Structure**: The new file will contain:
    - A `description` variable explaining what the tool does.
    - A `run()` function that implements the tool's logic.
4.  **Activation**: The assistant will automatically detect and load the new tool on its next restart, making it immediately available for use.

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