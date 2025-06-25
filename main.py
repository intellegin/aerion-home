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

    1. Listens for a wake word.
    2. Captures audio until silence.
    3. Transcribes the audio to text.
    4. Gets a response from the command handler (or LLM).
    5. Converts the response text to speech.
    """
    while True:
        # 1. Wait for the wake word
        if not listen_for_wake_word(keyword="Jarvis"):
            print("Wake word detection failed or was interrupted. Exiting.")
            break

        # 2. Capture and transcribe user's command
        print("Wake word detected, now listening for command...")
        try:
            user_input = capture_and_transcribe()
            if not user_input:
                print("No user input received or transcribed.")
                continue
        except Exception as e:
            print(f"An error occurred during transcription: {e}")
            continue

        # 3. Get response
        response = get_llm_response_or_execute_command(user_input)

        # 4. Speak the response
        if response:
            speak_async(response)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting…") 