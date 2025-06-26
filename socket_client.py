import socketio
import threading
import time
from typing import Dict, Any

class SocketClient:
    def __init__(self):
        self.sio = socketio.Client()
        self.port = None
        self.thread = None
        self.is_connected = False
        self._register_handlers()

    def _register_handlers(self):
        @self.sio.event
        def connect():
            self.is_connected = True
            print("Successfully connected to the web UI Socket.IO server.")

        @self.sio.event
        def connect_error(data):
            print(f"Failed to connect to the web UI Socket.IO server: {data}")
            self.is_connected = False

        @self.sio.event
        def disconnect():
            print("Disconnected from the web UI Socket.IO server.")
            self.is_connected = False

    def _run(self):
        # Attempt to connect with retries
        while not self.is_connected:
            try:
                self.sio.connect(f'http://127.0.0.1:{self.port}')
                break  # Exit loop on successful connection
            except socketio.exceptions.ConnectionError as e:
                print(f"Connection failed: {e}. Retrying in 5 seconds...")
                time.sleep(5)
        
        if self.is_connected:
            self.sio.wait()

    def start(self, port=5001):
        self.port = port
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        if self.sio.connected:
            self.sio.disconnect()
        if self.thread and self.thread.is_alive():
            self.thread.join()

    def emit(self, event: str, data: Dict[str, Any]):
        """A generic event emitter."""
        if self.is_connected:
            self.sio.emit(event, data)

    def navigate_ui(self, tab_name: str):
        """Emits a navigation event to the web UI."""
        print(f"Attempting to navigate UI to tab: {tab_name}")
        if self.is_connected:
            self.sio.emit('navigate', {'tab': tab_name})
            return f"UI navigation command sent for tab '{tab_name}'."
        else:
            return "Cannot navigate UI: not connected to the server."

    def update_user_speech(self, text: str):
        """Sends the user's transcribed speech to the UI."""
        if self.is_connected:
            self.sio.emit('user_speech_update', {'text': text})

    def update_ai_speech(self, text: str):
        """Sends the AI's speech to the UI."""
        if self.is_connected:
            self.sio.emit('ai_speech_update', {'text': text})
        
    def update_assistant_state(self, state: str):
        """Updates the assistant's state on the UI (e.g., 'listening', 'processing')."""
        if self.is_connected:
            self.sio.emit('assistant_state_update', {'state': state})

# Global instance for convenience
sio_instance = SocketClient() 