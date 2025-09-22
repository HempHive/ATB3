#!/usr/bin/env python3
"""
ATB3 Backend API (FastAPI)

Provides REST endpoints to manage the NautilusTrader engine lifecycle and
data/model downloads. Designed to be run locally alongside the static
frontend (e.g., GitHub Pages) and accessed via CORS-enabled requests.
"""

import os
import sys
import time
import threading
import signal
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = Path(os.getenv("NAUTILUS_DATA_PATH", PROJECT_ROOT / "nautilus_data"))


class EngineState:
    """Tracks lifecycle and process state for the Nautilus engine."""

    def __init__(self) -> None:
        self.status: str = "DISCONNECTED"  # DISCONNECTED | CONNECTED | SYNCING | ERROR
        self.detail: str = ""
        self.process: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "detail": self.detail, "pid": self.process.pid if self.process else None}


class DataState:
    """Tracks long-running data download/update progress."""

    def __init__(self) -> None:
        self.in_progress: bool = False
        self.total_bytes: int = 0
        self.downloaded_bytes: int = 0
        self.last_error: str = ""
        self.updated_at: float = time.time()
        self.lock = threading.Lock()

    def to_dict(self) -> Dict[str, Any]:
        with self.lock:
            pct = 0.0
            if self.total_bytes > 0:
                pct = (self.downloaded_bytes / self.total_bytes) * 100.0
            return {
                "in_progress": self.in_progress,
                "total_bytes": self.total_bytes,
                "downloaded_bytes": self.downloaded_bytes,
                "percent": round(pct, 2),
                "last_error": self.last_error,
                "updated_at": self.updated_at,
            }


engine_state = EngineState()
data_state = DataState()


class StartEngineRequest(BaseModel):
    # Placeholder for future config (venues, accounts, strategy, etc.)
    command: Optional[str] = None  # Custom command to launch Nautilus (advanced)


class DownloadDataRequest(BaseModel):
    # Placeholder for dataset selection and versioning
    source: Optional[str] = None  # e.g., "s3", "http", "git-lfs"
    size_gb: float = 10.0


app = FastAPI(title="ATB3 Backend API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _spawn_engine_subprocess(custom_command: Optional[str] = None) -> subprocess.Popen:
    """Start the Nautilus engine process.

    This is a thin placeholder which can be customized. If a custom command is
    not provided, we start a benign Python process that keeps running so the
    frontend can toggle status. Replace with a real Nautilus command when ready.
    """

    # Example real command (commented):
    # cmd = [sys.executable, "-m", "nautilus_trader.examples.live.run"]
    if custom_command:
        cmd = custom_command if isinstance(custom_command, list) else custom_command.split()
    else:
        # Portable long-running no-op loop
        cmd = [sys.executable, "-c", "import time;\n\nprint('ATB3 engine placeholder running');\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nwhile True: time.sleep(1)"]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _simulate_download_task(target_dir: Path, size_gb: float) -> None:
    """Simulate a large dataset download with progress updates.

    Replace with real download logic (e.g., S3, HTTP, or Git LFS).
    """

    target_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = int(size_gb * (1024 ** 3))
    chunk = 8 * 1024 * 1024  # 8MB
    with data_state.lock:
        data_state.in_progress = True
        data_state.total_bytes = total_bytes
        data_state.downloaded_bytes = 0
        data_state.last_error = ""
        data_state.updated_at = time.time()

    try:
        # Write to a temp file to simulate IO; discard content
        tmp_path = target_dir / "model.tmp"
        with open(tmp_path, "wb") as f:
            while True:
                with data_state.lock:
                    if data_state.downloaded_bytes >= total_bytes:
                        break
                    to_write = min(chunk, total_bytes - data_state.downloaded_bytes)
                f.write(b"\0" * to_write)
                with data_state.lock:
                    data_state.downloaded_bytes += to_write
                    data_state.updated_at = time.time()
                time.sleep(0.05)
        # Finalize
        final_path = target_dir / "MODEL_READY"
        final_path.write_text("ready")
    except Exception as exc:  # noqa: BLE001
        with data_state.lock:
            data_state.last_error = str(exc)
    finally:
        with data_state.lock:
            data_state.in_progress = False
            data_state.updated_at = time.time()


@app.get("/status")
def status() -> Dict[str, Any]:
    """Return current engine status and data status summary."""
    data_info = data_state.to_dict()
    try:
        ready = (DEFAULT_DATA_PATH / "MODEL_READY").exists()
        model_name = None
        info_path = DEFAULT_DATA_PATH / "model.info"
        if info_path.exists():
            try:
                model_name = info_path.read_text().strip() or None
            except Exception:  # noqa: BLE001
                model_name = None
    except Exception:  # noqa: BLE001
        ready = False
        model_name = None
    data_info.update({
        "ready": ready,
        "path": str(DEFAULT_DATA_PATH),
        "model": model_name,
    })
    return {"engine": engine_state.to_dict(), "data": data_info}


@app.post("/start_engine")
def start_engine(payload: StartEngineRequest | None = None) -> Dict[str, Any]:
    """Start or connect to the NautilusTrader engine."""
    with engine_state.lock:
        if engine_state.process and engine_state.process.poll() is None:
            engine_state.status = "CONNECTED"
            engine_state.detail = "Engine already running"
            return {"ok": True, **engine_state.to_dict()}
        engine_state.status = "CONNECTING"
        engine_state.detail = "Spawning engine process"
    try:
        proc = _spawn_engine_subprocess(payload.command if payload else None)
        with engine_state.lock:
            engine_state.process = proc
            engine_state.status = "CONNECTED"
            engine_state.detail = "Engine process started"
        return {"ok": True, **engine_state.to_dict()}
    except Exception as exc:  # noqa: BLE001
        with engine_state.lock:
            engine_state.status = "ERROR"
            engine_state.detail = str(exc)
        return {"ok": False, **engine_state.to_dict()}


@app.post("/stop_engine")
def stop_engine() -> Dict[str, Any]:
    """Stop the NautilusTrader engine if running."""
    with engine_state.lock:
        proc = engine_state.process
    if proc and proc.poll() is None:
        try:
            if os.name == "nt":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()
        finally:
            with engine_state.lock:
                engine_state.process = None
                engine_state.status = "DISCONNECTED"
                engine_state.detail = "Engine stopped"
    else:
        with engine_state.lock:
            engine_state.status = "DISCONNECTED"
            engine_state.detail = "No engine process running"
    return {"ok": True, **engine_state.to_dict()}


@app.post("/download_data")
def download_data(payload: DownloadDataRequest | None = None, background: BackgroundTasks = None) -> Dict[str, Any]:  # type: ignore[assignment]
    """Begin downloading the Nautilus market data model if not present."""
    target_dir = DEFAULT_DATA_PATH
    size_gb = (payload.size_gb if payload else 10.0) or 10.0

    with data_state.lock:
        if data_state.in_progress:
            return {"ok": True, "message": "Download already in progress", **data_state.to_dict()}
        data_state.in_progress = True
        data_state.total_bytes = 0
        data_state.downloaded_bytes = 0
        data_state.last_error = ""
        data_state.updated_at = time.time()

    background.add_task(_simulate_download_task, target_dir, size_gb)
    return {"ok": True, "message": "Download started", "path": str(target_dir)}


@app.post("/update_data")
def update_data(background: BackgroundTasks) -> Dict[str, Any]:
    """Update dataset to latest model. For now same as download (idempotent)."""
    with data_state.lock:
        if data_state.in_progress:
            return {"ok": True, "message": "Another operation in progress", **data_state.to_dict()}
    background.add_task(_simulate_download_task, DEFAULT_DATA_PATH, 1.0)
    return {"ok": True, "message": "Update started"}


@app.get("/download_progress")
def download_progress() -> Dict[str, Any]:
    return data_state.to_dict()


if __name__ == "__main__":
    # Run with: python backend/api.py
    # Or: uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
    import uvicorn

    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)


