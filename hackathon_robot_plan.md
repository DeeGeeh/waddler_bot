# Hackathon Implementation Plan – Vision + Voice Robot on Pi Zero 2 W

## 1️ Project Overview

**Goal:** Build a robot using a Raspberry Pi Zero 2 W with two completely independent pipelines:

**Movement pipeline** — joystick is the sole source of movement control:
- Browser-based joystick UI served over localhost, accessible from any phone or desktop on the same Wi-Fi
- Joystick inputs sent via WebSocket → motor backend (rust or sim) → either Rust (GPIO) or TCP to Isaac Lab bridge; no AI in movement
- No AI involvement in movement whatsoever

**Personality pipeline** — LLM runs async in the background, never touches the motors:
- Microphone captures voice → OpenAI Whisper → GPT-4o responds via TTS speaker
- Camera captures frames → GPT-4o observes and narrates what it sees
- Runs on its own async loop, completely decoupled from movement
- Slow API responses never delay or interfere with driving

### Core Components

| Component | Role |
|---|---|
| Pi Zero 2 W | Robot controller / hardware interface |
| Rust | Performance-critical motor/sensor control |
| PyO3 | Bridge Python → Rust |
| FastAPI + WebSocket | Localhost joystick server (movement) |
| motor_backend.py | Chooses rust (Rust/GPIO) or sim (TCP to Isaac Lab); env MOTOR_BACKEND, SIM_HOST, SIM_PORT. |
| nipplejs (browser) | Touch joystick UI on phone/desktop |
| Python (personality) | OpenAI Whisper, GPT-4o, TTS — async personality loop |
| Camera module | Feed for GPT-4o personality observations |
| Microphone | Voice input for personality conversation |
| Speaker | TTS output for robot personality |
| Wi-Fi | LAN for joystick UI + internet for OpenAI API |
| Isaac Lab (optional) | Sim bridge receives TCP commands; see SIM_PROTOCOL.md. |

---

## 2️ Architecture Diagram

```
MOVEMENT PIPELINE (realtime, no AI)
────────────────────────────────────────────────────────
Phone/Desktop Browser
  │  nipplejs joystick
  │  WebSocket
  ▼
FastAPI Server (server.py)
  │  motor_backend (execute_command)
  │  MOTOR_BACKEND=rust → PyO3 → Rust Motor Module → GPIO → Motors
  │  MOTOR_BACKEND=sim  → TCP → Isaac Lab bridge (teammate's machine) → simulated robot
  ▼
Motors / Servos (or simulated robot)


PERSONALITY PIPELINE (async, never touches motors)
────────────────────────────────────────────────────────
Microphone ──► Whisper API ──┐
                              ├──► GPT-4o ──► TTS ──► Speaker
Camera ──────► GPT-4o ───────┘
```

These two pipelines share no state and run in separate async threads. A slow LLM response never blocks motor commands by even a millisecond.

---

## 3️ Project Structure

```
hackathon_robot/
│
├─ rust_motor/               # Rust performance-critical module
│   ├─ Cargo.toml
│   └─ src/
│       ├─ lib.rs            # PyO3 module exposing motor commands
│       └─ motor.rs          # GPIO / PWM control
│
├─ python_controller/        # Python module
│   ├─ main.py               # Starts both pipelines in separate threads
│   ├─ server.py             # FastAPI WebSocket server + joystick HTML; calls motor_backend.execute_command
│   ├─ motor_backend.py      # Motor backend: rust (GPIO) or sim (TCP); reads motor_config for rust init
│   ├─ personality.py        # Async personality loop — voice, vision, TTS
│   ├─ voice.py              # Microphone capture & OpenAI Whisper
│   └─ vision.py             # Camera capture & GPT-4o observation
│
├─ config/
│   └─ motor_config.json     # Motor pins (BCM GPIO), servo params
│
├─ SIM_PROTOCOL.md           # TCP protocol for sim bridge (one command per line)
└─ README.md
```

---

## 4️ Detailed Implementation Steps

### Step 1: Set up Pi Zero 2 W

> **Env:** `.env` (see `.env.example`) includes `OPENAI_API_KEY` and, for movement, `MOTOR_BACKEND`, `SIM_HOST`, `SIM_PORT`.

Install Raspberry Pi OS Lite (minimal for performance), enable SSH, connect to Wi-Fi, then:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip libssl-dev pkg-config build-essential cmake git
```

Install Rust via rustup:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Install PyO3 dependencies:

```bash
sudo apt install python3-dev
cargo install maturin
```

> ⚠️ **Cross-compilation strongly recommended.** Compiling Rust directly on the Pi Zero 2 W is extremely slow (10–20+ minutes per build). Use `cross` on your laptop to build for the Pi's `arm-unknown-linux-gnueabihf` target, then transfer the built `.so` to the Pi. Do this early — it will save significant time during the hackathon.

**Setting up cross-rs (on your laptop):**

```bash
# Install cross (requires Docker or Podman running)
cargo install cross --git https://github.com/cross-rs/cross

# Add the Pi Zero 2 W target to rustup
rustup target add arm-unknown-linux-gnueabihf
```

**Building with cross-rs + maturin:**

```bash
cd rust_motor

# Build the PyO3 .so for the Pi using maturin + cross
maturin build --release --target arm-unknown-linux-gnueabihf --zig
# Or if using cross directly:
cross build --release --target arm-unknown-linux-gnueabihf
```

**Transfer the built module to the Pi:**

```bash
scp target/arm-unknown-linux-gnueabihf/release/librust_motor*.so pi@<PI_IP>:~/hackathon_robot/
```

> 💡 **Tip:** `maturin build --zig` uses the Zig linker for easier cross-compilation without needing a full ARM sysroot. Install with `pip install maturin[zig]` and `brew install zig` (macOS) or `snap install zig` (Linux).

---

### Step 2: Rust Motor Controller

**Objectives:**
- Control motors / servos via GPIO / PWM
- Provide atomic, low-latency commands
- Expose Python API via PyO3: `execute_command(cmd)` and `init(left_forward, left_backward, right_forward, right_backward)` — call `init` once at startup with BCM pin numbers from config

Create new Rust library:

```bash
cargo new --lib rust_motor
```

Add PyO3 and rppal (Linux only) in `Cargo.toml`:

```toml
[dependencies]
pyo3 = { version = "0.18", features = ["extension-module"] }

# On Pi/Linux only:
[target.'cfg(target_os = "linux")'.dependencies]
rppal = "0.17"
```

`motor_config.json` (in `config/`) holds `motor_pins`: `left_forward`, `left_backward`, `right_forward`, `right_backward` (BCM GPIO). Python loads it and calls `rust_motor.init(...)` once when using the rust backend. Implement motor functions and expose via PyO3 in `lib.rs`: `init(...)` and `execute_command(cmd)` — `init` must be called first when using the rust backend.

```rust
#[pyfunction]
fn init(left_forward: u8, left_backward: u8, right_forward: u8, right_backward: u8) { ... }
#[pyfunction]
fn execute_command(cmd: &str) { /* map cmd → move_forward, turn_left, stop etc */ }
```

Build and deploy:

```bash
# On your laptop
maturin build --release --target arm-unknown-linux-gnueabihf --zig
scp target/arm-unknown-linux-gnueabihf/release/librust_motor*.so pi@<PI_IP>:~/hackathon_robot/

# On the Pi — no compilation needed, just use the pre-built .so
```

---

### Step 3: Movement Pipeline — Joystick Web Server

**Objectives:**
- Serve a touch-friendly joystick UI to any device on the same Wi-Fi
- Receive joystick inputs via WebSocket and forward directly to Rust motor module
- No AI in this path — movement is always immediate and reliable

**Install dependencies:**

```bash
pip install fastapi uvicorn websockets
```

**`server.py`** — serves the joystick UI and drives motors via WebSocket (uses motor_backend, not rust_motor directly). Motor backend is selected by env: `MOTOR_BACKEND=rust` (default) or `sim`. For sim, set `SIM_HOST` (e.g. teammate's IP) and `SIM_PORT` (default 9999). See `.env.example`.

```python
from motor_backend import execute_command
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()

HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Robot Control</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/nipplejs/0.10.1/nipplejs.min.js"></script>
  <style>
    body { background: #111; display: flex; justify-content: center;
           align-items: center; height: 100vh; margin: 0; }
    #zone { width: 200px; height: 200px; }
  </style>
</head>
<body>
  <div id="zone"></div>
  <script>
    const ws = new WebSocket(`ws://${location.host}/ws`);
    const joystick = nipplejs.create({ zone: document.getElementById('zone'), mode: 'static',
                                       position: { left: '50%', top: '50%' }, color: 'white' });

    joystick.on('move', (_, data) => {
      const angle = data.angle.degree;
      let cmd = 'stop';
      if (angle > 45 && angle < 135)         cmd = 'forward';
      else if (angle > 225 && angle < 315)   cmd = 'backward';
      else if (angle >= 135 && angle <= 225) cmd = 'left';
      else                                   cmd = 'right';
      ws.send(cmd);
    });

    joystick.on('end', () => ws.send('stop'));
  </script>
</body>
</html>
"""

@app.get("/")
async def index():
    return HTMLResponse(HTML)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            cmd = await websocket.receive_text()
            execute_command(cmd)  # motor_backend: rust or sim
    except Exception:
        execute_command("stop")  # safe stop on disconnect
```

**Access from your phone or laptop:** open `http://<PI_IP>:8080` in any browser on the same Wi-Fi.

> 💡 Find your Pi's IP with `hostname -I`. For demo reliability, assign it a static IP in your router's DHCP settings beforehand.

---

### Step 4: Personality Pipeline — Voice & Vision

**Objectives:**
- Listen for voice input and respond conversationally via TTS
- Periodically observe the camera feed and narrate/comment on what it sees
- Run entirely async — never blocks or interferes with motor control

**Install dependencies:**

```bash
pip install openai opencv-python sounddevice numpy
```

**`voice.py`** — capture audio and transcribe via Whisper:

```python
import openai, sounddevice, numpy as np, scipy.io.wavfile as wav

def capture_and_transcribe():
    audio = sounddevice.rec(int(3 * 16000), samplerate=16000, channels=1)
    sounddevice.wait()
    wav.write("audio.wav", 16000, audio)
    response = openai.audio.transcriptions.create(
        file=open("audio.wav", "rb"),
        model="whisper-1"
    )
    return response.text
```

**`vision.py`** — capture a frame and ask GPT-4o to observe and comment:

```python
import openai, base64, cv2

def observe_and_comment():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    frame_small = cv2.resize(frame, (320, 240))
    _, buffer = cv2.imencode('.jpg', frame_small)
    b64 = base64.b64encode(buffer).decode("utf-8")

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                },
                {
                    "type": "text",
                    "text": "You are a witty robot. Comment on what you see in one short sentence."
                }
            ]
        }]
    )
    return response.choices[0].message.content
```

> ⚠️ **Note:** Do NOT use `openai.images.generate()` for vision — that is the image *generation* endpoint. Vision/analysis requires the chat completions endpoint with an image in the message content, as shown above.

**`personality.py`** — async loop that handles voice conversation and periodic visual narration:

```python
import asyncio, openai
import voice, vision

async def personality_loop():
    while True:
        # Vision: observe surroundings every ~10 seconds and narrate
        comment = vision.observe_and_comment()
        speak(comment)  # TTS (see Step 5)

        # Voice: listen for a question and respond
        heard = voice.capture_and_transcribe()
        if heard.strip():
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a witty, curious robot. Keep replies brief."},
                    {"role": "user", "content": heard}
                ]
            )
            speak(response.choices[0].message.content)

        await asyncio.sleep(1)
```

---

### Step 5: TTS — Robot Voice Output

Use OpenAI TTS for natural-sounding speech, or `pico2wave` for a lightweight offline fallback:

```python
import openai, subprocess

def speak(text):
    # Option A: OpenAI TTS (requires Wi-Fi)
    response = openai.audio.speech.create(model="tts-1", voice="onyx", input=text)
    response.stream_to_file("reply.mp3")
    subprocess.run(["mpg123", "reply.mp3"])

    # Option B: offline fallback
    # subprocess.run(["pico2wave", "-w", "reply.wav", text])
    # subprocess.run(["aplay", "reply.wav"])
```

---

### Step 6: main.py — Wiring Both Pipelines Together

`main.py` starts the movement server and personality loop in separate threads so they never interfere:

```python
import threading, asyncio, uvicorn
from server import app
import personality

def start_movement_server():
    uvicorn.run(app, host="0.0.0.0", port=8080)

def start_personality():
    asyncio.run(personality.personality_loop())

if __name__ == "__main__":
    threading.Thread(target=start_movement_server, daemon=True).start()
    threading.Thread(target=start_personality, daemon=True).start()

    # Keep main thread alive
    threading.Event().wait()
```

---

### Step 7: Isaac Lab Simulation (Optional)

When `MOTOR_BACKEND=sim`, the movement pipeline sends commands over TCP to a simulation bridge (e.g. on a teammate's machine running Isaac Lab). Same WebSocket server and command interface (forward/backward/left/right/stop). Protocol: TCP, one command per line, UTF-8, newline-terminated; see **SIM_PROTOCOL.md**. The bridge listens on `SIM_PORT` and drives the simulated robot; no response required from bridge to the controller.

---

## 5️ Testing Plan

1. Test Rust motor commands independently
2. Test joystick server — connect phone, verify WebSocket commands drive motors (or sim: set MOTOR_BACKEND=sim and verify TCP commands reach the Isaac Lab bridge)
3. Test personality voice — speak to robot, verify Whisper transcription and GPT-4o response
4. Test personality vision — verify camera capture → GPT-4o narration → TTS output
5. Test both pipelines running simultaneously — confirm personality loop never causes motor lag
6. Test safe stop on WebSocket disconnect
7. Optional: Isaac Lab simulation (MOTOR_BACKEND=sim + bridge per SIM_PROTOCOL.md)

---

## 6️ Performance Tips for Pi Zero 2 W

- Movement pipeline is entirely local (WebSocket → Rust → GPIO) — no internet needed, sub-10ms latency
- Personality pipeline can be slow (1–3s API round trips) — this is fine since it never blocks movement
- Keep camera frames small (320×240) for faster encoding
- Run personality loop at a relaxed cadence (every 10s for vision, voice-triggered for chat)
- Assign a static IP to the Pi before the demo for reliable browser access

---

## Summary

| Layer | Responsibility |
|---|---|
| **motor_backend** | Env-based: rust (Rust + config) or sim (TCP to bridge); .env: MOTOR_BACKEND, SIM_HOST, SIM_PORT. |
| **Rust** | Motor control via GPIO/PWM on Linux; called via motor_backend when MOTOR_BACKEND=rust; init(pins) at startup. |
| **FastAPI + WebSocket** | Serves joystick UI, receives inputs, calls motor_backend.execute_command (rust or sim). |
| **nipplejs** | Touch joystick in the browser — no app install needed |
| **personality.py** | Async loop: voice → Whisper → GPT-4o → TTS. Never touches motors |
| **vision.py** | Periodic camera observation fed to GPT-4o for narration |
| **voice.py** | Microphone capture and Whisper transcription |
| **TTS / Speaker** | Robot voice output for personality responses |
| **Wi-Fi** | LAN for joystick UI (movement) + internet for OpenAI API (personality) |
| **Isaac Lab** | Optional: sim bridge receives TCP commands (SIM_PROTOCOL.md). |