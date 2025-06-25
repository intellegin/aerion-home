from __future__ import annotations

import os
import pvleopard
import soundfile as sf
import io

def transcribe_with_leopard(wav_bytes: bytes) -> str:
    """
    Transcribes audio using the on-device Picovoice Leopard engine.

    :param wav_bytes: The audio data in WAV format (bytes).
    :return: The transcribed text, converted to lowercase.
    """
    access_key = os.getenv("PICOVOICE_ACCESS_KEY")
    if not access_key:
        raise ValueError("PICOVOICE_ACCESS_KEY environment variable not set.")

    leopard = None
    try:
        leopard = pvleopard.create(access_key=access_key)
        
        # Leopard processes a list of raw PCM data, not WAV bytes.
        # We use soundfile to read the PCM data from the in-memory WAV file.
        with io.BytesIO(wav_bytes) as wav_buffer:
            pcm, samplerate = sf.read(wav_buffer, dtype='int16')

        # This check is a safeguard; it should pass if audio_in.py is correct.
        if samplerate != leopard.sample_rate:
            raise ValueError(f"Incorrect sample rate: got {samplerate}, expected {leopard.sample_rate}")

        transcript, _ = leopard.process(pcm)
        
        # Standardize to lowercase for easier command processing
        transcript_lower = transcript.lower()
        print(f"✍️  Leopard transcribed text: '{transcript_lower}'")
        return transcript_lower

    except Exception as e:
        print(f"Error during Leopard transcription: {e}")
        return ""
    finally:
        if leopard:
            leopard.delete() 