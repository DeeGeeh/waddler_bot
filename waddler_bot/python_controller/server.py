"""Movement pipeline: FastAPI serves joystick UI, WebSocket forwards commands to Rust. No AI."""

import rust_motor
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
            rust_motor.execute_command(cmd)  # direct to Rust, no AI involved
    except Exception:
        rust_motor.execute_command("stop")  # safe stop on disconnect
