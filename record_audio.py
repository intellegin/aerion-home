
import sounddevice as sd
import soundfile as sf

def record_audio(filename='input.wav', duration=4, samplerate=16000):
    print("Recording audio...")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait()
    sf.write(filename, recording, samplerate)
    return filename
