# Deployment plan

| Mode | Command / file | Status |
|---|---|---|
| Local | `python app.py` | Tested |
| Production server | `gunicorn app:app --workers 1 --threads 4 --timeout 120` (`Procfile`) | Start-up and routes tested locally; peak memory about 190 MB |
| Render (free) | `render.yaml` | Config provided; **deploy yourself** (steps below) |
| Docker | `Dockerfile`, `docker-compose.yml` | Provided; built by you (not built in the authoring sandbox) |
| CI | `.github/workflows/ci.yml` | Unit tests + all three evals on every push |
| Schedule | `.github/workflows/weekly.yml`, `n8n-workflow.json` | Weekly headless run / optional trigger of the hosted app |

## Environment variables
| Name | Default | Meaning |
|---|---|---|
| `PORT` | 5000 | HTTP port |
| `WEEKLY_TOKEN` | unset | `POST /api/weekly/run` is **disabled (403) unless this is set**; callers must send it as header `X-Token` (constant-time check) |
| `REAL_CLOCK` | 0 | `1` stamps new questions with real time instead of the demo clock (pinned to the end of the reviews export) |
| `DESK_OUT`, `DESK_LOGS` | `outputs/`, `logs/` | Where approved writes and desk logs go |
| `CORPUS_LAST_CHECKED` | 22 Oct 2026 | Fallback date; per-source dates live in `data/source_checks.json` |
| `GROQ_API_KEY`, `USE_LLM`, `GROQ_MODEL` | unset | Optional LLM rephrasing (untested) |

## Pre-deployment checklist
- [ ] `python -m unittest discover -s tests -v` passes (5 tests)
- [ ] `python -m evals.run_evals` prints 13/13, 16/16, 26/26
- [ ] `data/source_checks.json` dates updated after re-opening each source page
- [ ] No `.env` committed; `.env.example` has placeholders only
- [ ] README top line has the live URL

## Render (free tier)
1. Push to a **new** GitHub repo (keeps Milestone 3 intact).
2. Render → New → Web Service → select the repo → it reads `render.yaml`.
3. Wait for the build, open the URL, check `/healthz`, then open **Overview**.
4. Free instances sleep after inactivity and reset in-memory state; open the app a minute before reviewing.

## Docker
```bash
docker compose up --build        # http://localhost:5000
```

## Scheduling the weekly loop
- **GitHub Actions** (`weekly-loop`): cron Monday 03:30 UTC (09:00 IST); runs `weekly_job.py`, uploads the result JSON, optionally calls the hosted app.
- **n8n** (`n8n-workflow.json`, optional, **untested**): Cron → HTTP `POST /api/weekly/run` → IF checks passed → notification. Import it into n8n and set the app URL and token.
- The hosted app also runs the weekly loop once at start-up. The run writes nothing; its two writes remain pending.

## Rollback
Redeploy the previous commit on Render; no migrations or stored data exist.


## Additions (26 Nov 2026)
| Variable | Purpose |
|---|---|
| `REVIEWER_PASSWORD` | Turns on reviewer-only actions. `render.yaml` generates one; read it in the Render dashboard (Environment) and share it only with reviewers. |
| `SECRET_KEY` | Signs the session cookie (generated on Render). |
| `COOKIE_SECURE` | `1` on HTTPS (also turns on HSTS). |
| `PROXY_HOPS` | Number of trusted reverse proxies (`1` on Render, `0` locally/Docker). The login rate limit uses the address the trusted proxy appended, never a raw `X-Forwarded-For` header. |
| `MCP_TRANSPORT` | `stdio` routes approved writes through `mcp_server.py` (needs `requirements-mcp.txt`). |
| `APPROVAL_SECRET` | Key for MCP approval receipts (otherwise generated into the output folder). |
| `DESK_DB` | SQLite journal path (default `logs/state.db`). |

**Persistence.** Human decisions, live questions, uploaded reviews and canonical explainers are journalled in SQLite and replayed at start-up. The database survives a restart only on a persistent disk: Docker (`docker-compose.yml` mounts `./data_state`), a Render paid disk (mount it and set `DESK_DB` and `DESK_OUT` onto it), or any VM. **On Render's free tier the filesystem is ephemeral, so a redeploy or sleep-and-rebuild still starts fresh.**


## Hosted architecture (which processes exist)
- **One process is enough for the demo:** `gunicorn app:app --workers 1 --threads 4` (one worker because state is in memory plus the SQLite journal; do not raise it). MCP runs in-process by default.
- **Optional second process:** `mcp_server.py --transport streamable-http` only if you want an outside MCP client. It must share the output folder and `APPROVAL_SECRET` with the web app, so run it in the same container (e.g. a process manager) or on the same VM; a separate Render service would not share the filesystem.
- **Scheduler:** the GitHub Action (`weekly.yml`) runs `weekly_job.py` and can ping `/api/weekly/run` with `WEEKLY_TOKEN`; n8n is an untested alternative.
- **State that must persist:** `logs/state.db` (journal), `outputs/` (approved writes), `logs/uploaded_reviews.csv`. Mount a persistent disk and set `DESK_DB`, `DESK_OUT`, `DESK_LOGS` onto it. Without a disk the app still works but starts fresh after a restart.
- **Health check:** `GET /healthz`.
- **Dependencies:** `requirements.txt` now includes `mcp`; the Docker image and both Actions install it. A fresh-environment install could not be reproduced in the authoring sandbox (no package index access); the installed versions satisfy the pins (flask 3.1, pandas 3.0, scikit-learn 1.9, mcp 2.3). `gunicorn` was not installed locally, so the production start command itself was not executed here.
- **Not claimed:** no public URL, no Google Docs or Gmail connection, no deployed MCP HTTP service.
