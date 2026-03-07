"""Microphone capture and OpenAI Whisper transcription."""

import wave
import openai
import sounddevice
import numpy as np
from openai.types.audio import Transcription
from pathlib import Path

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
    with wave.open(AUDIO_PATH, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_int16.tobytes())
    try:
        with open(AUDIO_PATH, "rb") as audio_file:
            response: Transcription = openai.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
            )
        return response.text
    finally:
        Path(AUDIO_PATH).unlink(missing_ok=True)
