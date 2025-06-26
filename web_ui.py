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

app = Flask(__name__)
app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME')
CORS(app)
app.secret_key = 'super_secret_key_for_flashing' # Required for flashing messages
socketio = SocketIO(app, cors_allowed_origins="*")

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
    global main_process
    
    current_voice_name = "Unknown"
    try:
        voices = get_cached_voices()
        if voices:
            settings = get_settings()
            current_voice_id = settings.get("voice_id") or os.getenv("VOICE_NAME") or DEFAULT_VOICE
            voice_map = {v['id']: v['name'] for v in voices}
            current_voice_name = voice_map.get(current_voice_id, "Default")
    except Exception as e:
        print(f"Could not determine current voice name: {e}")

    app_status = 'running' if main_process and main_process.poll() is None else 'stopped'
    
    # Emit the status to all clients
    socketio.emit('status_update', {'status': app_status, 'voice_name': current_voice_name})

@socketio.on('connect')
def handle_connect():
    """Send initial status to a newly connected client."""
    print("Client connected. Sending initial status.")
    emit_status_update()

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
    
    python_executable = sys.executable
    main_script_path = os.path.join(os.path.dirname(__file__), 'main.py')
    
    print(f"Starting assistant process: {python_executable} {main_script_path}")
    main_process = subprocess.Popen([
        python_executable, main_script_path,
        '--socket-port', str(5001) # Use the same port as the web UI
    ])
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

def run_assistant_thread():
    """A function to run the main assistant logic in a thread."""
    from main import main as assistant_main
    print("Assistant thread started.")
    try:
        assistant_main(web_ui_socket_port=5001)
    except Exception as e:
        print(f"Error in assistant thread: {e}")

if __name__ == '__main__':
    import threading

    # Start the assistant logic in a background thread
    # This makes the assistant start automatically with the web UI
    assistant_thread = threading.Thread(target=run_assistant_thread, daemon=True)
    assistant_thread.start()

    print("Starting Flask web UI with SocketIO...")
    print("Open your browser and go to http://127.0.0.1:5001")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, use_reloader=True) 