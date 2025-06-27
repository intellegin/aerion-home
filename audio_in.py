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
import io
import time
from collections import deque

import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad
from transcribe_leopard import transcribe_with_leopard

class VAD:
    def __init__(self, sensitivity=1, device_index=None, on_realtime_transcription=None):
        self.sensitivity = sensitivity
        self.device_index = device_index
        self.on_realtime_transcription = on_realtime_transcription
        self.vad = webrtcvad.Vad(sensitivity)
        self.sample_rate = 16000
        self.frame_duration_ms = 30
        self.frame_length = int(self.sample_rate * self.frame_duration_ms / 1000)
        self.transcriber = Transcriber() # Internal transcriber for real-time updates

    def _rms(self, block):
        return np.sqrt(np.mean(np.square(block, dtype=np.float64)))

    def record_until_silence(self, record_timeout=10.0, speech_timeout=2.0):
        rms_threshold = 0.01
        silence_frames_needed = int(speech_timeout * 1000 / self.frame_duration_ms)
        
        pre_buffer = deque(maxlen=int(0.5 * self.sample_rate / self.frame_length))
        recording_started = False
        chunks = []
        silent_frames = 0
        start_time = time.time()

        print("👂 Listening for command...")
        try:
            device_info = sd.query_devices(self.device_index, 'input')
            channels = int(device_info.get('max_input_channels', 1))

            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=channels,
                dtype="int16",
                blocksize=self.frame_length,
                device=self.device_index,
            ) as stream:
                while True:
                    if not recording_started and time.time() - start_time > record_timeout:
                        print(f"⏱️ No speech detected for {record_timeout}s, timing out.")
                        return None

                    block, _ = stream.read(self.frame_length)
                    
                    is_speech = False
                    if self._rms(block.astype(np.float32) / 32768.0) >= rms_threshold:
                        if self.vad.is_speech(block.tobytes(), self.sample_rate):
                            is_speech = True

                    if is_speech:
                        if not recording_started:
                            recording_started = True
                            print("🎙️ Recording started...")
                            try:
                                from speak import stop_speaking
                                stop_speaking()
                            except Exception: pass
                            chunks.extend(list(pre_buffer))
                            pre_buffer.clear()
                        
                        chunks.append(block)
                        silent_frames = 0

                    else:
                        if not recording_started:
                            pre_buffer.append(block)
                        else:
                            chunks.append(block)
                            silent_frames += 1
                            if silent_frames >= silence_frames_needed:
                                print("🛑 Detected silence, stopping recording.")
                                break
        except KeyboardInterrupt:
            raise SystemExit("Recording interrupted by user.") from None

        if not chunks:
            return None

        recording = np.concatenate(chunks, axis=0)
        buffer = io.BytesIO()
        sf.write(buffer, recording, self.sample_rate, format='WAV', subtype='PCM_16')
        buffer.seek(0)
        return buffer.read()


class Transcriber:
    def __init__(self):
        # This class no longer needs arguments
        pass

    def transcribe_audio(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""

        try:
            with io.BytesIO(audio_data) as buffer:
                with sf.SoundFile(buffer, 'r') as sound_file:
                    duration = sound_file.frames / sound_file.samplerate
                    if duration < 0.2:
                        print(f"🎤 Audio too short ({duration:.2f}s), skipping transcription.")
                        return ""
        except Exception as e:
            print(f"Could not read audio duration: {e}. Skipping transcription.")
            return ""
        
        return transcribe_with_leopard(audio_data) 