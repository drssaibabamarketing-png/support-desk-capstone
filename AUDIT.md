# Audit status (26 Nov 2026, after the Claude Code audit)

**Verdict: NOT SUBMISSION READY until the manual steps below are done.** The previous audit text is in git history (commit 40f8381).

## Tested here (reproducible, Python 3.14.7 on Windows 11)
- Unit tests: 30 pass, 7 skipped (`python -m unittest discover -s tests`). The 7 skipped are the voice browser tests: Playwright is not installed here, so they did not run, including the login step added to them.
- Evals: 175/175 in ten groups (`python -m evals.run_evals`). Before the SQLite fix this command crashed on Windows.
- `EVALS_REPORT.md` regenerated from that run (`python make_evals_report.py`).
- `python tools/scan_repo.py`: clean (it now scans what git would publish; ignored runtime files are counted, not scanned).
- `python tools/source_status.py`: 5 sources unconfirmed (the HDFC scheme pages, outside the fields checked on 26 Nov), 0 overdue.
- MCP: real SDK server (installed here: `mcp` 2.1.1; `requirements.txt` allows `>=2.0,<3`) over stdio and streamable HTTP, inside the eval run.
- Every fix has a regression test that fails on the previous code (see CHANGELOG).

## Not verified
- **Voice:** not run at all in this environment (Playwright missing); previously a mocked recogniser only. No live microphone test.
- **CSP in a real browser:** the header and nonces are tested; that the two inline scripts still run in a browser is not (needs Playwright or a manual check).
- Clean-environment `pip install` on Python 3.11 (the Docker and CI version), gunicorn, Docker build, n8n, GitHub Actions runs, any deployed URL.

## Known limits
Synthetic questions and author-written golden labels; deterministic replies (LLM path untested); reviewer support check is word-based, not semantic; one shared reviewer password, no per-user audit; a ticket approval covers its two writes (record + draft); HTTP MCP transport has no auth of its own; the hosted default writes in-process (the receipt-checked MCP server is used only with `MCP_TRANSPORT=stdio`); persistence needs a persistent disk (render.yaml is on the free plan, which loses state); weekly data is a replay unless a CSV is uploaded; dependencies are not pinned.

## Manual steps (need a person)
1. **Sources:** open the five HDFC scheme pages and confirm benchmark, riskometer, fund manager, objective and lock-in (record the fields in `data/source_checks.json` `field_scope`); confirm the mid-cap scheme's official name (SOURCES.md); re-check the twelve pages dated 22 Oct before 21 Dec 2026 and every page before 26 Jan 2027, or time-sensitive replies are blocked from then on.
2. **Deploy:** push to GitHub; deploy on Render; decide free plan (state lost on redeploy) or a paid disk (see render.yaml); set `REVIEWER_PASSWORD` (Render generates it), `WEEKLY_TOKEN` and `PROXY_HOPS=1`; add the live URL to the README.
3. **Voice:** install Playwright (`pip install playwright && python -m playwright install chromium`) and run `python -m unittest tests.test_voice_browser`; then the manual microphone check in Chrome or Edge (docs/ui-guide.md), logged in as the reviewer.
4. **Demo video** (script in docs/ui-guide.md), recorded logged in as the reviewer; upload to Drive, "Anyone with the link".
5. Paste GitHub links of EVALS_REPORT.md and SOURCES.md into the portal.
