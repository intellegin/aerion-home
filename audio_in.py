"""audio_in.py
Utility functions for recording audio from the default microphone and converting
speech to text using OpenAI Whisper.

Dependencies (see requirements.txt):
    - sounddevice
    - soundfile
    - numpy
    - openai
    - python-dotenv

This keeps the recording logic separate from business logic so that you can
swap in a different STT engine (e.g. on-device whisper.cpp) later.
"""
from __future__ import annotations

import os
import tempfile
from typing import Optional
import io
import wave

import numpy as np  # type: ignore
import sounddevice as sd  # type: ignore
import soundfile as sf  # type: ignore
import time
from collections import deque

try:
    # openai>=1.0 uses the Client class pattern.
    from openai import OpenAI  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "openai package is required but not installed. Did you run 'pip install -r requirements.txt'?"
    ) from exc

# Load environment variables (OPENAI_API_KEY, etc.) if present
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    # python-dotenv is optional but recommended; without it the user must set
    # environment variables manually.
    pass

# Speech-to-text recording utilities

import webrtcvad  # type: ignore

# Default parameters for recording
DEFAULT_FS = 16_000  # 16 kHz supported by webrtcvad and required by Leopard
DEFAULT_CHANNELS = 1  # Mono recording

# Minimum volume to trigger VAD check. Range 0.0–1.0.
# This can be tuned down if your mic is quiet, or up in a noisy environment.
# Set via `VAD_RMS_THRESHOLD` env var.
DEFAULT_RMS_THRESHOLD = 0.01

# VAD aggressiveness, 0-3. 3 is most aggressive against non-speech.
# Set via `VAD_AGGRESSIVENESS` env var.
DEFAULT_VAD_AGGRESSIVENESS = 1

DEFAULT_PROMPT = ""


def _rms(block: np.ndarray) -> float:
    """Root-mean-square energy of an audio block."""
    return float(np.sqrt(np.mean(np.square(block))))


def listen_for_speech(timeout: float) -> bool:
    """
    Listens to the microphone for a short period to detect any voice activity.

    :param timeout: How long to listen in seconds.
    :return: True if speech is detected, False otherwise.
    """
    vad = webrtcvad.Vad(int(os.getenv("VAD_AGGRESSIVENESS", DEFAULT_VAD_AGGRESSIVENESS)))
    rms_threshold = float(os.getenv("VAD_RMS_THRESHOLD", DEFAULT_RMS_THRESHOLD))
    fs = DEFAULT_FS
    frame_duration_ms = 30
    frame_length = int(fs * frame_duration_ms / 1000)
    
    start_time = time.time()
    
    try:
        with sd.InputStream(samplerate=fs, channels=DEFAULT_CHANNELS, dtype="int16", blocksize=frame_length) as stream:
            while time.time() - start_time < timeout:
                block, _ = stream.read(frame_length)
                block_float = block.astype(np.float32) / 32768.0
                
                if _rms(block_float) >= rms_threshold:
                    pcm_bytes = block.tobytes()
                    if vad.is_speech(pcm_bytes, fs):
                        return True
        return False
    except Exception as e:
        print(f"Error while listening for speech: {e}")
        return False


def capture_audio_stream(
    max_seconds: float = 10.0,
    fs: int = DEFAULT_FS,
    channels: int = DEFAULT_CHANNELS,
    *,
    rms_threshold: float = float(os.getenv("VAD_RMS_THRESHOLD", DEFAULT_RMS_THRESHOLD)),
    aggressiveness: int = int(os.getenv("VAD_AGGRESSIVENESS", DEFAULT_VAD_AGGRESSIVENESS)),
    silence_duration: float = 1.0,
) -> bytes | None:
    """
    Record microphone audio using VAD until silence is detected.
    Includes a pre-buffer to avoid clipping the start of speech.
    """
    vad = webrtcvad.Vad(aggressiveness)
    frame_duration_ms = 30  # VAD accepts 10, 20, or 30 ms
    frame_length = int(fs * frame_duration_ms / 1000)
    frames_needed_for_silence = int(silence_duration * 1000 / frame_duration_ms)

    # Buffer to store audio chunks before speech is detected
    pre_buffer = deque(maxlen=int(0.5 * fs / frame_length)) # ~0.5 seconds of pre-buffering
    
    recording_started = False
    chunks: list[np.ndarray] = []
    silent_frames = 0
    start_time = time.time()

    print("👂 Listening for command...")
    try:
        with sd.InputStream(
            samplerate=fs, channels=channels, dtype="int16", blocksize=frame_length
        ) as stream:
            while True:
                # Timeout check
                if not recording_started and time.time() - start_time > max_seconds:
                    print(f"⏱️  No speech detected for {max_seconds}s, timing out.")
                    return None

                block, _ = stream.read(frame_length)
                
                is_speech = False
                # VAD check only if volume is high enough
                if _rms(block.astype(np.float32) / 32768.0) >= rms_threshold:
                    if vad.is_speech(block.tobytes(), fs):
                        is_speech = True

                if is_speech:
                    if not recording_started:
                        recording_started = True
                        print("🎙️  Recording started...")
                        try: # Stop any TTS
                            from speak import stop_speaking
                            stop_speaking()
                        except Exception: pass
                        
                        # Add the pre-buffered audio to the recording
                        chunks.extend(list(pre_buffer))
                        pre_buffer.clear()
                    
                    chunks.append(block)
                    silent_frames = 0
                else:
                    if not recording_started:
                        # Keep filling the pre-buffer
                        pre_buffer.append(block)
                    else:
                        # We are recording, and this is a silent frame
                        chunks.append(block) # record the silence too
                        silent_frames += 1
                        if silent_frames >= frames_needed_for_silence:
                            print("🛑 Detected silence, stopping recording.")
                            break
    except KeyboardInterrupt:
        raise SystemExit("Recording interrupted by user.") from None

    if not chunks:
        return None

    recording = np.concatenate(chunks, axis=0)
    buffer = io.BytesIO()
    sf.write(buffer, recording, fs, format='WAV', subtype='PCM_16')
    buffer.seek(0)
    return buffer.read()


def capture_and_transcribe(max_seconds: float = 15.0) -> str:
    """Record until silence using VAD and immediately get its transcription."""
    audio_data = capture_audio_stream(max_seconds=max_seconds)
    if not audio_data:
        return ""

    # Check for minimum audio length before processing
    try:
        with io.BytesIO(audio_data) as buffer:
            with sf.SoundFile(buffer, 'r') as sound_file:
                duration = sound_file.frames / sound_file.samplerate
                if duration < 0.2:  # Leopard has a minimum audio length
                    print(f"🎤 Audio too short ({duration:.2f}s), skipping transcription.")
                    return ""
    except Exception as e:
        print(f"Could not read audio duration: {e}. Skipping transcription.")
        return ""
    
    # Use the new on-device transcription
    from transcribe_leopard import transcribe_with_leopard
    return transcribe_with_leopard(audio_data)


class Transcriber:
    """A wrapper for the OpenAI Whisper API for server-side processing."""
    def __init__(self):
        self.client = OpenAI()

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        """
        Transcribes raw PCM audio data by first wrapping it in a WAV container,
        then sending it to the Whisper API.

        :param audio_bytes: The raw 16-bit 16kHz mono PCM audio data.
        :return: The transcribed text, or an empty string on failure.
        """
        if not audio_bytes or len(audio_bytes) < 1000: # Basic check for empty/trivial audio
            print("Audio data is empty or too short to transcribe.")
            return ""

        print(f"Transcribing {len(audio_bytes)} bytes of audio via Whisper API...")
        
        try:
            # Create a proper WAV file in memory to send to the API
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)      # Mono
                wf.setsampwidth(2)      # 16-bit PCM
                wf.setframerate(16000)  # 16kHz sample rate
                wf.writeframes(audio_bytes)
            
            wav_buffer.name = "input.wav"
            wav_buffer.seek(0)

            # Send the in-memory WAV file to the Whisper API
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=wav_buffer,
                language="en"
            )
            print(f"Transcription result: '{transcript.text}'")
            return transcript.text
        except Exception as e:
            # This could be an API error, an issue with the audio data, etc.
            print(f"An error occurred during transcription: {e}")
            return "" 