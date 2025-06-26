from __future__ import annotations

import os
import struct
import sys
import threading

import pvporcupine
import sounddevice as sd

# Ensure environment variables are loaded
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class WakeWordDetector:
    def __init__(self, keyword="computer", sensitivity=0.5, on_wake_word=None, device_index=None):
        self.keyword = keyword
        self.sensitivity = sensitivity
        self.on_wake_word = on_wake_word
        self.device_index = device_index
        self.porcupine = None
        self.stream = None
        self.is_listening = False
        self.thread = None

    def _init_porcupine(self):
        try:
            access_key = os.getenv("PICOVOICE_ACCESS_KEY")
            if not access_key:
                raise ValueError("PICOVOICE_ACCESS_KEY environment variable not set.")
            self.porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=[self.keyword],
                sensitivities=[self.sensitivity]
            )
        except Exception as e:
            print(f"Error initializing Porcupine: {e}")
            raise

    def _run(self):
        if not self.porcupine:
            self._init_porcupine()

        try:
            self.stream = sd.InputStream(
                samplerate=self.porcupine.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.porcupine.frame_length,
                device=self.device_index
            )
            self.stream.start()
            print(f"👂 Listening for wake word: '{self.keyword}'...")
            
            while self.is_listening:
                pcm, _ = self.stream.read(self.porcupine.frame_length)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                result = self.porcupine.process(pcm)

                if result >= 0:
                    print(f"✅ Wake word '{self.keyword}' detected!")
                    if self.on_wake_word:
                        self.on_wake_word()
                    # Once detected, stop listening by breaking the loop.
                    # The 'finally' block will handle cleanup.
                    break

        except Exception as e:
            print(f"An error occurred in wake word listener: {e}")
        finally:
            if self.stream:
                self.stream.stop()
                self.stream.close()
            if self.porcupine:
                self.porcupine.delete()
                self.porcupine = None
            # Ensure the state is updated so a new listener can be started.
            self.is_listening = False

    def start(self):
        if not self.is_listening:
            self.is_listening = True
            self.thread = threading.Thread(target=self._run)
            self.thread.start()

    def stop(self):
        if self.is_listening:
            self.is_listening = False
            if self.thread:
                self.thread.join()
                self.thread = None
