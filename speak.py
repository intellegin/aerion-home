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
import json
from typing import NoReturn, Optional
import threading
from socket_client import sio_instance

# Conditionally import ElevenLabs config to avoid errors if not present
try:
    from config import ELEVENLABS_API_KEY, VOICE_ID, ANNOUNCER_VOICE_ID, TTS_MODEL
except ImportError:
    ELEVENLABS_API_KEY = None
    VOICE_ID = None
    ANNOUNCER_VOICE_ID = None
    TTS_MODEL = None

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

# --- Globals ---
stop_flag = threading.Event()


def _get_current_settings():
    """Reads settings from the settings file, returns empty dict if not found."""
    try:
        with open('settings.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _current_voice() -> str:
    """
    Return the desired voice name, checking settings and environment variables.
    Priority: 1. Settings File, 2. Environment Var, 3. Hardcoded Default
    """
    settings = _get_current_settings()
    return settings.get("voice_id") or os.getenv("VOICE_NAME") or DEFAULT_VOICE


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


def _speak_openai_sync(text: str, voice: str, device: int | None = None) -> bool:
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
        sd.play(data, samplerate, device=device)
        sd.wait()
        return True
    except Exception as exc:
        print(f"[OpenAI TTS error] {exc}")
        return False


def _speak_eleven_sync(text: str, voice: str, device: int | None = None) -> bool:
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
            import sounddevice as sd
            
            # Get the default device info if no device is specified
            if device is None:
                _new_play(audio)
            else:
                # This is a bit of a workaround to play to a specific device.
                # elevenlabs.play doesn't directly support it in all versions,
                # so we decode it and play it with sounddevice.
                import io
                import soundfile as sf
                
                # Convert list of bytes to a byte stream
                byte_stream = io.BytesIO()
                for chunk in audio:
                    byte_stream.write(chunk)
                byte_stream.seek(0)
                
                data, samplerate = sf.read(byte_stream, dtype='float32')
                sd.play(data, samplerate, device=device)
                sd.wait()

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
        
        # elevenlabs.play doesn't support device selection in the legacy SDK,
        # so we play it manually with sounddevice if a device is specified.
        if device is None:
            _eleven_play(audio_data)  # type: ignore[arg-type]
        else:
            import io
            import sounddevice as sd
            from pydub import AudioSegment

            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            samples = audio_segment.get_array_of_samples()
            
            sd.play(samples, audio_segment.frame_rate, device=device)
            sd.wait()
            
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[ElevenLabs legacy TTS error] {exc}")
        return False


def _speak_eleven_async(text: str, device_id: int | None) -> threading.Thread | None:
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
        _speak_eleven_sync(text, _current_voice(), device=device_id)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def speak_async(text: str, device_id: int | None = None) -> threading.Thread | None:
    """
    Synthesize and speak the given text in a background thread.
    This function will select the best available TTS method.
    It returns the thread so the caller can `join()` it if needed.
    """
    # Notify the UI that the AI is speaking and what it's saying
    sio_instance.update_ai_speech(text)

    # Prioritize ElevenLabs if the key is set
    if os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY"):
        return _speak_eleven_async(text, device_id)

    voice = _current_voice()

    # Priority 2: OpenAI if an OpenAI voice is selected
    if voice in _OPENAI_VOICES:
        def _worker():
            _speak_openai_sync(text, voice, device=device_id)
        
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    # Priority 3: pyttsx3 for local, offline TTS
    thread = _speak_pyttsx3_async(text)
    if thread:
        return thread

    # Fallback to system commands
    def _system_worker():
        speak_sync(text)
    
    thread = threading.Thread(target=_system_worker, daemon=True)
    thread.start()
    return thread


def speak_text(text: str) -> None:  # noqa: D401
    """DEPRECATED: Use speak_async for non-blocking or speak_sync for blocking."""
    speak_sync(text)


def play_activation_sound(device_id: int | None = None) -> None:
    """
    Plays a short, non-blocking activation sound.
    """
    def _worker():
        try:
            import numpy as np
            import sounddevice as sd

            samplerate = 44100
            frequency = 880.0  # A pleasant A5 note
            duration = 0.15   # seconds
            volume = 0.5

            t = np.linspace(0., duration, int(samplerate * duration), endpoint=False)
            amplitude = np.iinfo(np.int16).max * volume
            data = amplitude * np.sin(2. * np.pi * frequency * t)

            sd.play(data.astype(np.int16), samplerate, device=device_id)
            sd.wait()
        except Exception as e:
            print(f"Could not play activation sound: {e}")

    # Run in a separate thread so it doesn't block the main flow
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def play_deactivation_sound(device_id: int | None = None) -> None:
    """
    Plays a short, non-blocking deactivation sound.
    """
    def _worker():
        try:
            import numpy as np
            import sounddevice as sd

            samplerate = 44100
            frequency = 440.0  # A lower A4 note
            duration = 0.15
            volume = 0.4

            t = np.linspace(0., duration, int(samplerate * duration), endpoint=False)
            amplitude = np.iinfo(np.int16).max * volume
            data = amplitude * np.sin(2. * np.pi * frequency * t)

            # A quick fade out to make it sound softer
            fade_out = np.linspace(1., 0., int(samplerate * duration), endpoint=False)
            data *= fade_out

            sd.play(data.astype(np.int16), samplerate, device=device_id)
            sd.wait()
        except Exception as e:
            print(f"Could not play deactivation sound: {e}")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# Blocking speech helper
# ---------------------------------------------------------------------------

def speak_sync(text: str) -> None:
    """
    Speak text synchronously (blocks until speech is finished).
    Chooses the best TTS engine available.
    """
    voice = _current_voice()

    # Priority 1: ElevenLabs
    if len(voice) > 5 and voice not in _OPENAI_VOICES:
        if _speak_eleven_sync(text, voice):
            return

    # Priority 2: OpenAI
    if voice in _OPENAI_VOICES:
        if _speak_openai_sync(text, voice):
            return

    # Fallback to system commands
    if sys.platform == "darwin":
        # On macOS, 'say' is reliable
        _speak_with_command_async(["say", text], add_voice=True)
    elif sys.platform.startswith("linux"):
        # On Linux, 'espeak' is common
        _speak_with_command_async(["espeak", "-v", "en-us", text])
    else:
        print("Warning: No TTS engine available for this platform.")
        # Attempt pyttsx3 as a last resort, but synchronously
        try:
            import pyttsx3  # type: ignore
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass


def get_elevenlabs_voices():
    """Returns a list of available ElevenLabs voices."""
    api_key = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("Warning: ELEVEN_API_KEY not set. Cannot fetch voices.")
        return []
    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        voices = client.voices.get_all().voices
        # Format for display: [{"id": "...", "name": "..."}]
        return [{"id": v.voice_id, "name": v.name} for v in voices]
    except Exception as e:
        print(f"Could not fetch ElevenLabs voices: {e}")
        return []

