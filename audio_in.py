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

DEFAULT_PROMPT = (
    "The speaker is issuing informal English commands to an AI companion. "
    "Avoid interpreting short utterances as abbreviations like FEMA. "
    "Common words include 'yeah', 'bro', 'dude', 'hello'. Respond with the exact transcription, no additional text."
)


def _rms(block: np.ndarray) -> float:
    """Root-mean-square energy of an audio block."""
    return float(np.sqrt(np.mean(np.square(block))))


def record_to_wav(
    max_seconds: float = 10.0,
    fs: int = DEFAULT_FS,
    channels: int = DEFAULT_CHANNELS,
    *,
    aggressiveness: int = 2,  # 0–3; 2 is balanced
    silence_duration: float = 0.8,
) -> str:
    """Record microphone audio until `silence_duration` of quiet using WebRTC-VAD."""

    print("🎙️  Speak now (auto-stop on pause)… Press Ctrl+C to abort.")

    vad = webrtcvad.Vad(aggressiveness)

    frame_duration_ms = 30  # VAD accepts 10, 20, or 30 ms
    frame_length = int(fs * frame_duration_ms / 1000)  # samples per frame

    frames_needed_for_silence = int(silence_duration * 1000 / frame_duration_ms)

    silent_frames = 0
    speech_frames = 0  # consecutive voiced frames before start
    recording_started = False
    chunks: list[np.ndarray] = []
    start_time = time.time()

    try:
        with sd.InputStream(
            samplerate=fs,
            channels=channels,
            dtype="int16",
            blocksize=frame_length,
        ) as stream:
            while True:
                block, _ = stream.read(frame_length)

                pcm_bytes = block.tobytes()
                is_speech = vad.is_speech(pcm_bytes, fs)

                if is_speech:
                    if not recording_started:
                        speech_frames += 1
                        if speech_frames >= 3:  # need 3 consecutive speech frames (~90 ms)
                            recording_started = True
                            # Cut off any current TTS right when voice starts
                            try:
                                from speak import stop_speaking

                                stop_speaking()
                            except Exception:
                                pass
                            # backfill the buffered speech frames
                            chunks.extend([block])
                            silent_frames = 0
                    else:
                        chunks.append(block)
                        silent_frames = 0
                else:
                    speech_frames = 0  # reset
                    if recording_started:
                        silent_frames += 1
                        if silent_frames >= frames_needed_for_silence:
                            print("🛑 Detected silence, stopping recording.")
                            break

                # Safety net
                if time.time() - start_time > max_seconds:
                    print("⏱️  Reached max recording time, stopping.")
                    break
    except KeyboardInterrupt:
        raise SystemExit("Recording interrupted by user.") from None

    if not chunks:
        # No speech captured; create an empty silent block to avoid crash
        chunks.append(np.zeros((frame_length, channels), dtype="int16"))

    recording = np.concatenate(chunks, axis=0)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, recording, fs, subtype="PCM_16")
    # Return path for transcription; will be deleted afterwards
    return tmp.name


def transcribe_with_openai(
    wav_path: str,
    model: str = "whisper-1",
    *,
    prompt: Optional[str] = DEFAULT_PROMPT,
) -> str:
    """Send *wav_path* to OpenAI Whisper and return the transcribed text.

    Uses the openai>=1.0 client interface.
    """

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Export it or add it to a .env file.")

    client = OpenAI(api_key=api_key)  # type: ignore

    # Skip if audio too short (<0.1 s)
    import soundfile as _sf
    frames, sr = _sf.info(wav_path).frames, _sf.info(wav_path).samplerate
    if frames / sr < 0.1:
        os.remove(wav_path)
        return ""

    with open(wav_path, "rb") as fp:
        print("🕊️  Transcribing with OpenAI Whisper …")
        transcription = client.audio.transcriptions.create(
            model=model,
            file=fp,
            prompt=prompt,
            response_format="text",
            language="en",
        )

    os.remove(wav_path)  # cleanup temp file

    # The new client returns the text directly (when response_format="text").
    text: str = transcription  # type: ignore[assignment]
    print(f"✍️  Transcribed text: {text}")
    return text


def capture_and_transcribe() -> str:
    """Record until silence using VAD and immediately get its transcription."""
    wav = record_to_wav()
    return transcribe_with_openai(wav) 