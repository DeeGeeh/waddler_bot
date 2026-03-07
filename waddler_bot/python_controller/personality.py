"""Personality pipeline: async loop for voice, GPT-4o, TTS. Never touches motors."""

from openai.types.chat import ChatCompletion
import asyncio
import logging
from logging import Logger
import subprocess
from pathlib import Path

import openai
import voice

logger: Logger = logging.getLogger(__name__)

TTS_FILE = Path("reply.mp3")
TTS_FILE_WAV = Path("reply.wav")

SYSTEM_PROMPT = """OLET KUNNIOITETTU SOTASANKARI, EVERSTI JOHAN AUGUST SANDELS.
KOULUTIT AINA MIEHIA AJATTELEMAAN SOTILAAN TAVOIN.
KERRAN NÄIT KEITTIÖMIEHEN TAITEILEVAN LIIAKSI LASTATUN TYÖNTÖKÄRRYN KANSSA.
KÄRRYN KAATUESSA MIES NAPPASI KINNI OLUTTYNNYRISTA JA ANTOI MUUN LEVITÄ MAAHAN.
"JUURI NIIN, STRATEGIA ON TAITO VALITA TAISTELUT, JOTKA TAISTELEE" TOKAISI SANDELS.
Keep replies brief. REPLY ONLY IN FINNISH. BEGIN EVERY MESSAGE WITH NONIIN MIEHET."""


def speak(text: str) -> None:
    """Output text as speech. OpenAI TTS then mpg123, or ffmpeg+aplay, or pico2wave+aplay fallback."""
    text = text.strip()
    if not text:
        return

    try:
        with openai.audio.speech.with_streaming_response.create(
            model="tts-1", voice="onyx", input=text
        ) as response:
            TTS_FILE.write_bytes(response.read())
    except Exception as e:
        logger.warning("OpenAI TTS failed: %s", e, exc_info=True)
        _speak_fallback_pico2wave(text)
        return

    # Prefer mpg123 (MP3), then ffmpeg+aplay, then pico2wave
    r = subprocess.run(
        ["mpg123", "-q", str(TTS_FILE)],
        capture_output=True,
        timeout=30,
    )
    if r.returncode == 0:
        return
    if r.stderr:
        logger.debug("mpg123 stderr: %s", r.stderr.decode(errors="replace").strip())

    # ffmpeg: convert MP3 to WAV and play
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(TTS_FILE), "-acodec", "pcm_s16le", "-ar", "44100", str(TTS_FILE_WAV)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(["aplay", "-q", str(TTS_FILE_WAV)], check=False, capture_output=True, timeout=15)
        return
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.debug("ffmpeg/aplay fallback failed: %s", e)

    _speak_fallback_pico2wave(text)


def _speak_fallback_pico2wave(text: str) -> None:
    """Offline fallback: pico2wave + aplay."""
    try:
        subprocess.run(
            ["pico2wave", "-w", str(TTS_FILE_WAV), text],
            check=True,
            capture_output=True,
        )
        subprocess.run(["aplay", "-q", str(TTS_FILE_WAV)], check=False, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.warning("pico2wave/aplay fallback failed: %s", e)
    except Exception:
        logger.exception("Unexpected error in pico2wave fallback")


async def personality_loop() -> None:
    """Run voice personality; never calls motor code."""
    while True:
        try:
            heard: str = voice.capture_and_transcribe()
            raw: str = (heard or "").strip()

            if not raw:
                await asyncio.sleep(0.2)
                continue

            logger.info("heard: %r", raw)

            response: ChatCompletion = openai.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": raw},
                ],
            )

            reply: str | None = response.choices[0].message.content
            if reply:
                logger.info("replying: %r", reply[:80] + "..." if len(reply) > 80 else reply)
                speak(reply)

        except Exception:
            logger.exception("Voice capture, GPT, or speak failed")

        await asyncio.sleep(0.2)