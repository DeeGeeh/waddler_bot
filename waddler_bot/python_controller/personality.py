"""Personality pipeline: async loop for voice, vision, GPT-4o, TTS. Never touches motors."""

import asyncio
import subprocess
from pathlib import Path

import openai
import voice
import vision

TTS_FILE = Path("reply.mp3")
TTS_FILE_WAV = Path("reply.wav")


def speak(text: str) -> None:
    """Output text as speech. OpenAI TTS (mpg123) or pico2wave + aplay fallback."""
    if not (text or text.strip()):
        return
    text = text.strip()
    try:
        with openai.audio.speech.with_streaming_response.create(
            model="tts-1", voice="onyx", input=text
        ) as response:
            TTS_FILE.write_bytes(response.read())
        subprocess.run(["mpg123", "-q", str(TTS_FILE)], check=False, capture_output=True)
    except Exception:
        # Offline fallback (Linux/Pi: pico2wave + aplay)
        try:
            subprocess.run(
                ["pico2wave", "-w", str(TTS_FILE_WAV), text],
                check=True,
                capture_output=True,
            )
            subprocess.run(["aplay", "-q", str(TTS_FILE_WAV)], check=False, capture_output=True)
        except Exception:
            pass


async def personality_loop() -> None:
    """Run voice + vision personality; never calls motor code."""
    iteration = 0
    while True:
        # Vision: observe surroundings every ~10 seconds and narrate
        if iteration % 10 == 0:
            try:
                comment = vision.observe_and_comment()
                if comment and comment.strip():
                    speak(comment)
            except Exception:
                pass

        # Voice: listen for a question and respond
        try:
            heard = voice.capture_and_transcribe()
            if heard and heard.strip():
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a witty, curious robot. Keep replies brief.",
                        },
                        {"role": "user", "content": heard},
                    ],
                )
                reply = response.choices[0].message.content
                if reply:
                    speak(reply)
        except Exception:
            pass

        iteration += 1
        await asyncio.sleep(1)
