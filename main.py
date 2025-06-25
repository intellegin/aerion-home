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

import command_handler
from audio_in import capture_and_transcribe
from speak import speak_sync


def main() -> None:
    print("Aerion AI (VOICE MODE) — Press Ctrl+C to quit.\n")

    while True:
        # Record → Transcribe (auto-stop on silence)
        text = capture_and_transcribe().lower()

        if not text.strip():
            print("(Silence detected.)\n")
            time.sleep(0.5)
            continue

        # Business logic
        reply = command_handler.handle_command(text)

        # Output: print + speak
        print(f"You (voice): {text}\nAerion : {reply}\n")
        speak_sync(reply)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting…") 