"""Microphone capture and OpenAI Whisper transcription."""

import openai
import sounddevice
import numpy as np
import scipy.io.wavfile as wav

AUDIO_PATH = "audio.wav"
SAMPLE_RATE = 16000
DURATION_SEC = 3


def capture_and_transcribe() -> str:
    """Record ~3s at 16 kHz, write WAV, call Whisper API, return transcribed text."""
    samples = int(DURATION_SEC * SAMPLE_RATE)
    audio = sounddevice.rec(samples, samplerate=SAMPLE_RATE, channels=1, dtype=np.float32)
    sounddevice.wait()
    # Whisper expects 16-bit PCM
    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    wav.write(AUDIO_PATH, SAMPLE_RATE, audio_int16)
    response = openai.audio.transcriptions.create(
        file=open(AUDIO_PATH, "rb"),
        model="whisper-1",
    )
    return response.text
