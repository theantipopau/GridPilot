"""Entry point for the packaged desktop build (docs/packaging.md Phase 2).

Starts the same FastAPI app used in dev/single-process mode on a local
port, waits for it to actually answer before showing anything, then opens
a native window onto it with pywebview instead of asking the user to open
a browser tab themselves. Not used in normal development - `npm run dev` +
`uvicorn` (hot reload) or the single-process `uvicorn` command in the
README remain how this project is actually built.
"""

import threading
import time
import urllib.request

import uvicorn
import webview

from app.config import ensure_dirs

HOST = "127.0.0.1"
PORT = 8000


def _run_server() -> None:
    from app.api.main import app

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def _wait_until_ready(timeout_seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://{HOST}:{PORT}/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.2)
    return False


def main() -> None:
    ensure_dirs()
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    if not _wait_until_ready():
        raise RuntimeError(f"Backend did not become ready on {HOST}:{PORT} in time")

    webview.create_window("GridPilot", f"http://{HOST}:{PORT}", width=1440, height=900, min_size=(1024, 700))
    webview.start()


if __name__ == "__main__":
    main()
