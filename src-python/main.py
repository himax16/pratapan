from __future__ import annotations

import logging
import os
import sys
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[sidecar] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

PORT = 48240
server: uvicorn.Server | None = None

app = FastAPI(title="Pratapan sidecar", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/connect")
def connect():
    """Endpoint to check sidecar port and PID"""
    return {"status": "ok", "port": PORT, "pid": os.getpid()}


@app.post("/v1/lowercase")
def lowercase(payload: dict):
    """Endpoint to make lowercase the input text"""
    text = payload.get("text", "")
    log.info("lowercase: %r", text)
    return {"result": text.lower()}


def _stdin_loop() -> None:
    log.info("stdin loop ready")
    for line in sys.stdin:
        if line.strip() == "sidecar shutdown":
            log.info("shutdown command received")
            if server is not None:
                server.should_exit = True
            break


if __name__ == "__main__":
    log.info("sidecar started, pid=%d", os.getpid())
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    threading.Thread(target=_stdin_loop, daemon=True).start()
    server.run()
    sys.exit(0)
