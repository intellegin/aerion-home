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
import threading
import uuid

from command_handler import handle_command, SYSTEM_PROMPT, RestartRequest
from audio_in import capture_and_transcribe, listen_for_speech
from speak import speak_async, stop_speaking
from wake_word_listener import listen_for_wake_word
from database import log_message, create_chat_session


def main_loop():
    """
    The main operational loop of the assistant.
    This function is designed to be restartable.
    """
    # 1. Wait for the wake word
    if not listen_for_wake_word(keyword="jarvis"):
        print("Wake word detection failed or was interrupted. Exiting for now.")
        # We return here, and the outer loop will decide whether to restart.
        # This prevents a tight loop if the audio device is disconnected.
        return

    print("✅ Wake word detected. Starting conversation...")
    session_id = int(time.time())
    create_chat_session(session_id)
    
    # Initialize conversation history with the system prompt
    conversation_history = [SYSTEM_PROMPT]
    
    # 2. Conversation Loop
    while True:
        print("Listening for command...")
        user_input = capture_and_transcribe(max_seconds=15.0)

        # If transcription is empty or just whitespace, it's a timeout or misfire.
        if not user_input or not user_input.strip():
            print("… Conversation timed out or empty audio. Returning to wake word listening.")
            break  # Exit conversation loop, go back to waiting for wake word.

        log_message(session_id=session_id, content=user_input, direction="outbound")

        # Get response from LLM
        response = handle_command(user_input, conversation_history)
        
        if not response:
            print("LLM returned no response. Listening again.")
            continue # Listen for the next command

        log_message(session_id=session_id, content=response, direction="inbound")

        # Speak the response and listen for barge-in
        speaking_thread = speak_async(response)
        if not speaking_thread:
            # This can happen if a TTS method that doesn't support threading is used.
            # In this case, we can't do barge-in, so we just wait for it to finish implicitly.
            continue

        # --- Barge-in Logic ---
        time.sleep(0.2)  # Grace period for TTS audio to start playing.
        interrupted = False
        while speaking_thread.is_alive():
            if listen_for_speech(timeout=0.1): # Check for speech every 100ms
                print("🎤 Barge-in detected! Stopping TTS...")
                stop_speaking()
                interrupted = True
                break
            time.sleep(0.1)

        speaking_thread.join() # Wait for the thread to finish cleanly

        if interrupted:
            # If interrupted, immediately start listening for the next command
            continue


if __name__ == "__main__":
    while True:
        try:
            main_loop()
        except RestartRequest:
            print("📢 Restarting application as requested by user...")
            continue # Immediately loop back to the start of main_loop
        except KeyboardInterrupt:
            print("\nExiting application. Goodbye!")
            break
        except Exception as e:
            print(f"💥 An unexpected error occurred: {e}")
            print("🤕 Restarting the main loop in 5 seconds...")
            # Log the full traceback for debugging
            import traceback
            traceback.print_exc()
            time.sleep(5) 