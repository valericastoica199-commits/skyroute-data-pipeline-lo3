"""Unit and integration tests for the SkyRoute pipeline (run with: pytest -v)."""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pipeline  # noqa: E402
from pipeline import (QualityGateError, region_kpis, run_pipeline, split_valid,  # noqa: E402
                      transform, transform_all, validate)


def make_row(**overrides):
    row = {"order_id": "SR1", "order_date": "2026-10-01", "region": "North",
           "depot": "Leeds", "carrier": "SwiftHaul", "status": "Delivered",
           "order_value": "20", "items": "2", "weight_kg": "3.5",
           "promised_days": "2", "actual_days": "2"}
    row.update(overrides)
    return row


# ---------- validation rules
def test_valid_row_passes():
    assert validate(make_row()) is None


@pytest.mark.parametrize("field,value,reason", [
    ("order_value", "-2", "values out of range"),
    ("order_date", "31/10/2026", "invalid order_date"),
    ("region", "Central", "unknown region"),
    ("status", "Lost?", "unknown status"),
    ("items", "three", "must be numeric"),
    ("order_id", "  ", "empty order_id"),
    ("weight_kg", "", "must be numeric"),
])
def test_bad_rows_are_rejected(field, value, reason):
    assert reason in validate(make_row(**{field: value}))


def test_missing_column_reported():
    row = make_row()
    del row["carrier"]
    assert validate(row) == "missing column(s): carrier"


def test_delivered_needs_actual_days():
    assert "actual_days required" in validate(make_row(actual_days=""))


def test_in_transit_without_actual_days_is_fine():
    assert validate(make_row(status="In Transit", actual_days="")) is None


def test_duplicates_are_rejected():
    valid, rejected = split_valid([make_row(), make_row()])
    assert len(valid) == 1
    assert rejected[0]["reject_reason"] == "duplicate order_id"


# ---------- transformation
def test_transform_value_per_item_and_on_time():
    out = transform(make_row(order_value="25", items="5", actual_days="3", promised_days="2"))
    assert out["value_per_item"] == "5.00"
    assert out["on_time"] == "no"


def test_parallel_matches_sequential_order():
    rows = [make_row(order_id=f"SR{i}", order_value=str(i + 1)) for i in range(50)]
    assert transform_all(rows, workers=1) == transform_all(rows, workers=8)


def test_region_kpis():
    rows = [transform(make_row(order_id="A")), transform(make_row(order_id="B", actual_days="4"))]
    north = next(k for k in region_kpis(rows) if k["region"] == "North")
    assert north["orders"] == 2 and north["on_time_rate"] == 50.0


# ---------- end-to-end
def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_end_to_end_run(tmp_path):
    src = tmp_path / "in.csv"
    _write_csv(src, [make_row(order_id=f"SR{i}") for i in range(20)] + [make_row(order_id="BAD", region="Mars")])
    summary = run_pipeline(src, tmp_path / "out", workers=4, log_path=None)
    assert summary["processed_rows"] == 20 and summary["rejected_rows"] == 1
    assert json.loads((tmp_path / "out" / "run_summary.json").read_text())["status"] == "completed_with_rejections"
    assert len(json.loads((tmp_path / "out" / "run_history.json").read_text())) == 1


def test_quality_gate_blocks_bad_batch(tmp_path):
    src = tmp_path / "in.csv"
    _write_csv(src, [make_row(order_id=f"SR{i}", region="Mars") for i in range(5)] + [make_row()])
    with pytest.raises(QualityGateError):
        run_pipeline(src, tmp_path / "out", log_path=None, max_reject_rate=0.10)
    assert not (tmp_path / "out" / "processed_orders.csv").exists()


def test_missing_input_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)
    with pytest.raises(FileNotFoundError):
        run_pipeline(tmp_path / "nope.csv", tmp_path / "out", log_path=None)
