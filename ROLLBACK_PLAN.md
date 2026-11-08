# SkyRoute Pipeline – Rollback Plan

| Item | Detail |
|---|---|
| Owner | Data engineering on-call |
| Last known good | Latest git tag that passed CI (e.g. `v1.2.1`) |
| Recovery target | Pipeline restored within 30 minutes; at most one scheduled run lost |

## 1. Triggers – roll back when any of these happen
- CI (`pytest`) fails on `main` after a merge.
- `run_summary.json` shows `failed_quality_gate`, or reject rate rises sharply against `run_history.json`.
- Render / Vercel logs show repeated errors (exit code 1 or 2, HTTP 500/422).
- Run duration more than 3× the normal value in the run history.

## 2. Steps
1. **Stop the damage** – suspend the Render cron job (Settings → Suspend) or remove the Vercel cron so no new bad runs start.
2. **Restore the service quickly** – Render: open *Events*, pick the last good deploy, choose *Rollback*. Vercel: *Deployments* → last good deployment → *Instant Rollback*.
3. **Fix the code history** – never rewrite shared history:
   ```bash
   git log --oneline --decorate        # find the bad commit
   git revert <bad-sha>                # new commit that undoes it
   pytest -v                           # must pass
   git tag -a v1.2.1 -m "Hotfix: revert bad change"
   git push origin main --tags         # CI runs, platform redeploys
   ```
4. **Restore data** – code rollback does not undo data that was already written. Copy the outputs of the last good run (CI artifact `pipeline-run-<sha>`) back into `output/`, then rerun the pipeline for the missed day.
5. **Verify** – check the dashboard (`index.html`): status, row counts and timings back to normal; resume the cron job.
6. **Review** – write a short blameless post-incident note and add a unit test that would have caught the fault.

## 3. Safeguards already in place
- Outputs are written atomically (temp file → rename), so a crash never leaves half a file.
- The quality gate stops publishing when more than 10% of rows are rejected.
- Every release is tagged, so the last good version can always be found.
- Secrets (`CRON_SECRET`) live in platform environment variables, not in git.

## 4. Rehearsal evidence
The rollback was rehearsed in this repository: commit "v1.2.0 switch to UK date format" broke validation, the unit tests failed, and `git revert` restored the behaviour (tag `v1.2.1`). See `evidence/` and `git log --graph`.
