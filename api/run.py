"""Vercel serverless function: GET /api/run runs the pipeline once.

Vercel's file system is read-only except /tmp, so outputs go to /tmp and the
run summary is returned as JSON. Vercel Cron calls this route on a schedule
and sends "Authorization: Bearer <CRON_SECRET>"; manual calls must send the
same header, so the endpoint cannot be triggered by strangers.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline import QualityGateError, run_pipeline  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        secret = os.getenv("CRON_SECRET")
        if secret and self.headers.get("Authorization") != f"Bearer {secret}":
            return self._send(401, {"error": "unauthorised"})
        out = Path("/tmp/skyroute")
        try:
            summary = run_pipeline(ROOT / "data" / "orders.csv", out, workers=4,
                                   log_path=None, trigger="serverless")
            return self._send(200, summary)
        except QualityGateError as exc:
            return self._send(422, {"error": "quality gate failed", "summary": exc.args[0]})
        except Exception as exc:  # logged by Vercel runtime logs
            print(f"pipeline failed: {exc!r}")
            return self._send(500, {"error": "pipeline failed"})
