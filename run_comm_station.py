
from wake_word_listener import listen_for_wake_word
from record_audio import record_audio
from transcribe import transcribe_audio
from command_handler import handle_command
from speak import speak_text

def main():
    while True:
        if listen_for_wake_word():
            audio_file = record_audio()
            text = transcribe_audio(audio_file)
            print(f"User said: {text}")
            response = handle_command(text)
            speak_text(response)

if __name__ == "__main__":
    main()
