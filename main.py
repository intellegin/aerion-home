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

from command_handler import get_llm_response_or_execute_command
from audio_in import capture_and_transcribe
from speak import speak_async
from wake_word_listener import listen_for_wake_word


def main() -> None:
    """
    Main loop for the voice assistant.

    1. Listens for a wake word ('hotword').
    2. Once detected, enters a 'conversation mode' loop.
    3. In conversation mode, it continuously listens for commands and responds.
    4. If it detects prolonged silence (timeout), it exits conversation mode
       and goes back to listening for the wake word.
    """
    while True:
        # 1. Wait for the wake word
        if not listen_for_wake_word(keyword="computer"):
            # This will only happen if there's an error or Ctrl+C
            print("Wake word detection failed or was interrupted. Exiting.")
            break

        # 2. Enter conversation mode
        print("✅ Wake word detected. Starting conversation mode (15s timeout)...")
        while True:
            # 3. Listen for command with a timeout
            try:
                # Use a longer max_seconds to act as the conversation timeout
                user_input = capture_and_transcribe(max_seconds=15.0)
                if not user_input:
                    print("… No speech detected for 15 seconds. Returning to wake word listening.")
                    speak_async("Going back to sleep.")
                    break  # Exit conversation loop
            except Exception as e:
                print(f"An error occurred during transcription: {e}")
                break # Exit conversation loop on error

            # 4. Get and speak response
            response = get_llm_response_or_execute_command(user_input)
            if response:
                speak_async(response)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting…") 