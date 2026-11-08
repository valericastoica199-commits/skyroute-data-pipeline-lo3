"""Flask app for Render: start command  `gunicorn api.app:app`

Routes (same as server.py):
- GET /                -> operations dashboard (index.html)
- GET /output/<file>   -> run results used by the dashboard (json / csv only)
- GET /healthz         -> health check
- GET /api/run         -> runs the pipeline now (needs "Authorization: Bearer <CRON_SECRET>")

The pipeline runs once when the app starts, so the dashboard shows a run
that happened on Render.
"""
import os
import sys
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline import QualityGateError, run_pipeline  # noqa: E402

OUTPUT = ROOT / "output"
RUN_LOCK = threading.Lock()

app = Flask(__name__)


def run_once(trigger: str):
    if not RUN_LOCK.acquire(blocking=False):
        return {"error": "a run is already in progress"}, 409
    try:
        return run_pipeline(ROOT / "data" / "orders.csv", OUTPUT, trigger=trigger), 200
    except QualityGateError as exc:
        return {"error": "quality gate failed", "summary": exc.args[0]}, 422
    except Exception as exc:  # shown in Render logs
        print(f"pipeline failed: {exc!r}", flush=True)
        return {"error": "pipeline failed"}, 500
    finally:
        RUN_LOCK.release()


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.get("/")
@app.get("/index.html")
def dashboard():
    return send_from_directory(ROOT, "index.html")


@app.get("/healthz")
def health():
    return jsonify(status="ok")


@app.get("/output/<name>")
def output_file(name):
    if Path(name).suffix not in (".json", ".csv"):
        abort(404)
    return send_from_directory(OUTPUT, name)  # blocks ../ paths itself


@app.get("/api/run")
def api_run():
    secret = os.getenv("CRON_SECRET")
    if not secret or request.headers.get("Authorization") != f"Bearer {secret}":
        return jsonify(error="unauthorised"), 401
    body, code = run_once("api")
    return jsonify(body), code


if os.getenv("SKYROUTE_RUN_ON_START", "1") == "1":
    run_once(os.getenv("SKYROUTE_TRIGGER", "render-deploy"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
