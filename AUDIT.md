# Final audit (26 Nov 2026)

**Verdict: NOT SUBMISSION READY until the manual steps below are done. The code and repository are ready.**

## Tested here (reproducible)
- Unit/browser tests: 13/13 (`python -m unittest discover -s tests`).
- Evals: 169/169 in ten groups (`python -m evals.run_evals`).
- App start, `/healthz` 200, unauthenticated POST refused (400 without CSRF token).
- `python tools/scan_repo.py`: clean (no PII, secrets, databases, receipts or poison files; two reviewed files allowlisted: placeholder address and fake test PII).
- MCP: real SDK (v2.3.0) server tested over stdio and streamable HTTP: discovery, refusal without receipt, tampered and replayed receipts, expiry, validation failure, PII refusal, audit line. No Google Docs or Gmail is connected; tools write local files and an unsent .eml.
- Defect fixed: restore replayed twice (queue 38 to 40) while the assertion accepted it; code made idempotent, assertion strict.

## Not verified
- **Voice:** mocked recogniser only. No live microphone test.
- Clean-environment `pip install`, gunicorn, Docker build, n8n workflow, any deployed URL (no network or daemon in the sandbox).
- No git history exists in the folder, so none could be inspected.

## Known limits
Synthetic questions and author-written golden labels; deterministic replies (LLM path untested); reviewer support check is word-based, not semantic; one shared reviewer password; a ticket approval covers its two writes (record + draft); HTTP MCP transport has no auth of its own; persistence needs a persistent disk; weekly data is a replay unless a CSV is uploaded.

## Manual steps
1. Push to GitHub; deploy on Render with a persistent disk; set REVIEWER_PASSWORD; add the live URL to the README.
2. Manual microphone check in Chrome or Edge (docs/ui-guide.md).
3. Record the 5-minute demo (script in docs/ui-guide.md); upload to Drive, "Anyone with the link".
4. Re-check source dates not re-opened on 26 Nov (SOURCES.md).
5. Paste GitHub links of EVALS_REPORT.md and SOURCES.md into the portal.
