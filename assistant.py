from __future__ import annotations

import time
import threading
from enum import Enum, auto

from command_handler import handle_command, SYSTEM_PROMPT, RestartRequest
from audio_in import Transcriber # Use our new, lean transcriber
from speak import speak_async, stop_speaking
from database import log_message, create_chat_session

# The new, simpler state machine for the web UI
class AssistantState(Enum):
    """Represents the current state of the assistant."""
    IDLE = auto()               # Not active
    LISTENING = auto()          # Actively listening for a command
    PROCESSING = auto()         # Transcribing and thinking
    SPEAKING = auto()           # Replying to the user


class Assistant:
    """
    The core logic of the voice assistant, refactored for a web-based,
    serverless environment.
    """
    LISTENING_TIMEOUT_SEC = 10.0 # Timeout if no speech is ever detected
    SILENCE_THRESHOLD_SEC = 2.0  # How long of a pause indicates the end of a command

    def __init__(self, on_state_change=None):
        self.state = AssistantState.IDLE
        self.transcriber = Transcriber()
        self.on_state_change = on_state_change
        
        # Conversation state
        self.session_id = None
        self.conversation_history = []
        self._command_audio_buffer = [] # Buffer for storing command audio
        self._last_audio_time = None
        self._speaking_thread = None
    
    def _set_state(self, new_state: AssistantState):
        """Updates the assistant's state and notifies the UI."""
        if self.state == new_state:
            return
        print(f"ASSISTANT STATE: {self.state.name} -> {new_state.name}")
        self.state = new_state
        if self.on_state_change:
            self.on_state_change(self.state)

        # Reset buffers and timers when we start listening
        if new_state == AssistantState.LISTENING:
            self._command_audio_buffer = []
            self._last_audio_time = time.time()

    def start(self):
        """Starts the assistant by listening for a command."""
        if self.state != AssistantState.IDLE:
            return
        
        self.session_id = int(time.time())
        create_chat_session(self.session_id)
        self.conversation_history = [SYSTEM_PROMPT]
        self._set_state(AssistantState.LISTENING)

    def stop(self):
        """Stops the assistant and returns it to the idle state."""
        if self._speaking_thread and self._speaking_thread.is_alive():
            stop_speaking()
        self._set_state(AssistantState.IDLE)

    def process_audio_chunk(self, audio_chunk):
        """Processes an audio chunk from the browser, managing the conversation state."""
        if self.state != AssistantState.LISTENING:
            return # Only process audio when in the listening state

        self._last_audio_time = time.time()
        self._command_audio_buffer.append(audio_chunk)

    def check_for_silence(self):
        """
        Periodically called by the server to check if the user has stopped speaking.
        """
        if self.state != AssistantState.LISTENING:
            return
        
        silence_duration = time.time() - self._last_audio_time
        
        # If there's a long enough pause, process the command
        if self._command_audio_buffer and silence_duration > self.SILENCE_THRESHOLD_SEC:
            print(f"Silence detected ({silence_duration:.2f}s). Processing command...")
            self._process_command()
        # If there's been no audio at all for the max duration, time out
        elif not self._command_audio_buffer and silence_duration > self.LISTENING_TIMEOUT_SEC:
            print("Listening timed out. Returning to IDLE.")
            self.stop()

    def _process_command(self):
        """Transcribes and handles the buffered command audio."""
        if not self._command_audio_buffer:
            return

        self._set_state(AssistantState.PROCESSING)
        
        full_audio_data = b"".join(self._command_audio_buffer)
        self._command_audio_buffer = [] # Clear buffer

        user_input = self.transcriber.transcribe_audio(full_audio_data)

        if not user_input or not user_input.strip():
            print("… Transcription was empty. Returning to listening.")
            self._set_state(AssistantState.LISTENING)
            return

        log_message(session_id=self.session_id, content=user_input, direction="outbound")
        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
            response = handle_command(user_input, self.conversation_history)
        except RestartRequest:
            print("Restart requested. For now, just going back to idle.")
            self.stop() 
            return
        except Exception as e:
            print(f"Error in command handling: {e}")
            response = "I'm sorry, I encountered an error. Please try again."

        if not response:
            print("LLM returned no response. Returning to listening.")
            self._set_state(AssistantState.LISTENING)
            return
        
        log_message(session_id=self.session_id, content=response, direction="inbound")
        self.conversation_history.append({"role": "assistant", "content": response})

        self._speak_response(response)
    
    def _speak_response(self, text):
        """Handles the text-to-speech part of the response."""
        self._set_state(AssistantState.SPEAKING)
        
        def speak_and_return_to_listen():
            # Stop any previous speech just in case
            stop_speaking() 
            speaking_thread = speak_async(text)
            if speaking_thread:
                speaking_thread.join()
            
            # After speaking, go back to idle. The user can click the button to talk again.
            if self.state == AssistantState.SPEAKING:
                 self.stop()

        self._speaking_thread = threading.Thread(target=speak_and_return_to_listen)
        self._speaking_thread.start() 