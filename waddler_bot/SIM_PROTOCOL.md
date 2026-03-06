# Sim bridge protocol

The simulation bridge is a TCP server listening on `SIM_PORT` (default 9999).

- **Encoding:** UTF-8, one command per line, newline-terminated (`\n`).
- **Commands:** `forward`, `backward`, `left`, `right`, `stop`.
- **Response:** None required; client sends and may close the connection.
