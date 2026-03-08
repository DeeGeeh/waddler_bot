"""Movement pipeline: FastAPI serves joystick UI, WebSocket forwards commands to motor backend. No AI."""

from motor_backend import execute_command
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()

# TODO: I know, I know, this is fucking ugly, but works for now.
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
    const wsSchema = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${wsSchema}://${location.host}/ws`);
    const joystick = nipplejs.create({ zone: document.getElementById('zone'), mode: 'static',
                                       position: { left: '50%', top: '50%' }, color: 'white' });

    const DEADZONE = 0.2;
    const RATE_MS = 66;
    let lastCmd = 'stop';
    let lastSendTime = 0;

    function sendCmd(cmd) {
      if (ws.readyState !== WebSocket.OPEN || cmd === lastCmd) return;
      if (cmd !== 'stop' && (Date.now() - lastSendTime) < RATE_MS) return;
      ws.send(cmd);
      lastCmd = cmd;
      lastSendTime = Date.now();
    }

    function angleToCmd(angle) {
      if (angle > 55 && angle < 125) return 'forward';
      if (angle > 235 && angle < 305) return 'backward';
      if (angle >= 125 && angle <= 235) return 'left';
      return 'right';
    }

    joystick.on('move', (_, data) => {
      const dist = (data.distance != null) ? data.distance : (data.force != null ? data.force : 1);
      if (dist < DEADZONE) {
        sendCmd('stop');
        return;
      }
      const angle = data.angle.degree;
      sendCmd(angleToCmd(angle));
    });

    joystick.on('end', () => sendCmd('stop'));
  </script>
</body>
</html>
"""


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse(HTML)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            cmd: str = await websocket.receive_text()
            execute_command(cmd)  # motor_backend: rust (GPIO) or sim (TCP)
    except Exception:
        execute_command("stop")  # safe stop on disconnect
