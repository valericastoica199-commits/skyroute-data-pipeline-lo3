"""Builds the synthetic SkyRoute shipments dataset (data/orders.csv).

The data is made up but realistic. A fixed random seed keeps it the same on
every run, and a small number of faulty rows are added on purpose so the
validation and troubleshooting steps have something to catch.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "orders.csv"

REGIONS = {
    "North": ["Leeds", "Newcastle"],
    "South": ["Southampton", "Brighton"],
    "East": ["Norwich", "Cambridge"],
    "West": ["Bristol", "Cardiff"],
}
CARRIERS = ["SkyRoute Fleet", "ParcelLink", "SwiftHaul"]
STATUSES = ["Delivered", "Delivered", "Delivered", "In Transit", "Delayed", "Processing"]
FIELDS = ["order_id", "order_date", "region", "depot", "carrier", "status",
          "order_value", "items", "weight_kg", "promised_days", "actual_days"]


def build_rows(n: int = 240, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    start = date(2026, 9, 1)
    rows = []
    for i in range(n):
        region = rng.choice(list(REGIONS))
        status = rng.choice(STATUSES)
        items = rng.randint(1, 12)
        promised = rng.choice([1, 2, 3, 5])
        if status == "Delivered":
            actual = str(max(1, promised + rng.choice([-1, 0, 0, 0, 1, 2])))
        elif status == "Delayed":
            actual = str(promised + rng.randint(1, 4))
        else:
            actual = ""  # not delivered yet
        rows.append({
            "order_id": f"SR{10001 + i}",
            "order_date": (start + timedelta(days=rng.randint(0, 60))).isoformat(),
            "region": region,
            "depot": rng.choice(REGIONS[region]),
            "carrier": rng.choice(CARRIERS),
            "status": status,
            "order_value": f"{rng.uniform(15, 900):.2f}",
            "items": str(items),
            "weight_kg": f"{items * rng.uniform(0.4, 6.5):.1f}",
            "promised_days": str(promised),
            "actual_days": actual,
        })

    # Faulty rows injected on purpose (each one tests a different rule).
    rows[17]["order_value"] = "-45.00"           # negative value
    rows[42]["order_date"] = "31/10/2026"        # wrong date format
    rows[63]["region"] = "Central"               # unknown region
    rows[88]["items"] = "three"                  # non-numeric
    rows[101]["order_id"] = ""                   # missing key
    rows[150]["status"] = "Lost?"                # unknown status
    rows[199]["weight_kg"] = ""                  # missing weight
    rows.append(dict(rows[120]))                 # exact duplicate order_id
    return rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
