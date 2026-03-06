"""Motor backend: rust (GPIO on Pi) or sim (TCP to Isaac Lab bridge)."""

import json
import logging
import os
import socket

from logging import Logger

logger: Logger = logging.getLogger(__name__)

MOTOR_BACKEND: str = os.environ.get("MOTOR_BACKEND", "rust").strip().lower()
SIM_HOST: str = os.environ.get("SIM_HOST", "127.0.0.1").strip()
SIM_PORT: int = int(os.environ.get("SIM_PORT", "9999").strip())

_rust_initialized = False


def _ensure_rust_init() -> None:
    global _rust_initialized
    if _rust_initialized:
        return
    config_dir: str = os.path.join(os.path.dirname(__file__), "..", "config")
    config_path: str = os.path.join(config_dir, "motor_config.json")
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Motor config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    pins = config.get("motor_pins", {})
    left_forward = int(pins.get("left_forward", 0))
    left_backward = int(pins.get("left_backward", 0))
    right_forward = int(pins.get("right_forward", 0))
    right_backward = int(pins.get("right_backward", 0))
    import rust_motor  # noqa: PLC0415
    rust_motor.init(left_forward, left_backward, right_forward, right_backward)
    _rust_initialized = True


def execute_command(cmd: str) -> None:
    """Run a movement command: forward, backward, left, right, stop."""
    cmd = (cmd or "").strip().lower()
    if cmd not in ("forward", "backward", "left", "right", "stop"):
        cmd = "stop"

    if MOTOR_BACKEND == "rust":
        _ensure_rust_init()
        import rust_motor  # noqa: PLC0415
        rust_motor.execute_command(cmd)
        return

    if MOTOR_BACKEND == "sim":
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2.0)
                sock.connect((SIM_HOST, SIM_PORT))
                sock.sendall((cmd + "\n").encode("utf-8"))
        except (OSError, socket.error) as e:
            logger.debug("Sim TCP send failed: %s", e)
        return

    logger.warning("Unknown MOTOR_BACKEND=%r; no-op", MOTOR_BACKEND)
