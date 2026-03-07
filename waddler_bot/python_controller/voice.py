"""Microphone capture and OpenAI Whisper transcription."""

import logging
import wave
import struct
import openai
import sounddevice
from openai.types.audio import Transcription
from pathlib import Path
from logging import Logger

logger: Logger = logging.getLogger(__name__)

AUDIO_PATH = "audio.wav"
SAMPLE_RATE = 16000
CHUNK_SIZE = 512
SILENCE_THRESHOLD = 500   # RMS below this = silence; tune up/down as needed
SILENCE_DURATION = 1.5    # seconds of silence before stopping
MAX_DURATION = 15         # max recording seconds
MIC_DEVICE = 1            # USB mic card index


def rms(data: bytes) -> float:
    samples = struct.unpack_from(f"{len(data)//2}h", data)
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


def is_silent(data: bytes) -> bool:
    return rms(data) < SILENCE_THRESHOLD


def capture_and_transcribe() -> str:
    """Record until silence detected, write WAV, call Whisper, return text."""
    logger.info("listening...")

    chunks = []
    silent_chunks = 0
    max_chunks = int(MAX_DURATION * SAMPLE_RATE / CHUNK_SIZE)
    silence_chunks_needed = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE)
    started_speaking = False

    with sounddevice.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=CHUNK_SIZE,
        device=MIC_DEVICE,
    ) as stream:
        while len(chunks) < max_chunks:
            data, _ = stream.read(CHUNK_SIZE)
            chunk = bytes(data)
            chunks.append(chunk)

            if not is_silent(chunk):
                started_speaking = True
                silent_chunks = 0
            elif started_speaking:
                silent_chunks += 1
                if silent_chunks >= silence_chunks_needed:
                    logger.info("silence detected, stopping recording")
                    break

    if not started_speaking:
        logger.info("no speech detected")
        return ""

    frames_bytes = b"".join(chunks)

    with wave.open(AUDIO_PATH, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(frames_bytes)

    try:
        with open(AUDIO_PATH, "rb") as audio_file:
            response: Transcription = openai.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                language="fi",
            )
        text = response.text or ""
        logger.info("transcribed: %r", text if text else "(empty)")
        return text
    finally:
        Path(AUDIO_PATH).unlink(missing_ok=True)