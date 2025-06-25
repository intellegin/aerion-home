from __future__ import annotations

import os
import struct
import sys

import pvporcupine
import sounddevice as sd

# Ensure environment variables are loaded
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def listen_for_wake_word(keyword: str = "Jarvis") -> bool:
    """
    Listens for a specific wake word using pvporcupine.

    :param keyword: The wake word to listen for. Available options include:
                    "Americano", "Blueberry", "Bumblebee", "Computer",
                    "Grapefruit", "Grashopper", "Hey Google", "Hey Siri",
                    "Jarvis", "Okay Google", "Picovoice", "Porcupine", "Terminator".
    :return: True when the wake word is detected.
    """
    access_key = os.getenv("PICOVOICE_ACCESS_KEY")
    if not access_key:
        print("Error: PICOVOICE_ACCESS_KEY not set in environment.", file=sys.stderr)
        print("Please sign up for a free account at https://console.picovoice.ai/ to get your key.", file=sys.stderr)
        return False

    try:
        porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=[keyword]
        )
    except pvporcupine.PorcupineInvalidArgumentError as e:
        print(f"Error initializing Porcupine with keyword '{keyword}': {e}", file=sys.stderr)
        print(f"Available keywords: {pvporcupine.KEYWORDS}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error initializing Porcupine: {e}", file=sys.stderr)
        return False


    print(f"👂 Listening for wake word: '{keyword}'...")

    try:
        with sd.InputStream(
            samplerate=porcupine.sample_rate,
            channels=1,
            dtype='int16',
            blocksize=porcupine.frame_length,
        ) as stream:
            while True:
                pcm, _ = stream.read(porcupine.frame_length)
                pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

                result = porcupine.process(pcm)
                if result >= 0:
                    print(f"✅ Wake word '{keyword}' detected!")
                    # Play a sound to indicate listening
                    try:
                        from speak import speak_sync
                        # A non-verbal, quick sound is best. Let's use a simple "bing".
                        # This part might need adjustment depending on TTS capabilities.
                        # For now, we'll just announce it.
                        # speak_sync("Listening") # This can be slow, maybe a sound file is better
                    except Exception:
                        pass
                    return True

    except KeyboardInterrupt:
        print("Stopping wake word listener.")
    except Exception as e:
        print(f"An error occurred during audio streaming: {e}", file=sys.stderr)
    finally:
        if porcupine:
            porcupine.delete()
    
    return False
