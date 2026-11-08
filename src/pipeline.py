"""SkyRoute Logistics - shipments reporting pipeline.

Stages: extract -> validate -> transform (parallel) -> aggregate -> load -> observe.

Only the Python standard library is used, so the same file runs on a laptop
(manual), on a Render cron job (scheduled) and inside a Vercel function
(serverless) without extra packages.

Usage:
    python src/pipeline.py --workers 4
    python src/pipeline.py --benchmark --simulate-latency 5
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_VERSION = "1.2.0"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "orders.csv"
DEFAULT_OUTPUT = ROOT / "output"
DEFAULT_LOG = ROOT / "logs" / "pipeline.log"

REQUIRED = ["order_id", "order_date", "region", "depot", "carrier", "status",
            "order_value", "items", "weight_kg", "promised_days", "actual_days"]
VALID_STATUSES = {"Delivered", "In Transit", "Delayed", "Processing"}
VALID_REGIONS = {"North", "South", "East", "West"}
DATE_FORMAT = "%d/%m/%Y"

# Settings can be changed per platform through environment variables.
MAX_REJECT_RATE = float(os.getenv("SKYROUTE_MAX_REJECT_RATE", "0.10"))
EXTRACT_RETRIES = int(os.getenv("SKYROUTE_EXTRACT_RETRIES", "3"))

log = logging.getLogger("skyroute")


class QualityGateError(RuntimeError):
    """Raised when too many rows fail validation."""


# ---------------------------------------------------------------- logging
def configure_logging(log_path: Path | None, run_id: str) -> None:
    fmt = logging.Formatter(
        f"%(asctime)s | %(levelname)-7s | run={run_id} | %(stage)s | %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    log.handlers.clear()
    log.setLevel(logging.INFO)
    log.propagate = False
    for h in handlers:
        h.setFormatter(fmt)
        h.addFilter(_StageFilter())
        log.addHandler(h)


class _StageFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "stage"):
            record.stage = "main"
        return True


def _info(stage: str, msg: str, *args) -> None:
    log.info(msg, *args, extra={"stage": stage})


def _warn(stage: str, msg: str, *args) -> None:
    log.warning(msg, *args, extra={"stage": stage})


# ---------------------------------------------------------------- extract
def extract(path: Path, retries: int = EXTRACT_RETRIES, wait: float = 0.5) -> list[dict]:
    """Read the CSV, retrying a few times in case the file is still arriving."""
    for attempt in range(1, retries + 1):
        try:
            with path.open(newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            _info("extract", "read %d rows from %s (attempt %d)", len(rows), path.name, attempt)
            return rows
        except FileNotFoundError:
            _warn("extract", "input not found: %s (attempt %d/%d)", path, attempt, retries)
            if attempt == retries:
                raise
            time.sleep(wait * attempt)
    return []


# ---------------------------------------------------------------- validate
def validate(row: dict) -> str | None:
    """Return None when the row is valid, otherwise a short reject reason."""
    missing = [c for c in REQUIRED if c not in row]
    if missing:
        return f"missing column(s): {', '.join(missing)}"
    if not (row["order_id"] or "").strip():
        return "empty order_id"
    try:
        datetime.strptime(row["order_date"], DATE_FORMAT)
    except (TypeError, ValueError):
        return "invalid order_date; expected YYYY-MM-DD"
    if row["region"] not in VALID_REGIONS:
        return "unknown region"
    if row["status"] not in VALID_STATUSES:
        return "unknown status"
    try:
        value = float(row["order_value"])
        items = int(row["items"])
        weight = float(row["weight_kg"])
        promised = int(row["promised_days"])
    except (TypeError, ValueError):
        return "order_value/items/weight_kg/promised_days must be numeric"
    if value < 0 or items < 1 or weight <= 0 or promised < 1:
        return "values out of range (value>=0, items>=1, weight>0, promised>=1)"
    if row["status"] in {"Delivered", "Delayed"} and not (row["actual_days"] or "").strip():
        return "actual_days required for delivered/delayed orders"
    return None


def split_valid(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    valid, rejected, seen = [], [], set()
    for row in rows:
        reason = validate(row)
        if reason is None and row["order_id"] in seen:
            reason = "duplicate order_id"
        if reason:
            rejected.append({**row, "reject_reason": reason})
        else:
            seen.add(row["order_id"])
            valid.append(row)
    return valid, rejected


# ---------------------------------------------------------------- transform
def transform(row: dict, latency: float = 0.0) -> dict:
    """Clean and enrich one row. `latency` imitates a slow lookup (e.g. a carrier API)."""
    if latency:
        time.sleep(latency)
    value = round(float(row["order_value"]), 2)
    items = int(row["items"])
    promised = int(row["promised_days"])
    actual = int(row["actual_days"]) if (row["actual_days"] or "").strip() else None
    on_time = "" if actual is None else ("yes" if actual <= promised else "no")
    return {
        "order_id": row["order_id"].strip(),
        "order_date": row["order_date"],
        "region": row["region"],
        "depot": row["depot"],
        "carrier": row["carrier"],
        "status": row["status"],
        "order_value": f"{value:.2f}",
        "items": items,
        "weight_kg": f"{float(row['weight_kg']):.1f}",
        "value_per_item": f"{value / items:.2f}",
        "promised_days": promised,
        "actual_days": "" if actual is None else actual,
        "on_time": on_time,
    }


def transform_all(rows: list[dict], workers: int, latency: float = 0.0) -> list[dict]:
    """Transform rows in parallel. executor.map keeps the original row order."""
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(lambda r: transform(r, latency), rows))


# ---------------------------------------------------------------- aggregate
def region_kpis(processed: list[dict]) -> list[dict]:
    out = []
    for region in sorted(VALID_REGIONS):
        rows = [r for r in processed if r["region"] == region]
        delivered = [r for r in rows if r["on_time"]]
        on_time = sum(1 for r in delivered if r["on_time"] == "yes")
        out.append({
            "region": region,
            "orders": len(rows),
            "revenue": round(sum(float(r["order_value"]) for r in rows), 2),
            "delayed": sum(1 for r in rows if r["status"] == "Delayed"),
            "on_time_rate": round(on_time / len(delivered) * 100, 1) if delivered else 0.0,
        })
    return out


# ---------------------------------------------------------------- load
def atomic_write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    """Write to a temp file first, then swap it in, so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def append_history(path: Path, summary: dict, keep: int = 30) -> None:
    history = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []
    history.append({k: summary[k] for k in
                    ("run_id", "finished_at", "version", "trigger", "input_rows",
                     "processed_rows", "rejected_rows", "duration_ms", "status")})
    write_json(path, history[-keep:])


# ---------------------------------------------------------------- orchestration
def run_pipeline(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT,
                 workers: int = 4, latency: float = 0.0,
                 log_path: Path | None = DEFAULT_LOG,
                 trigger: str = os.getenv("SKYROUTE_TRIGGER", "manual"),
                 max_reject_rate: float = MAX_REJECT_RATE) -> dict:
    run_id = uuid.uuid4().hex[:8]
    configure_logging(log_path, run_id)
    timings: dict[str, float] = {}
    started = time.perf_counter()
    _info("main", "pipeline v%s started (trigger=%s, workers=%d)", PIPELINE_VERSION, trigger, workers)

    t = time.perf_counter()
    rows = extract(input_path)
    timings["extract_ms"] = round((time.perf_counter() - t) * 1000, 2)

    t = time.perf_counter()
    valid, rejected = split_valid(rows)
    timings["validate_ms"] = round((time.perf_counter() - t) * 1000, 2)
    for r in rejected:
        _warn("validate", "rejected %s: %s", r.get("order_id") or "<blank>", r["reject_reason"])
    reject_rate = len(rejected) / len(rows) if rows else 0.0

    t = time.perf_counter()
    processed = transform_all(valid, workers, latency)
    timings["transform_ms"] = round((time.perf_counter() - t) * 1000, 2)

    t = time.perf_counter()
    kpis = region_kpis(processed)
    timings["aggregate_ms"] = round((time.perf_counter() - t) * 1000, 2)

    status = "success" if not rejected else "completed_with_rejections"
    if reject_rate > max_reject_rate:
        status = "failed_quality_gate"

    t = time.perf_counter()
    if status != "failed_quality_gate":
        atomic_write_csv(output_dir / "processed_orders.csv", processed,
                         list(processed[0]) if processed else ["order_id"])
        write_json(output_dir / "region_kpis.json", kpis)
    atomic_write_csv(output_dir / "rejected_orders.csv", rejected,
                     REQUIRED + ["reject_reason"])
    timings["load_ms"] = round((time.perf_counter() - t) * 1000, 2)

    reasons: dict[str, int] = {}
    for r in rejected:
        reasons[r["reject_reason"]] = reasons.get(r["reject_reason"], 0) + 1

    summary = {
        "run_id": run_id,
        "version": PIPELINE_VERSION,
        "trigger": trigger,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_file": input_path.name,
        "input_rows": len(rows),
        "processed_rows": len(processed),
        "rejected_rows": len(rejected),
        "reject_rate_pct": round(reject_rate * 100, 2),
        "reject_reasons": reasons,
        "workers": max(1, workers),
        "stage_timings": timings,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "status": status,
    }
    write_json(output_dir / "run_summary.json", summary)
    append_history(output_dir / "run_history.json", summary)

    if status == "failed_quality_gate":
        log.error("reject rate %.1f%% above limit %.1f%%; outputs not published",
                  reject_rate * 100, max_reject_rate * 100, extra={"stage": "quality"})
        raise QualityGateError(summary)
    _info("main", "completed: input=%d processed=%d rejected=%d duration=%.1fms status=%s",
          len(rows), len(processed), len(rejected), summary["duration_ms"], status)
    return summary


def benchmark(input_path: Path, latency: float, worker_counts=(1, 2, 4, 8)) -> list[dict]:
    """Time the transform stage with different worker counts (performance tuning)."""
    rows, _ = split_valid(extract(input_path))
    results = []
    for w in worker_counts:
        t = time.perf_counter()
        transform_all(rows, w, latency)
        ms = round((time.perf_counter() - t) * 1000, 1)
        results.append({"workers": w, "transform_ms": ms})
        print(f"workers={w:<2} transform={ms:>8.1f} ms  rows={len(rows)}")
    base = results[0]["transform_ms"]
    for r in results:
        r["speedup"] = round(base / r["transform_ms"], 2)
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="SkyRoute shipments pipeline")
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--workers", type=int, default=int(os.getenv("SKYROUTE_WORKERS", "4")))
    p.add_argument("--simulate-latency", type=float, default=0.0,
                   help="milliseconds of fake I/O per row")
    p.add_argument("--benchmark", action="store_true")
    args = p.parse_args(argv)
    latency = args.simulate_latency / 1000
    if args.benchmark:
        configure_logging(None, "bench")
        res = benchmark(args.input, latency)
        write_json(args.output / "benchmark.json", res)
        return 0
    try:
        summary = run_pipeline(args.input, args.output, args.workers, latency)
    except QualityGateError:
        return 2
    except FileNotFoundError as exc:
        log.error("input missing: %s", exc, extra={"stage": "extract"})
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
