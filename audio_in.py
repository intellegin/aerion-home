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
DEFAULT_FS = 48_000  # 48 kHz supported by webrtcvad and most hardware
DEFAULT_CHANNELS = 1  # Mono recording

# Minimum volume to trigger VAD check. Range 0.0–1.0.
# This can be tuned down if your mic is quiet, or up in a noisy environment.
# Set via `VAD_RMS_THRESHOLD` env var.
DEFAULT_RMS_THRESHOLD = 0.02

# VAD aggressiveness, 0-3. 3 is most aggressive against non-speech.
# Set via `VAD_AGGRESSIVENESS` env var.
DEFAULT_VAD_AGGRESSIVENESS = 2

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
    silence_duration: float = 0.8,
) -> bytes | None:
    """Record microphone audio until silence and return it as a WAV bytes stream."""

    vad = webrtcvad.Vad(aggressiveness)

    frame_duration_ms = 30  # VAD accepts 10, 20, or 30 ms
    frame_length = int(fs * frame_duration_ms / 1000)  # samples per frame

    frames_needed_for_silence = int(silence_duration * 1000 / frame_duration_ms)

    silent_frames = 0
    speech_frames = 0  # consecutive voiced frames before start
    recording_started = False
    chunks: list[np.ndarray] = []
    last_speech_time = time.time()

    try:
        with sd.InputStream(
            samplerate=fs,
            channels=channels,
            dtype="int16",
            blocksize=frame_length,
        ) as stream:
            while True:
                block, _ = stream.read(frame_length)

                # Convert block to normalized float32 for RMS calculation
                block_float = block.astype(np.float32) / 32768.0

                # 1. Volume check
                if _rms(block_float) < rms_threshold:
                    is_speech = False
                else:
                    # 2. VAD check (only if loud enough)
                    pcm_bytes = block.tobytes()
                    is_speech = vad.is_speech(pcm_bytes, fs)

                if is_speech:
                    if not recording_started:
                        speech_frames += 1
                        if speech_frames >= 3:  # need 3 consecutive speech frames (~90 ms)
                            recording_started = True
                            print("🎙️  Recording started...")
                            # Cut off any current TTS right when voice starts
                            try:
                                from speak import stop_speaking

                                stop_speaking()
                            except Exception:
                                pass
                            # backfill the buffered speech frames
                            chunks.extend([block])
                            silent_frames = 0
                            last_speech_time = time.time()
                    else:
                        chunks.append(block)
                        silent_frames = 0
                        last_speech_time = time.time()
                else:
                    speech_frames = 0  # reset
                    if recording_started:
                        silent_frames += 1
                        if silent_frames >= frames_needed_for_silence:
                            print("🛑 Detected short silence, stopping recording.")
                            break

                # Timeout check
                if time.time() - last_speech_time > max_seconds:
                    print(f"⏱️  No speech for {max_seconds}s, stopping.")
                    # If we weren't even recording, it's a true timeout.
                    if not recording_started:
                        return None
                    break
    except KeyboardInterrupt:
        raise SystemExit("Recording interrupted by user.") from None

    if not chunks:
        # No speech captured
        print("No speech detected.")
        return None

    recording = np.concatenate(chunks, axis=0)

    # Instead of writing to a file, write to an in-memory buffer
    buffer = io.BytesIO()
    sf.write(buffer, recording, fs, format='WAV', subtype='PCM_16')
    buffer.seek(0)
    return buffer.read()


def transcribe_with_openai(
    wav_bytes: bytes,
    model: str = "whisper-1",
    *,
    prompt: Optional[str] = DEFAULT_PROMPT,
) -> str:
    """Send *wav_bytes* to OpenAI Whisper and return the transcribed text.

    Uses the openai>=1.0 client interface.
    """
    # --- Check for minimum audio length before sending to OpenAI ---
    try:
        with io.BytesIO(wav_bytes) as buffer:
            with sf.SoundFile(buffer, 'r') as sound_file:
                # Get duration from metadata
                duration = sound_file.frames / sound_file.samplerate
                if duration < 0.1:
                    print(f"🎤 Audio too short ({duration:.2f}s), skipping transcription.")
                    return ""
    except Exception as e:
        print(f"Could not read audio duration: {e}. Skipping transcription.")
        return ""


    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Export it or add it to a .env file.")

    client = OpenAI(api_key=api_key)  # type: ignore

    # Use an in-memory file-like object
    with io.BytesIO(wav_bytes) as audio_stream:
        # Pass the stream along with a tuple specifying the filename
        file_tuple = ("audio.wav", audio_stream)
        print("🕊️  Transcribing with OpenAI Whisper …")
        transcription = client.audio.transcriptions.create(
            model=model,
            file=file_tuple,
            prompt=prompt,
            response_format="text",
            language="en",
        )

    # The new client returns the text directly (when response_format="text").
    text: str = transcription  # type: ignore[assignment]
    print(f"✍️  Transcribed text: {text}")
    return text


def capture_and_transcribe(max_seconds: float = 15.0) -> str:
    """Record until silence using VAD and immediately get its transcription."""
    audio_data = capture_audio_stream(max_seconds=max_seconds)
    if not audio_data:
        return ""
    return transcribe_with_openai(audio_data) 