"""Start both pipelines in separate threads: movement (joystick server) and personality (voice/vision/TTS)."""

import sys
import threading
from collections.abc import Callable
import asyncio
import uvicorn
from server import app
import personality

# Exceptions from worker threads; keyed by thread name so main can propagate failure.
_worker_exceptions: dict[str, BaseException] = {}


def _run_and_capture(fn: Callable[[], None]) -> None:
    try:
        fn()
    except BaseException as e:
        _worker_exceptions[threading.current_thread().name] = e


def start_movement_server() -> None:
    print("Starting movement server...")
    uvicorn.run(app, host="0.0.0.0", port=8080)


def start_personality() -> None:
    print("Starting personality...")
    asyncio.run(personality.personality_loop())


if __name__ == "__main__":
    t_movement = threading.Thread(
        name="movement",
        target=lambda: _run_and_capture(start_movement_server),
        daemon=False,
    )
    t_personality = threading.Thread(
        name="personality",
        target=lambda: _run_and_capture(start_personality),
        daemon=False,
    )
    t_movement.start()
    t_personality.start()

    while True:
        t_movement.join(timeout=1.0)
        t_personality.join(timeout=1.0)
        for t in (t_movement, t_personality):
            if not t.is_alive():
                if t.name in _worker_exceptions:
                    e: BaseException = _worker_exceptions[t.name]
                    print(f"Worker thread '{t.name}' failed: {e}", file=sys.stderr)
                    sys.exit(1)
                print(f"Worker thread '{t.name}' exited.", file=sys.stderr)
                sys.exit(1)
