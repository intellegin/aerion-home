import os
import subprocess
import sys
import atexit
import json
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from speak import get_elevenlabs_voices, DEFAULT_VOICE # Import the new function
import google_auth as google_auth_helper # Import the new auth module
from assistant import Assistant # Import the new Assistant class

app = Flask(__name__)
app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME')
CORS(app)
app.secret_key = 'super_secret_key_for_flashing' # Required for flashing messages
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Create a single instance of the Assistant
# This will be shared across all client connections
assistant = Assistant(on_state_change=lambda state: socketio.emit('assistant_state_change', {'state': state.name}))

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

@app.route('/')
def index():
    """A minimalist home page with just the assistant control."""
    return render_template('home.html')

@app.route('/files')
def files():
    """Page for viewing and editing project files."""
    auth_status = google_auth_helper.get_auth_status()
    if not auth_status or auth_status.get('status') != 'authenticated':
        flash('You must be logged in to view project files.', 'error')
        return redirect(url_for('index'))

    editable_files = get_editable_files()
    return render_template('files.html', files=editable_files)

@app.route('/settings')
def settings():
    """Page for managing application settings, like voice selection."""
    return render_template('settings.html')

@app.route('/auth')
def auth():
    """Page for managing Google Authentication."""
    return render_template('auth.html')

@app.route('/view/<filename>')
def view_file(filename):
    """Read-only view for a file."""
    auth_status = google_auth_helper.get_auth_status()
    if not auth_status or auth_status.get('status') != 'authenticated':
        flash('You must be logged in to view project files.', 'error')
        return redirect(url_for('index'))
        
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
    # This function is now deprecated and will be replaced by state updates from the Assistant class
    pass

@socketio.on('connect')
def handle_connect():
    """Send initial status to a newly connected client."""
    print("Client connected. Sending initial assistant state.")
    # Immediately send the current state to the newly connected client
    socketio.emit('assistant_state_change', {'state': assistant.state.name}, room=request.sid)

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

# --- New Assistant Socket.IO Handlers ---
@socketio.on('start_assistant')
def handle_start_assistant(data):
    """Starts the assistant's listening process."""
    print("Received start_assistant request")
    assistant.start()

@socketio.on('stop_assistant')
def handle_stop_assistant(data):
    """Stops the assistant's listening process."""
    print("Received stop_assistant request")
    assistant.stop()

@socketio.on('audio_stream')
def handle_audio_stream(audio_chunk):
    """Processes an incoming audio chunk from the client."""
    assistant.process_audio_chunk(audio_chunk)

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

if __name__ == '__main__':
    print("Starting Flask web UI with integrated assistant...")
    print("Open your browser and go to http://127.0.0.1:5001")
    # We no longer start a separate thread for the assistant.
    # It's now integrated and driven by Socket.IO events.
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, use_reloader=False) # Reloader must be False for single-instance Assistant 