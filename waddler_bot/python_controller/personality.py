"""Personality pipeline: async loop for voice, vision, GPT-4o, TTS. Never touches motors."""

from openai.types.chat import ChatCompletion
import asyncio
import logging
from logging import Logger
import subprocess
from pathlib import Path

import openai
import voice
import vision

logger: Logger = logging.getLogger(__name__)

TTS_FILE = Path("reply.mp3")
TTS_FILE_WAV = Path("reply.wav")


def speak(text: str) -> None:
    """Output text as speech. OpenAI TTS (mpg123) or pico2wave + aplay fallback."""
    text = text.strip()
    if not text:
        return
        
    try:
        with openai.audio.speech.with_streaming_response.create(
            model="tts-1", voice="onyx", input=text
        ) as response:
            TTS_FILE.write_bytes(response.read())
        subprocess.run(["mpg123", "-q", str(TTS_FILE)], check=False, capture_output=True)
    except Exception as e:
        logger.warning(
            "OpenAI TTS or mpg123 failed, trying pico2wave fallback: %s", e, exc_info=True
        )
        # Offline fallback (Linux/Pi: pico2wave + aplay)
        try:
            subprocess.run(
                ["pico2wave", "-w", str(TTS_FILE_WAV), text],
                check=True,
                capture_output=True,
            )
            subprocess.run(["aplay", "-q", str(TTS_FILE_WAV)], check=False, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            logger.warning(
                "pico2wave/aplay fallback failed (missing or failed): %s", e, exc_info=True
            )
        except Exception:
            logger.exception("Unexpected error in pico2wave fallback")
            raise

async def personality_loop() -> None:
    """Run voice + vision personality; never calls motor code."""
    iteration = 0
    while True:
        # Vision: observe surroundings every ~10 seconds and narrate
        if iteration % 10 == 0:
            try:
                comment: str = vision.observe_and_comment()
                if comment and comment.strip():
                    speak(comment)
            except Exception:
                logger.exception("Vision observe_and_comment failed")

        # Voice: listen for a question and respond
        try:
            heard: str = voice.capture_and_transcribe()
            if heard and heard.strip():
                response: ChatCompletion = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content":   """OLET KUNNIOITETTU SOTASANKARI,
                                            EVERSTI JOHAN AUGUST
                                            SANDELS KOULUTIT AINA MIEHIA AJATTELEMAAN
                                            SOTILAAN TAVOIN. KERRAN NÄIT KEITTIÖMIEHEN TAITEILEVAN LIIAKSI LASTATUN
                                            TYÖNTÖKÄRRYN KANSSA.
                                            KÄRRYN KAATUESSA MIES NAPPASI KINNI OLUTTYNNY
                                            RISTA JA ANTOI MUUN LEVITÄ
                                            MAAHAN. "JUURI NIIN,
                                            STRATEGIA ON TAITO VALITA TAISTELUT, JOTKA TAISTELEE:
                                            TOKAISI SANDELS. Keep replies brief.",
                                            """,
                        },
                        {"role": "user", "content": heard},
                    ],
                )
                reply: str | None = response.choices[0].message.content
                if reply:
                    speak(reply)
        except Exception:
            logger.exception("Voice capture, GPT, or speak failed")

        iteration += 1
        await asyncio.sleep(1)
