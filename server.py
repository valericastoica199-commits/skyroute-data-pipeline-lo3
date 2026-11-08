"""Small web server for Render (web service).

- GET /                -> operations dashboard (index.html)
- GET /output/<file>   -> run results used by the dashboard (json / csv only)
- GET /healthz         -> health check for Render
- GET /api/run         -> runs the pipeline now (needs "Authorization: Bearer <CRON_SECRET>")

The pipeline also runs once when the service starts, so the dashboard always
shows a run that happened on Render. Only the Python standard library is used.
"""
import json
import mimetypes
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from pipeline import QualityGateError, run_pipeline  # noqa: E402

OUTPUT = ROOT / "output"
RUN_LOCK = threading.Lock()


def run_once(trigger: str) -> tuple[int, dict]:
    if not RUN_LOCK.acquire(blocking=False):
        return 409, {"error": "a run is already in progress"}
    try:
        return 200, run_pipeline(ROOT / "data" / "orders.csv", OUTPUT, trigger=trigger)
    except QualityGateError as exc:
        return 422, {"error": "quality gate failed", "summary": exc.args[0]}
    except Exception as exc:  # shown in Render logs
        print(f"pipeline failed: {exc!r}", flush=True)
        return 500, {"error": "pipeline failed"}
    finally:
        RUN_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, data: dict) -> None:
        self._send(code, json.dumps(data, indent=2).encode(), "application/json")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/healthz":
            return self._json(200, {"status": "ok"})
        if path == "/api/run":
            secret = os.getenv("CRON_SECRET")
            if not secret or self.headers.get("Authorization") != f"Bearer {secret}":
                return self._json(401, {"error": "unauthorised"})
            return self._json(*run_once("api"))
        if path.startswith("/output/"):
            name = path[len("/output/"):]
            file = OUTPUT / name
            # only plain file names inside output/, only json/csv
            if "/" not in name and "\\" not in name and file.suffix in (".json", ".csv") and file.is_file():
                ctype = mimetypes.guess_type(file.name)[0] or "text/plain"
                return self._send(200, file.read_bytes(), ctype)
        return self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # one line per request in Render logs
        print(f"{self.address_string()} - {fmt % args}", flush=True)


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    if os.getenv("SKYROUTE_RUN_ON_START", "1") == "1":
        run_once(os.getenv("SKYROUTE_TRIGGER", "startup"))
    print(f"SkyRoute dashboard listening on 0.0.0.0:{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
