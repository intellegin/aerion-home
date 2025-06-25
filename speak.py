"""speak.py
Cross-platform helper to convert text to speech.

Priority order:
1. Use the `pyttsx3` library if installed (offline, works on macOS, Windows,
   and Linux with `nsss`, `sapi5`, or `espeak` back-ends).
2. Fallback to the native `say` command on macOS.
3. Fallback to `espeak`/`espeak-ng` on Linux.

If none of these methods are available, the function prints a warning.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import os
import io
from typing import NoReturn, Optional
import threading

# OpenAI client for TTS
try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None  # type: ignore

# ElevenLabs client for TTS
try:
    from elevenlabs import generate as _eleven_generate, play as _eleven_play, set_api_key as _eleven_set_api_key  # type: ignore
except ImportError:  # pragma: no cover
    _eleven_generate = _eleven_play = _eleven_set_api_key = None  # type: ignore


# ---------------------------------------------------------------------------
# Global state to manage interruption
# ---------------------------------------------------------------------------

_engine = None  # pyttsx3 engine instance (optional)
_process: Optional[subprocess.Popen] = None  # subprocess handle for say/espeak
_lock = threading.Lock()

# Default voice name if VOICE_NAME not supplied
DEFAULT_VOICE = "4YYIPFl9wE5c4L2eu2Gb"

# OpenAI voice choices
_OPENAI_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}


def _current_voice() -> str:
    """Return the desired voice name, falling back to DEFAULT_VOICE."""
    return os.getenv("VOICE_NAME", DEFAULT_VOICE)


def stop_speaking() -> None:
    """Immediately halt any ongoing TTS playback."""
    with _lock:
        global _process, _engine

        # Stop pyttsx3
        try:
            if _engine is not None:
                _engine.stop()  # type: ignore[attr-defined]
        except Exception:
            pass

        # Terminate external process
        if _process and _process.poll() is None:
            try:
                _process.terminate()
            except Exception:
                pass
        _process = None


def _speak_pyttsx3_async(text: str) -> threading.Thread | None:
    """Speak via pyttsx3 in a background thread."""
    try:
        import pyttsx3  # type: ignore

        def _worker():
            with _lock:
                global _engine
                if _engine is None:
                    _engine = pyttsx3.init()
                eng = _engine
                # Set voice if requested
                voice_name = _current_voice()
                for v in eng.getProperty("voices"):
                    if voice_name.lower() in v.name.lower():
                        eng.setProperty("voice", v.id)
                        break
            eng.say(text)
            eng.runAndWait()
        
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread
    except Exception:
        return None


def _speak_with_command_async(cmd: list[str], *, add_voice: bool = False) -> bool:
    """Launch command asynchronously; store process for interruption."""
    if shutil.which(cmd[0]) is None:
        return False

    with _lock:
        global _process
        try:
            if add_voice:
                voice_arg = _current_voice()
                cmd = [cmd[0], "-v", voice_arg] + cmd[1:]
            _process = subprocess.Popen(cmd)
            return True
        except Exception:
            _process = None
            return False


def _speak_openai_sync(text: str, voice: str) -> bool:
    """Use OpenAI TTS if available. Returns True if successful."""
    if OpenAI is None or voice.lower() not in _OPENAI_VOICES:
        return False

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False

    try:
        client = OpenAI(api_key=api_key)  # type: ignore[arg-type]

        response = client.audio.speech.create(
            model="tts-1",
            voice=voice.lower(),
            input=text,
            response_format="wav",
        )

        import soundfile as sf  # local import
        import sounddevice as sd

        wav_bytes = response.content  # type: ignore[attr-defined]
        with io.BytesIO(wav_bytes) as bio:
            data, samplerate = sf.read(bio, dtype="float32")
        sd.play(data, samplerate)
        sd.wait()
        return True
    except Exception as exc:
        print(f"[OpenAI TTS error] {exc}")
        return False


def _speak_eleven_sync(text: str, voice: str) -> bool:
    """Use ElevenLabs TTS if API key and library are available. Returns True on success."""

    if _eleven_generate is None and _eleven_play is None:
        # Try newer v2+ SDK programmatic path
        try:
            from elevenlabs.client import ElevenLabs  # type: ignore
        except Exception:
            return False

        api_key = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            return False

        try:
            client = ElevenLabs(api_key=api_key)  # type: ignore[arg-type]

            # If the provided voice looks like a name (not a 22-char id) resolve to id
            voice_id = voice
            if len(voice) < 22:
                try:
                    all_voices = client.voices.search().voices  # type: ignore[attr-defined]
                    for v in all_voices:
                        if v.name.lower() == voice.lower():  # type: ignore[attr-defined]
                            voice_id = v.voice_id  # type: ignore[attr-defined]
                            break
                except Exception:
                    pass

            audio = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            from elevenlabs import play as _new_play  # type: ignore
            _new_play(audio)  # type: ignore[arg-type]
            return True
        except Exception as exc:  # pragma: no cover
            print(f"[ElevenLabs v2 TTS error] {exc}")
            return False

    # Legacy SDK path (v0.x – v1.x)
    if _eleven_generate is None:
        return False

    api_key = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return False

    try:
        _eleven_set_api_key(api_key)  # type: ignore[arg-type]
        audio_data = _eleven_generate(text=text, voice=voice)  # type: ignore[arg-type]
        _eleven_play(audio_data)  # type: ignore[arg-type]
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[ElevenLabs legacy TTS error] {exc}")
        return False


def _speak_eleven_async(text: str) -> threading.Thread | None:
    """Speak using ElevenLabs in a background thread (non-blocking)."""
    # Quick check for API key before starting thread.
    if not (os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")):
        return None

    # Check for either old or new SDK
    try:
        from elevenlabs.client import ElevenLabs as _ElevenLabsClient
        sdk_v2_present = True
    except ImportError:
        sdk_v2_present = False
    
    if _eleven_generate is None and not sdk_v2_present:
        return None

    def _worker():
        """Worker thread to call the synchronous speak method."""
        _speak_eleven_sync(text, _current_voice())

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def speak_async(text: str) -> threading.Thread | None:
    """
    Speak *text* without blocking and return the thread.
    Call `stop_speaking()` to interrupt.
    """
    # First stop anything that might still be playing
    stop_speaking()

    # Prefer ElevenLabs if available
    if (thread := _speak_eleven_async(text)):
        return thread

    # Fallback to OpenAI
    if OpenAI is not None:
        def _worker():
            _speak_openai_sync(text, _current_voice())
        
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    # Fallback to system commands
    if sys.platform == "darwin":
        if _speak_with_command_async(["say", text], add_voice=True):
            return None  # Cannot return thread for subprocess
    elif sys.platform.startswith("linux"):
        if _speak_with_command_async(["espeak", text], add_voice=True):
            return None # Cannot return thread for subprocess

    # Final fallback to pyttsx3
    if (thread := _speak_pyttsx3_async(text)):
        return thread

    print("Warning: No TTS engine available.")
    return None


# Backward-compat name kept
def speak_text(text: str) -> None:  # noqa: D401
    """Compatibility wrapper for older calls."""
    speak_async(text)


# ---------------------------------------------------------------------------
# Blocking speech helper
# ---------------------------------------------------------------------------

def speak_sync(text: str) -> None:
    """Speak *text* and block until finished (no interruption)."""

    stop_speaking()

    voice = _current_voice()

    # Prefer ElevenLabs if configured
    if _speak_eleven_sync(text, voice):
        return

    # Next try OpenAI TTS
    if _speak_openai_sync(text, voice):
        return

    if sys.platform.startswith("darwin"):
        subprocess.run(["say", "-v", voice, text])
        return

    # Try pyttsx3
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        voice_name = voice
        for v in engine.getProperty("voices"):
            if voice_name.lower() in v.name.lower():
                engine.setProperty("voice", v.id)
                break
        engine.say(text)
        engine.runAndWait()
        return
    except Exception:
        pass

    # Fallback espeak
    if shutil.which("espeak"):
        subprocess.run(["espeak", text])
        return

    print("(TTS unavailable — install pyttsx3, or 'say'/'espeak'.)")

