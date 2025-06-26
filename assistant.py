from __future__ import annotations

import time
import threading
from enum import Enum, auto

from command_handler import handle_command, SYSTEM_PROMPT, RestartRequest
from audio_in import VAD, Transcriber, AudioRecorder
from speak import speak_async, stop_speaking
from wake_word_listener import PorcupineListener
from database import log_message, create_chat_session


class AssistantState(Enum):
    """Represents the current state of the assistant."""
    IDLE = auto()               # Doing nothing, waiting to be started
    LISTENING_FOR_WAKE_WORD = auto()
    LISTENING_FOR_COMMAND = auto()
    PROCESSING_COMMAND = auto()
    SPEAKING = auto()


class Assistant:
    """
    The core logic of the voice assistant.
    This class is responsible for the main state machine and processing audio.
    """

    def __init__(self, on_state_change=None):
        self.state = AssistantState.IDLE
        self.recorder = AudioRecorder()
        self.vad = VAD()
        self.wake_word_detector = PorcupineListener(
            on_detection=self._on_wake_word_detected,
            keywords=["computer"]
        )
        self.transcriber = Transcriber()
        self.on_state_change = on_state_change  # Callback to notify UI of state changes
        
        # Conversation state
        self.session_id = None
        self.conversation_history = []
        self._command_audio_buffer = [] # Buffer for storing command audio
        self._speech_started = False
        self._last_speech_time = None
    
    def _set_state(self, new_state: AssistantState):
        """Updates the assistant's state and notifies the UI."""
        if self.state == new_state:
            return
        print(f"ASSISTANT STATE: {self.state.name} -> {new_state.name}")
        self.state = new_state
        if self.on_state_change:
            self.on_state_change(self.state)

        # Reset buffers and timers when entering a listening state
        if new_state == AssistantState.LISTENING_FOR_COMMAND:
            self._command_audio_buffer = []
            self._speech_started = False
            self._last_speech_time = time.time() # Start timer to detect timeout

    def start(self):
        """Starts the assistant by listening for the wake word."""
        if self.state != AssistantState.IDLE:
            return
        self._set_state(AssistantState.LISTENING_FOR_WAKE_WORD)

    def stop(self):
        """Stops the assistant and returns it to the idle state."""
        self._set_state(AssistantState.IDLE)

    def _on_wake_word_detected(self):
        """Callback executed when the wake word is detected."""
        if self.state != AssistantState.LISTENING_FOR_WAKE_WORD:
            return
        print("✅ Wake word detected.")
        self.session_id = int(time.time())
        create_chat_session(self.session_id)
        self.conversation_history = [SYSTEM_PROMPT]
        self._set_state(AssistantState.LISTENING_FOR_COMMAND)

    def process_audio_chunk(self, audio_chunk):
        """
        This is the main entry point for audio data from the browser.
        It manages the state machine for the conversation.
        """
        if self.state == AssistantState.IDLE:
            return # Do nothing if we're not active

        elif self.state == AssistantState.LISTENING_FOR_WAKE_WORD:
            self.wake_word_detector.process(audio_chunk)
        
        elif self.state == AssistantState.LISTENING_FOR_COMMAND:
            self._handle_command_audio(audio_chunk)
        
        elif self.state == AssistantState.SPEAKING:
            # While speaking, we can listen for barge-in
            self._handle_barge_in(audio_chunk)

    def _handle_command_audio(self, audio_chunk):
        """Processes audio when listening for a user's command."""
        is_speech = self.vad.is_speech(audio_chunk)
        
        # If we detect speech, start buffering
        if is_speech:
            self._speech_started = True
            self._last_speech_time = time.time()
            self._command_audio_buffer.append(audio_chunk)

        # If we have started capturing speech and then there's a silence
        elif self._speech_started and not is_speech:
            silence_duration = time.time() - self._last_speech_time
            if silence_duration > self.vad.silence_threshold_sec:
                print("Silence detected, processing command...")
                self._process_command()

        # Timeout logic: if no speech is detected for a while
        elif not self._speech_started:
            if time.time() - self._last_speech_time > 10.0: # 10-second timeout
                print("No command detected, returning to wake word listening.")
                self._set_state(AssistantState.LISTENING_FOR_WAKE_WORD)

    def _process_command(self):
        """Transcribes and handles the buffered command audio."""
        if not self._command_audio_buffer:
            print("Process command called with no audio, returning to wake word listening.")
            self._set_state(AssistantState.LISTENING_FOR_WAKE_WORD)
            return

        self._set_state(AssistantState.PROCESSING_COMMAND)
        
        full_audio_data = b"".join(self._command_audio_buffer)
        self._command_audio_buffer = [] # Clear buffer

        user_input = self.transcriber.transcribe_audio(full_audio_data)

        if not user_input or not user_input.strip():
            print("… Transcription was empty. Listening for wake word again.")
            self._set_state(AssistantState.LISTENING_FOR_WAKE_WORD)
            return

        log_message(session_id=self.session_id, content=user_input, direction="outbound")
        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
            response = handle_command(user_input, self.conversation_history)
        except RestartRequest:
            print("Restart requested. For now, just going back to idle.")
            self.stop() # Or handle restart more gracefully
            return
        except Exception as e:
            print(f"Error in command handling: {e}")
            response = "I'm sorry, I encountered an error. Please try again."

        if not response:
            print("LLM returned no response. Listening for wake word.")
            self._set_state(AssistantState.LISTENING_FOR_WAKE_WORD)
            return
        
        log_message(session_id=self.session_id, content=response, direction="inbound")
        self.conversation_history.append({"role": "assistant", "content": response})

        self._speak_response(response)
    
    def _speak_response(self, text):
        """Handles the text-to-speech part of the response."""
        self._set_state(AssistantState.SPEAKING)
        
        # We run TTS in a separate thread so the main thread (Socket.IO) isn't blocked.
        # This thread will transition the state back to listening when it's done.
        def speak_and_return_to_listen():
            speaking_thread = speak_async(text)
            if speaking_thread:
                speaking_thread.join() # Wait for speech to finish
            
            # Check if state is still SPEAKING (i.e., not interrupted by barge-in)
            if self.state == AssistantState.SPEAKING:
                 self._set_state(AssistantState.LISTENING_FOR_WAKE_WORD)

        threading.Thread(target=speak_and_return_to_listen).start()

    def _handle_barge_in(self, audio_chunk):
        """Listens for user speech while the assistant is talking."""
        if self.vad.is_speech(audio_chunk):
            print("Barge-in detected!")
            stop_speaking() # Stop the currently playing TTS
            # Immediately transition to listening for the next command
            self._set_state(AssistantState.LISTENING_FOR_COMMAND) 