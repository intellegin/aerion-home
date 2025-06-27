# Aerion: Your Personal AI Framework

This project is a sophisticated, voice-controlled AI assistant built on a modular, extensible framework. It features a real-time web UI, a powerful tool system, and deep integrations with external services. Originally designed for a Raspberry Pi, it is now a platform-agnostic framework that you can run on any system and adapt for any purpose.

---

## Core Features

-   **🎙️ Voice-Controlled Assistant**: Hands-free interaction using a wake word, with real-time voice activity detection and transcription.
-   **🌐 Real-Time Web UI**: A comprehensive web interface for controlling the assistant, viewing live dialogue, managing tools, editing files, and configuring settings.
-   **🧩 Modular & Hot-Loadable Tools**: The assistant's capabilities are defined by simple Python files in the `tools/` directory. The system automatically loads new tools without requiring a restart.
-   **🤖 Agentic Capabilities**:
    -   **Tool Creation**: The assistant can write its own tools by generating new Python files in the `tools/` directory.
    -   **Workflow Chaining**: The AI can intelligently chain multiple tool calls together to accomplish complex tasks.
-   **🔌 Major Integrations**:
    -   **Notion**: Search databases, create and edit pages, and perform Q&A with your Notion workspace.
    -   **Google**: Authenticates with Google services (Calendar, Gmail) using OAuth2.
    -   **Twilio**: Send SMS messages directly from the assistant.
-   **🔒 Secure Remote Access**: Built-in `ngrok` integration automatically creates a secure public URL for the web UI, allowing you to connect from anywhere and enabling webhooks for integrations like Notion.
-   **⚙️ High Configurability**: Easily configure wake words, select specific microphone and speaker devices, and choose from a wide range of AI voices, all from the settings page.

---

## Architecture Overview

The system is split into two main processes that communicate in real time:

1.  **Web UI (`web_ui.py`)**: A Flask application that serves as the control panel and process manager.
2.  **Assistant (`main.py`)**: The core voice assistant logic that handles wake-word detection, audio processing, and tool execution.

Communication between the browser, the web UI server, and the assistant process is handled by **Socket.IO**, enabling real-time updates.

```mermaid
graph TD
    subgraph Browser
        A[Web UI - Vue.js Frontend]
    end

    subgraph Web Server (Flask)
        B(web_ui.py)
        C{config.py & .env}
    end
    
    subgraph Assistant Process
        E(start.py -> main.py)
        F[Wake Word]
        G[VAD & Transcription]
        H[LLM Command Handler]
        I[Modular Tools]
        J[Text-to-Speech]
    end

    A -- HTTP/Socket.IO --> B
    B -- Manages --> E
    B -- Reads --> C

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

## Setup and Installation

### 1. Prerequisites
- Python 3.9+
- An internet connection
- For voice I/O: a microphone and speakers
- An [ngrok account](https://ngrok.com/) and authtoken for secure remote access.

### 2. Clone the repository and install dependencies:
```bash
git clone <your-repo-url>
cd <repository-name>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root by copying the example and add your secret keys.

```bash
cp .env.example .env
```

Then, edit `.env` and fill in your keys:

```env
# --- Core Services ---
# OpenAI for the language model
OPENAI_API_KEY="sk-..."

# ElevenLabs for Text-to-Speech
ELEVEN_API_KEY="..."

# Picovoice for on-device wake-word and transcription
PICOVOICE_ACCESS_KEY="..."

# --- Integrations ---
# Ngrok for secure tunneling (get from your ngrok dashboard)
NGROK_AUTHTOKEN="..."

# Twilio for sending SMS
TWILIO_ACCOUNT_SID="..."
TWILIO_AUTH_TOKEN="..."
TWILIO_PHONE_NUMBER="..." # Your Twilio phone number

# Notion Integration
NOTION_CLIENT_ID="..."
NOTION_CLIENT_SECRET="..."
# NOTION_ACCESS_TOKEN is generated and stored automatically

# --- Optional ---
# Set to your name to be greeted in the UI
USER_NAME="Guest"
```

### 4. Google Authentication (Optional)
If you want to use tools that interact with Google services (like Calendar), you must create credentials.

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project.
3.  Enable the **Google Calendar API**, **Gmail API**, and **People API**.
4.  Create an "OAuth 2.0 Client ID" credential for a "Web application".
5.  Download the JSON credentials file and save it as `credentials.json` in the project's root directory.
6.  When you run the app, it will generate a secure ngrok URL. You must add this URL to your Google Console under "Authorized redirect URIs".
    -   Example: `https://<your-ngrok-subdomain>.ngrok-free.app/google/callback`

### 5. Notion Integration Setup (Optional)
1.  Go to [Notion Developers](https://www.notion.so/my-integrations) and create a new integration.
2.  Note the **Client ID** and **Client Secret** and add them to your `.env` file.
3.  The application will generate a secure ngrok URL when it starts. You must add this URL to your Notion integration settings under "Redirect URIs".
    -   Example: `https://<your-ngrok-subdomain>.ngrok-free.app/notion/callback`
4.  Share specific databases or pages in your Notion workspace with your new integration to grant it access.

---

## How to Run

1.  **Start the Application**:
    ```bash
    python start.py
    ```
    This script launches the Flask web server. The terminal will display a public `ngrok` URL.

2.  **Access the UI**:
    - Open your browser to the provided `ngrok` URL or to `http://127.0.0.1:5001` if accessing locally.

3.  **Configure Settings**:
    - Navigate to the **Settings** tab.
    - Select your microphone and speaker devices, choose a voice, and set a wake word.
    - Save your changes.

4.  **Connect Integrations**:
    - Navigate to the **Integrations** tab.
    - Click "Connect" for Notion or Google and complete the authentication flow.

5.  **Start the Assistant**:
    - Navigate back to the **Home** tab.
    - Click the large microphone button. It will turn green to indicate the assistant is running and listening for the wake word.

6.  **Talk to the Assistant**:
    - Say the wake word.
    - The UI will update to show "Listening...". Speak your command.
    - The full conversation will appear in real-time on the screen.

---

## Using as a Framework

This project is designed to be a starting point. Here's how to adapt and extend it:

### 1. Creating a New Tool
This is the primary way to add new functionality.

1.  **Create a file**: Add a new `.py` file to the `tools/` directory (e.g., `tools/get_weather.py`).
2.  **Define the Tool**: Inside the file, add two components:
    -   A `TOOL_DEFINITION` dictionary describing the function, its parameters, and what it does. This follows the OpenAI Functions format.
    -   A `run(**args)` function that contains the Python logic to execute the tool. It must accept the same arguments defined in `TOOL_DEFINITION`.
3.  **Update the System Prompt**: Open `config.py` and modify the `SYSTEM_PROMPT`. Add a "WORKFLOW" section that describes when and how the AI should use your new tool.
4.  **Reload and Use**: The application will automatically load the new tool. You can now ask the assistant to use it.

### 2. Customizing the UI
The frontend is built with standard HTML, CSS, and JavaScript.

-   **Templates**: Modify the `.html` files in the `templates/` directory to change the layout.
-   **Static Assets**: Add or change styles in `static/css/` and client-side logic in `static/js/`.
-   **Backend API**: Add new API endpoints in `web_ui.py` to support new frontend features.

---

## Current Tools

The framework comes with a powerful set of pre-built tools:

| File Name                   | Description                                             |
| --------------------------- | ------------------------------------------------------- |
| `create_new_tool.py`        | Creates a new tool file in the `tools/` directory.      |
| `create_notion_page.py`     | Creates a new page in a Notion database.                |
| `edit_notion_page.py`       | Appends content to an existing Notion page.             |
| `get_page_content.py`       | Retrieves the full content of a Notion page.            |
| `search_pages_in_database.py`| Searches for pages within a specific Notion database.   |
| `search_notion_databases.py`| Searches for Notion databases shared with the integration.|
| `send_sms.py`               | Sends an SMS message using Twilio.                      |
| `search_web.py`             | Searches the web using DuckDuckGo.                      |
| `get_current_time.py`       | Gets the current time and date.                         |
| `create_email_draft.py`     | Creates a draft email in Gmail.                         |
| `get_all_upcoming_events.py`| Fetches upcoming events from Google Calendar.           |
| `get_my_profile.py`         | Gets basic user profile info from Google.               |
| `navigate_ui.py`            | Navigates the web UI to different pages.                |
| `save_email_draft.py`       | Saves an email draft. (Likely overlaps with above)      |
| `search_contacts.py`        | Searches Google Contacts.                               |
| `send_email.py`             | Sends an email using Gmail.                             |
