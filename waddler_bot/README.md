# Hackathon Robot (Voice on Pi Zero 2 W)

This folder contains the robot stack: **two decoupled pipelines** — movement (joystick only) and personality (voice + TTS). Python (OpenAI APIs, mic) + Rust (motor/servo control via PyO3), targeting a Raspberry Pi Zero 2 W. See the main repo and `../hackathon_robot_plan.md` for the full architecture.

## Two pipelines

- **Movement:** Browser joystick (nipplejs) → WebSocket → FastAPI → Rust `execute_command` → GPIO/motors. No AI; joystick is the sole source of movement control.
- **Personality:** Microphone → Whisper → GPT-4o → TTS → speaker (wake word "Waddler"). Runs in a separate async loop and never touches the motors.

## Directory layout

| Path | Role |
|------|------|
| `rust_motor/` | Rust crate: GPIO/PWM motor control; exposes `execute_command(cmd)` to Python via PyO3. |
| `python_controller/` | Python app: `server.py` (joystick UI + WebSocket), `personality.py` (voice/TTS loop), `voice.py`. |
| `config/` | Config files (e.g. motor pins, servo params). |

## How to run

- **Rust:** From `rust_motor/`, build the PyO3 module. On the Pi, use maturin/cross to build for `arm-unknown-linux-gnueabihf` and copy the built `.so` into this project (e.g. so Python can `import rust_motor`). On your laptop, `maturin develop` for local testing.
- **Python:** From `python_controller/`, create a venv, run `pip install -r requirements.txt`, set `OPENAI_API_KEY` (see `.env.example`), then `python main.py`.
- **Joystick:** Open `http://<PI_IP>:8080` in any browser on the same Wi-Fi (phone or laptop). Find the Pi’s IP with `hostname -I`. For reliable demos, assign the Pi a static IP in your router’s DHCP settings.
- **Personality:** Voice uses the OpenAI API (Whisper, GPT-4o, TTS); ensure the Pi has internet and `OPENAI_API_KEY` is set.
