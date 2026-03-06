"""Start both pipelines in separate threads: movement (joystick server) and personality (voice/vision/TTS)."""

import threading
import asyncio
import uvicorn
from server import app
import personality


def start_movement_server() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8080)


def start_personality() -> None:
    asyncio.run(personality.personality_loop())


if __name__ == "__main__":
    threading.Thread(target=start_movement_server, daemon=True).start()
    threading.Thread(target=start_personality, daemon=True).start()

    # Keep main thread alive
    threading.Event().wait()
