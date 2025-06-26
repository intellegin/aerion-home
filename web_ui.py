import os
import subprocess
import sys
import atexit
import json
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from speak import get_elevenlabs_voices, DEFAULT_VOICE # Import the new function
import google_auth as google_auth_helper # Import the new auth module
import sounddevice as sd # Import the sounddevice library
from tools import tools, _load_tools # Import the loader
from audio_in import Transcriber # Corrected import path
from command_handler import handle_command, conversation_history, SYSTEM_PROMPT

app = Flask(__name__)
CORS(app)
app.secret_key = 'super_secret_key_for_flashing' # Required for flashing messages
socketio = SocketIO(app, cors_allowed_origins="*")

def _to_friendly_name(name: str) -> str:
    """Converts a function_name like 'get_all_events' to 'Get All Events'."""
    return name.replace('_', ' ').title()

# Make the function available in all templates
app.jinja_env.globals.update(to_friendly_name=_to_friendly_name)

# Global variable to hold the main.py process
main_process = None

@app.context_processor
def inject_auth_status():
    """Injects Google auth status into all templates."""
    return dict(auth_status=google_auth_helper.get_auth_status())

# Cache for voices to avoid excessive API calls
_voice_cache = None
_voice_cache_time = 0

ALLOWED_EXTENSIONS = {'.py', '.txt', '.md', '.json', '.env'}
SETTINGS_FILE = 'settings.json'

def get_settings():
    """Reads settings from the settings file."""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def save_settings(settings_data):
    """Writes settings to the settings file."""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings_data, f, indent=4)

def get_editable_files():
    """Scan the root directory for files with allowed extensions."""
    files = []
    for f in os.listdir('.'):
        if os.path.isfile(f) and os.path.splitext(f)[1] in ALLOWED_EXTENSIONS:
            files.append(f)
    return sorted(files)

def get_python_files_to_watch():
    """Returns a list of all .py files to monitor for changes."""
    return [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.py')]

@app.route('/')
def index():
    """A minimalist home page with just the assistant control."""
    return render_template('home.html')

@app.route('/files')
def files():
    """Page for viewing and editing project files."""
    editable_files = get_editable_files()
    return render_template('files.html', files=editable_files)

@app.route('/settings')
def settings():
    """Page for managing application settings, like voice selection."""
    return render_template('settings.html')

@app.route('/tools')
def tools_page():
    """Page to display available tools."""
    return render_template('tools.html', tools=tools)

@app.route('/auth')
def auth():
    """Page for managing Google Authentication."""
    return render_template('auth.html')

@app.route('/view/<filename>')
def view_file(filename):
    """Read-only view for a file."""
    if os.path.splitext(filename)[1] not in ALLOWED_EXTENSIONS:
        flash(f"Error: '{filename}' is not a viewable file type.", 'error')
        return redirect(url_for('files'))
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        return render_template('view.html', filename=filename, content=content)
    except FileNotFoundError:
        flash(f"Error: File '{filename}' not found.", 'error')
        return redirect(url_for('files'))
    except Exception as e:
        flash(f"Error reading file: {e}", 'error')
        return redirect(url_for('files'))

@app.route('/edit/<filename>')
def edit_file(filename):
    """Page to edit a specific file, restricted by user."""
    auth_status = google_auth_helper.get_auth_status()
    if not auth_status or auth_status.get('email') != 'sheldonsadler@gmail.com':
        flash('You are not authorized to edit files.', 'error')
        return redirect(url_for('files'))

    if os.path.splitext(filename)[1] not in ALLOWED_EXTENSIONS:
        flash(f"Error: '{filename}' is not an editable file type.", 'error')
        return redirect(url_for('files'))
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        return render_template('edit.html', filename=filename, content=content)
    except FileNotFoundError:
        flash(f"Error: File '{filename}' not found.", 'error')
        return redirect(url_for('files'))
    except Exception as e:
        flash(f"Error reading file: {e}", 'error')
        return redirect(url_for('files'))

@app.route('/save/<filename>', methods=['POST'])
def save_file(filename):
    """Endpoint to save the file content, restricted by user."""
    auth_status = google_auth_helper.get_auth_status()
    if not auth_status or auth_status.get('email') != 'sheldonsadler@gmail.com':
        flash('You are not authorized to save files.', 'error')
        return redirect(url_for('files'))

    if os.path.splitext(filename)[1] not in ALLOWED_EXTENSIONS:
        flash(f"Error: Cannot save '{filename}'. Invalid file type.", 'error')
        return redirect(url_for('edit_file', filename=filename))
    
    content = request.form['content']
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        flash(f"Successfully saved '{filename}'!", 'success')
    except Exception as e:
        flash(f"Error saving file: {e}", 'error')

    return redirect(url_for('edit_file', filename=filename))

def get_cached_voices():
    """Get voices from cache or fetch if cache is old (5 min expiry)."""
    global _voice_cache, _voice_cache_time
    if _voice_cache and (time.time() - _voice_cache_time < 300):
        return _voice_cache
    
    print("Fetching fresh voice list from ElevenLabs...")
    _voice_cache = get_elevenlabs_voices()
    _voice_cache_time = time.time()
    return _voice_cache

def emit_status_update():
    """Gets the current status and emits it to all clients."""
    global main_process
    settings = get_settings()
    
    current_voice_name = "Unknown"
    try:
        voices = get_cached_voices()
        if voices:
            current_voice_id = settings.get("voice_id") or os.getenv("VOICE_NAME") or DEFAULT_VOICE
            voice_map = {v['id']: v['name'] for v in voices}
            current_voice_name = voice_map.get(current_voice_id, "Default")
    except Exception as e:
        print(f"Could not determine current voice name: {e}")

    app_status = 'running' if main_process and main_process.poll() is None else 'stopped'
    wake_word = settings.get("wake_word", "jarvis")
    
    # Emit the status to all clients
    socketio.emit('status_update', {
        'status': app_status, 
        'voice_name': current_voice_name,
        'wake_word': wake_word
    })

@socketio.on('connect')
def handle_connect():
    """Send initial status to a newly connected client."""
    print("Client connected. Sending initial status.")
    emit_status_update()

# --- Assistant Process Event Relay ---
# These handlers receive events from the main.py assistant process
# and broadcast them to all connected web clients.

@socketio.on('user_speech_update')
def handle_user_speech(data):
    """Relay user speech from the assistant process to all web clients."""
    socketio.emit('user_speech_update', data)

@socketio.on('ai_speech_update')
def handle_ai_speech(data):
    """Relay AI speech from the assistant process to all web clients."""
    socketio.emit('ai_speech_update', data)

@socketio.on('assistant_state_update')
def handle_assistant_state(data):
    """Relay assistant state from the assistant process to all web clients."""
    socketio.emit('assistant_state_update', data)

@app.route('/api/microphones')
def get_microphones_endpoint():
    """Endpoint to get available audio input devices."""
    try:
        devices = sd.query_devices()
        input_devices = [
            {'id': i, 'name': d['name']} 
            for i, d in enumerate(devices) 
            if d['max_input_channels'] > 0
        ]
        return jsonify(input_devices)
    except Exception as e:
        print(f"Error querying audio devices: {e}")
        return jsonify({"error": "Could not fetch audio devices."}), 500

@app.route('/api/speakers')
def get_speakers_endpoint():
    """Endpoint to get available audio output devices."""
    try:
        devices = sd.query_devices()
        output_devices = [
            {'id': i, 'name': d['name']}
            for i, d in enumerate(devices)
            if d['max_output_channels'] > 0
        ]
        return jsonify(output_devices)
    except Exception as e:
        print(f"Error querying audio devices: {e}")
        return jsonify({"error": "Could not fetch audio devices."}), 500

@app.route('/api/voices')
def get_voices_endpoint():
    """Endpoint to get available TTS voices."""
    voices = get_cached_voices()
    return jsonify(voices)

@app.route('/api/settings', methods=['GET'])
def get_settings_endpoint():
    """Endpoint to get current settings."""
    return jsonify(get_settings())

@app.route('/api/settings', methods=['POST'])
def save_settings_endpoint():
    """Endpoint to save settings."""
    new_settings = request.json
    save_settings(new_settings)
    emit_status_update() # Emit status update on voice change
    return jsonify({'status': 'success', 'settings': new_settings})

@app.route('/start', methods=['POST'])
def start_app():
    """Endpoint to start the main application."""
    global main_process
    if main_process and main_process.poll() is None:
        return jsonify({'status': 'running', 'message': 'Assistant is already running.'})
    
    start_assistant_process()
    emit_status_update()
    return jsonify({'status': 'running', 'message': 'Assistant started.'})

@app.route('/stop', methods=['POST'])
def stop_app():
    """Endpoint to stop the main application."""
    global main_process
    if main_process and main_process.poll() is None:
        print("Stopping assistant process...")
        main_process.terminate()
        try:
            main_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            main_process.kill()
        main_process = None
        emit_status_update()
        return jsonify({'status': 'stopped', 'message': 'Assistant stopped.'})
    
    emit_status_update() # Also emit if it was already stopped
    return jsonify({'status': 'stopped', 'message': 'Assistant was not running.'})

def start_assistant_process():
    """Starts the main.py assistant as a subprocess."""
    global main_process
    if main_process and main_process.poll() is None:
        return # Already running

    python_executable = sys.executable
    main_script_path = os.path.join(os.path.dirname(__file__), 'main.py')
    
    print(f"Starting assistant process: {python_executable} {main_script_path}")
    main_process = subprocess.Popen([
        python_executable, main_script_path,
        '--socket-port', str(5001) # Use the same port as the web UI
    ])

def cleanup_assistant_process():
    """Ensure the assistant process is terminated when the web UI exits."""
    global main_process
    if main_process and main_process.poll() is None:
        print("Web UI is shutting down, terminating assistant process...")
        main_process.terminate()
        main_process.wait()

atexit.register(cleanup_assistant_process)

# --- Google Auth Routes ---
@app.route('/google/login')
def google_login():
    """Redirects to Google's consent screen."""
    redirect_uri = url_for('google_callback', _external=True)
    auth_url = google_auth_helper.get_auth_url(redirect_uri)
    return redirect(auth_url)

@app.route('/google/callback')
def google_callback():
    """Handles the callback from Google after user consent."""
    code = request.args.get('code')
    redirect_uri = url_for('google_callback', _external=True)
    success = google_auth_helper.process_auth_callback(code, redirect_uri)
    if success:
        flash('Successfully authenticated with Google!', 'success')
    else:
        flash('Failed to authenticate with Google.', 'error')
    return redirect(url_for('auth'))

@app.route('/api/google/status')
def google_status():
    """Returns the current Google Auth status."""
    return jsonify(google_auth_helper.get_auth_status())

@app.route('/api/google/logout', methods=['POST'])
def google_logout():
    """Logs the user out by deleting their token."""
    success = google_auth_helper.revoke_auth()
    return jsonify({'status': 'success' if success else 'failure'})

def run_assistant_process():
    """Starts the assistant process in a separate thread."""
    global assistant_process
    # Ensure the tools are loaded in the main process before starting the assistant
    _load_tools()
    
    assistant_path = os.path.join(os.path.dirname(__file__), "main.py")
    if assistant_process and assistant_process.is_alive():
        print("Assistant process already running.")

def main():
    """Starts the Flask web UI and the assistant process."""
    # Watch for changes in the main script and the tools directory
    extra_files = [
        os.path.join(os.path.dirname(__file__), 'command_handler.py'),
        os.path.join(os.path.dirname(__file__), 'tools') # Watch the whole directory
    ]
    
    # Start the Flask app with the reloader
    socketio.run(app, host="127.0.0.1", port=5001, debug=True, allow_unsafe_werkzeug=True, extra_files=extra_files)

if __name__ == "__main__":
    main() 