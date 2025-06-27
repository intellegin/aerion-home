"""main.py
Voice-only chat loop for Pi-5 AI Communicator.

Workflow:
    1. Record a short chunk of audio from microphone.
    2. Transcribe it with OpenAI Whisper.
    3. Feed transcription to command_handler.handle_command.
    4. Display the response (text).  You can later hook up TTS here.

Usage:
    python main.py

Press Ctrl+C to exit.
"""
from __future__ import annotations

import time
import json
import threading
import os
import sys
import asyncio
import uuid
import argparse
from dotenv import load_dotenv
from functools import partial

from command_handler import handle_command, SYSTEM_PROMPT, RestartRequest
from audio_in import VAD, Transcriber
from speak import speak_async, stop_speaking, play_activation_sound, play_deactivation_sound
from wake_word_listener import WakeWordDetector
from database import log_message, create_chat_session
from socket_client import SocketClient, sio_instance

load_dotenv()

# Get the process ID once when the script starts.
process_id = os.getpid()

# --- Settings ---
def get_settings():
    """Reads settings from the settings.json file."""
    try:
        with open('settings.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# --- Constants ---
WAKE_WORD_SENSITIVITY = 0.6
VAD_SENSITIVITY = 3
RECORD_TIMEOUT_SEC = 10
SPEECH_TIMEOUT_SEC = 3.0 

# --- State Management ---
class AssistantState:
    IDLE = 1
    LISTENING_FOR_WAKE_WORD = 2
    LISTENING_FOR_COMMAND = 3
    PROCESSING_COMMAND = 4
    SPEAKING = 5

state = AssistantState.IDLE
speaking_thread = None
conversation_history = [SYSTEM_PROMPT]
session_id = None

stop_listening_flag = threading.Event()

def on_wake_word_detected(speaker_device_id: int | None = None):
    """Callback function for when the wake word is detected."""
    global state, session_id, conversation_history
    if state == AssistantState.LISTENING_FOR_WAKE_WORD:
        play_activation_sound(device_id=speaker_device_id)
        print("Wake word detected! Listening for command...")
        sio_instance.update_assistant_state("listening")
        state = AssistantState.LISTENING_FOR_COMMAND
        
        if not session_id:
            session_id = int(process_id)
            create_chat_session(session_id)
            conversation_history = [SYSTEM_PROMPT]

def reset_to_idle(speaker_device_id: int | None = None):
    """Resets the assistant's state back to idle."""
    global state, speaking_thread, session_id
    print("Resetting to idle state.")
    sio_instance.update_assistant_state("idle")
    play_deactivation_sound(device_id=speaker_device_id)
    if speaking_thread and speaking_thread.is_alive():
        stop_speaking()
        speaking_thread.join()
    state = AssistantState.LISTENING_FOR_WAKE_WORD
    speaking_thread = None
    # Do not reset session_id here, to allow for conversation continuation.

async def main(web_ui_socket_port=None):
    """The main application loop."""
    global state, speaking_thread, conversation_history

    if web_ui_socket_port:
        sio_instance.start(port=web_ui_socket_port)

    # --- Initialization ---
    settings = get_settings()
    wake_word = settings.get("wake_word", "jarvis").lower()
    
    mic_device_id_str = settings.get("mic_device_id")
    mic_device_id = None
    if mic_device_id_str:
        try:
            mic_device_id = int(mic_device_id_str)
        except (ValueError, TypeError):
            print(f"Warning: Invalid microphone device ID '{mic_device_id_str}'. Using default.")

    speaker_device_id_str = settings.get("speaker_device_id")
    speaker_device_id = None
    if speaker_device_id_str:
        try:
            speaker_device_id = int(speaker_device_id_str)
        except (ValueError, TypeError):
            print(f"Warning: Invalid speaker device ID '{speaker_device_id_str}'. Using default.")

    # --- Validate Microphone Device ---
    if mic_device_id is not None:
        try:
            import sounddevice as sd
            device_info = sd.query_devices(mic_device_id)
            if device_info['max_input_channels'] == 0:
                print(f"Warning: Device ID {mic_device_id} ('{device_info['name']}') is not an input device. Falling back to default.")
                mic_device_id = None
        except Exception as e:
            print(f"Error validating microphone device ID {mic_device_id}: {e}. Falling back to default.")
            mic_device_id = None

    # --- Validate Speaker Device ---
    if speaker_device_id is not None:
        try:
            import sounddevice as sd
            device_info = sd.query_devices(speaker_device_id)
            if device_info['max_output_channels'] == 0:
                print(f"Warning: Device ID {speaker_device_id} ('{device_info['name']}') is not an output device. Falling back to default.")
                speaker_device_id = None
        except Exception as e:
            print(f"Error validating speaker device ID {speaker_device_id}: {e}. Falling back to default.")
            speaker_device_id = None

    # Create a callback that includes the speaker_device_id
    on_detection_callback = partial(on_wake_word_detected, speaker_device_id=speaker_device_id)

    wake_word_detector = WakeWordDetector(
        keyword=wake_word, 
        sensitivity=WAKE_WORD_SENSITIVITY, 
        on_wake_word=on_detection_callback,
        device_index=mic_device_id
    )
    
    vad = VAD(
        sensitivity=VAD_SENSITIVITY, 
        device_index=mic_device_id,
        on_realtime_transcription=sio_instance.update_user_speech
    )
    transcriber = Transcriber()
    
    state = AssistantState.LISTENING_FOR_WAKE_WORD
    print(f"Assistant is up and running. Listening for '{wake_word}'...")

    # --- Main Loop ---
    while not stop_listening_flag.is_set():
        try:
            if state == AssistantState.LISTENING_FOR_WAKE_WORD:
                wake_word_detector.start()
                # The wake word detector is non-blocking and uses a callback,
                # so we need to wait here. A sleep loop is simple and effective.
                while state == AssistantState.LISTENING_FOR_WAKE_WORD:
                    await asyncio.sleep(0.1)

            elif state == AssistantState.LISTENING_FOR_COMMAND:
                # The VAD uses the selected microphone.
                audio_data = vad.record_until_silence(
                    record_timeout=RECORD_TIMEOUT_SEC, 
                    speech_timeout=SPEECH_TIMEOUT_SEC
                )
                
                if not audio_data:
                    print("No command heard, returning to wake word listening.")
                    reset_to_idle(speaker_device_id=speaker_device_id)
                    continue

                state = AssistantState.PROCESSING_COMMAND
                sio_instance.update_assistant_state("processing")
                print("Transcribing command...")
                user_input = transcriber.transcribe_audio(audio_data)
                
                # Send the final transcription to the UI
                if user_input:
                    sio_instance.emit('final_transcription', {'text': user_input})

                if not user_input or not user_input.strip():
                    print("Transcription is empty, ignoring.")
                    reset_to_idle(speaker_device_id=speaker_device_id)
                    continue

                print(f"USER: {user_input}")
                log_message(session_id, user_input, "outbound")
                conversation_history.append({"role": "user", "content": user_input})

                try:
                    response = handle_command(user_input, conversation_history)
                except RestartRequest:
                    reset_to_idle(speaker_device_id=speaker_device_id)
                    continue

                if not response:
                    print("No response from command handler, going back to listening.")
                    state = AssistantState.LISTENING_FOR_WAKE_WORD
                    continue

                state = AssistantState.SPEAKING
                sio_instance.update_assistant_state("speaking")
                print(f"ASSISTANT: {response}")
                log_message(session_id, response, "inbound")
                conversation_history.append({"role": "assistant", "content": response})

                # The speak_async function returns the thread that is playing the audio.
                audio_thread = speak_async(response, device_id=speaker_device_id)
                
                # Wait for the audio to finish playing before resetting.
                if audio_thread:
                    audio_thread.join()
                
                # If the assistant asked a question, listen for the user's answer.
                # Otherwise, reset to wait for the wake word.
                if response.strip().endswith('?'):
                    print("Assistant asked a question. Listening for user's response...")
                    sio_instance.update_assistant_state("listening")
                    state = AssistantState.LISTENING_FOR_COMMAND
                else:
                    reset_to_idle(speaker_device_id=speaker_device_id)

            else:
                 await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print("Shutting down assistant.")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            reset_to_idle(speaker_device_id=speaker_device_id)

    # --- Cleanup ---
    wake_word_detector.stop()
    sio_instance.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the voice assistant.")
    parser.add_argument(
        '--socket-port',
        type=int,
        help='Port for the web UI socket connection (optional)'
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(web_ui_socket_port=args.socket_port))
    except KeyboardInterrupt:
        print("Assistant stopped by user.") 