"""Turns evidence/*.txt terminal captures into terminal-style PNGs and draws
the parallel-processing benchmark chart used in the report."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
FONT = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 26)
BG, FG, CMD, WARN, ERR, OK = "#1e1e1e", "#d4d4d4", "#4fc1ff", "#dcdcaa", "#f48771", "#89d185"


def colour(line: str) -> str:
    if line.startswith("$"):
        return CMD
    if "ERROR" in line or "FAILED" in line or "failed" in line or "HTTP 401" in line or "exit code: 1" in line or "exit code: 2" in line:
        return ERR
    if "WARNING" in line:
        return WARN
    if "passed" in line or "PASSED" in line or "HTTP 200" in line:
        return OK
    return FG


def render(txt: Path, title: str, max_lines: int = 60, width: int = 118) -> None:
    lines = txt.read_text(encoding="utf-8").splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + ["..."]
    lines = [l if len(l) <= width else l[:width - 3] + "..." for l in lines]
    lh, pad, bar = 32, 24, 46
    w = int(FONT.getlength("M") * width) + pad * 2
    h = bar + pad * 2 + lh * len(lines)
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, bar], fill="#323233")
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        d.ellipse([16 + i * 26, 15, 32 + i * 26, 31], fill=c)
    d.text((110, 10), title, font=FONT, fill="#cccccc")
    for i, line in enumerate(lines):
        d.text((pad, bar + pad + i * lh), line, font=FONT, fill=colour(line))
    img.save(txt.with_suffix(".png"))


def benchmark_chart() -> None:
    data = json.loads((ROOT / "output" / "benchmark.json").read_text())
    w = [str(r["workers"]) for r in data]
    ms = [r["transform_ms"] / 1000 for r in data]
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=200)
    bars = ax.bar(w, ms, color="#1b3a8c", width=0.55)
    for b, r in zip(bars, data):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.08,
                f"{r['transform_ms'] / 1000:.2f} s  (x{r['speedup']})", ha="center", fontsize=8)
    ax.set_xlabel("Parallel worker threads")
    ax.set_ylabel("Transform stage time (s)")
    ax.set_title("Transform time for 233 rows with 20 ms simulated I/O per row", fontsize=9.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(EV / "04_parallel_benchmark_chart.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    titles = {
        "01_pipeline_run_log": "Terminal - manual run (logging)",
        "02_run_summary": "Terminal - run_summary.json (monitoring)",
        "03_unit_tests_pass": "Terminal - pytest unit tests",
        "04_parallel_benchmark": "Terminal - performance benchmark",
        "05_bad_release_tests_fail": "Terminal - faulty release v1.2.0",
        "06_quality_gate_blocks_release": "Terminal - quality gate",
        "07_rollback_revert_tests_pass": "Terminal - rollback with git revert",
        "08_git_history": "Terminal - git history and tags",
        "09_missing_input_retry": "Terminal - missing input, retry logic",
        "10_serverless_function_test": "Terminal - serverless /api/run test",
        "12_deployment_config": "Editor - Render and Vercel deployment config",
    }
    for stem, title in titles.items():
        render(EV / f"{stem}.txt", title)
    benchmark_chart()
    shot = EV / "11_dashboard.png"
    im = Image.open(shot)
    if im.height > 1480:
        im.crop((0, 0, im.width, 1470)).save(shot)
    print("evidence images written")
