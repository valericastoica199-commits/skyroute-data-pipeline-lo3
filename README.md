# SkyRoute Logistics – Task 3 (LO3) Data Pipeline Project

Shipments reporting pipeline used as evidence for the Task 3 report
(deployment methods, pipeline features, troubleshooting, version control and rollback).

## Folder contents
| Path | Purpose |
|---|---|
| `data/orders.csv` | Synthetic SkyRoute dataset – 241 shipments, 8 faulty rows added on purpose |
| `scripts/generate_dataset.py` | Rebuilds the dataset (fixed seed) |
| `src/pipeline.py` | Extract → validate → transform (parallel) → aggregate → load → log |
| `tests/test_pipeline.py` | 18 unit / integration tests (pytest) |
| `api/run.py`, `vercel.json` | Serverless deployment (Vercel Function + Vercel Cron) |
| `render.yaml` | Render Blueprint: web service (dashboard + `/api/run`) and Cron Job (02:00 UTC) |
| `server.py` | Web server used by Render: serves the dashboard, `/healthz`, `/api/run` |
| `run_pipeline.bat` / `.sh` | Manual deployment |
| `.github/workflows/ci.yml` | GitHub Actions: tests + smoke run on every push / PR |
| `index.html` | Operations dashboard (reads `output/*.json`) |
| `ROLLBACK_PLAN.md` | Rollback triggers and steps |
| `diagrams/*.drawio` | draw.io source of every diagram (open in app.diagrams.net) |
| `evidence/` | Terminal outputs and screenshots used in the report |
| `report/` | Final Word report |

## Run locally (Python 3.10+)
```bash
pip install -r requirements.txt
python src/pipeline.py --workers 4                    # manual run
python src/pipeline.py --benchmark --simulate-latency 5   # parallel tuning test
pytest -v                                             # unit tests
python -m http.server 8000                            # then open http://localhost:8000
```
Expected result: 241 input rows, 233 processed, 8 rejected, status `completed_with_rejections`.
Exit codes: `0` ok, `1` input missing, `2` quality gate failed (more than 10% rejected).

## Deploy
### Render (step by step)
1. Create an empty GitHub repository (e.g. `skyroute-pipeline`) and push this folder:
   ```bash
   git remote add origin https://github.com/<your-user>/skyroute-pipeline.git
   git push -u origin main --tags
   ```
2. In Render: **New → Blueprint** → connect GitHub → choose the repo → **Apply**.
   `render.yaml` creates:
   - `skyroute-pipeline-dashboard` – free web service. Build runs `pytest`; start runs `gunicorn api.app:app` (Flask app in `api/app.py`),
     which runs the pipeline once and serves the dashboard at `https://<name>.onrender.com`.
   - `skyroute-orders-pipeline` – cron job, every day 02:00 UTC (paid service type; delete that block
     in `render.yaml` first if you have no payment method on Render).
3. Test the on-demand run: copy `CRON_SECRET` from the web service's **Environment** tab, then click
   *Trigger /api/run* on the dashboard, or:
   `curl -H "Authorization: Bearer <CRON_SECRET>" https://<name>.onrender.com/api/run`
4. Evidence screenshots for the report: **Events** (deploy history), **Logs**, **Environment**, the live
   dashboard, and a **Rollback** to an earlier deploy from the Events page.

Run the Render web server locally: `python server.py` → http://localhost:8000

### Vercel (serverless)
`vercel` CLI or import the repo in Vercel. Add env var `CRON_SECRET`. The dashboard is served from `index.html`; `/api/run` runs the pipeline.

## Version control
```bash
git log --oneline --graph --decorate --all
git tag -n
```
Branches are merged through pull requests after CI passes; releases are tagged (`v1.0.0`, `v1.1.0`, `v1.2.1`).
See `ROLLBACK_PLAN.md` for how a bad release is undone.
