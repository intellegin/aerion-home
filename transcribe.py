
import vosk
import sys
import soundfile as sf
import json

def transcribe_audio(file_path='input.wav', model_path='models/vosk-model-en-us'):
    model = vosk.Model(model_path)
    with sf.SoundFile(file_path) as audio_file:
        rec = vosk.KaldiRecognizer(model, audio_file.samplerate)
        data = audio_file.read(dtype='int16')
        rec.AcceptWaveform(data)
        result = json.loads(rec.FinalResult())
        return result.get("text", "")
