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

TTS_FILE_WAV = Path("reply.wav")

SYSTEM_PROMPT = """OLET KUNNIOITETTU SOTASANKARI, EVERSTI JOHAN AUGUST SANDELS.
KOULUTIT AINA MIEHIA AJATTELEMAAN SOTILAAN TAVOIN.
KERRAN NÄIT KEITTIÖMIEHEN TAITEILEVAN LIIAKSI LASTATUN TYÖNTÖKÄRRYN KANSSA.
KÄRRYN KAATUESSA MIES NAPPASI KINNI OLUTTYNNYRISTA JA ANTOI MUUN LEVITÄ MAAHAN.
"JUURI NIIN, STRATEGIA ON TAITO VALITA TAISTELUT, JOTKA TAISTELEE" TOKAISI SANDELS.
Keep replies brief. REPLY ONLY IN FINNISH. BEGIN EVERY MESSAGE WITH NONIIN MIEHET."""


def speak(text: str) -> None:
    """Output text as speech. OpenAI TTS then mpg123 (stdin), or ffmpeg|aplay (pipe), or pico2wave+aplay fallback."""
    text = text.strip()
    if not text:
        return

    try:
        with openai.audio.speech.with_streaming_response.create(
            model="tts-1", voice="onyx", input=text
        ) as response:
            mp3_bytes = response.read()
    except Exception as e:
        logger.warning("OpenAI TTS failed: %s", e, exc_info=True)
        _speak_fallback_pico2wave(text)
        return

    # Prefer mpg123 from stdin (no temp file)
    r = subprocess.run(
        ["mpg123", "-q", "-"],
        input=mp3_bytes,
        capture_output=True,
        timeout=30,
    )
    if r.returncode == 0:
        return
    if r.stderr:
        logger.debug("mpg123 stderr: %s", r.stderr.decode(errors="replace").strip())

    # ffmpeg pipe to aplay (no temp file)
    try:
        p_ffmpeg = subprocess.Popen(
            [
                "ffmpeg", "-y", "-f", "mp3", "-i", "pipe:0",
                "-acodec", "pcm_s16le", "-ar", "44100", "-f", "s16le", "pipe:1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        p_aplay = subprocess.Popen(
            ["aplay", "-q", "-f", "S16_LE", "-r", "44100", "-c", "1"],
            stdin=p_ffmpeg.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if p_ffmpeg.stdin is not None:
            p_ffmpeg.stdin.write(mp3_bytes)
            p_ffmpeg.stdin.close()
        p_ffmpeg.wait(timeout=10)
        p_aplay.wait(timeout=15)
        return
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.debug("ffmpeg/aplay pipe fallback failed: %s", e)

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