import socketio

# Global Socket.IO client
sio = socketio.Client()

@sio.event
def connect():
    print("Successfully connected to the web UI Socket.IO server.")

@sio.event
def connect_error(data):
    print(f"Failed to connect to the web UI Socket.IO server: {data}")

@sio.event
def disconnect():
    print("Disconnected from the web UI Socket.IO server.")

def navigate_ui(tab_name: str):
    """Emits a navigation event to the web UI."""
    print(f"Attempting to navigate UI to tab: {tab_name}")
    if sio.connected:
        sio.emit('navigate', {'tab': tab_name})
        return f"UI navigation command sent for tab '{tab_name}'."
    else:
        # This message is for the LLM, not the user.
        return "Cannot navigate UI: not connected to the server." 