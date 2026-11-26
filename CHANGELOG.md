# Changelog

## 26 Nov 2026 (hardening pass)
- **Defect fixed:** `restore()` replayed twice created duplicate tickets (queue 38 to 40) while the persistence assertion (`==` OR `>=`) still passed. Restore is now idempotent and the assertion is exact.
- **Receipts:** expire after 15 minutes; single use is atomic (race-tested); validation failures no longer burn a receipt; ids are letters only.
- **MCP:** streamable-HTTP transport added; transport architecture and hosting limits documented; `mcp` moved into `requirements.txt`; `tools/mcp_demo.py`.
- **Privacy:** poisoned test CSVs now live in a temp folder and are deleted; `.gitignore` excludes runtime artefacts; `tools/scan_repo.py`; evals for every ingestion pathway including the journal, the Pattern Agent vocabulary and browser storage.
- **Voice:** consent notice, processing state, error states per cause; 7 browser tests with a mocked recogniser.
- **Stale facts:** expense ratio, exit load and minimum SIP replies are blocked when the source was last checked more than 60 days ago.
- **Evals:** approval security, privacy pathways and assignment requirements added; total 169 checks.

## 26 Nov 2026 (second pass)
- **Access control:** reviewer login, CSRF tokens, security headers, login rate limit; Render generates the password.
- **Real MCP server** (`mcp_server.py`) with signed single-use approval receipts; optional `MCP_TRANSPORT=stdio` routing from the app.
- **Persistence:** SQLite journal of human decisions, live questions, uploads and canonical explainers, replayed on start-up.
- **Reviews upload** on the Weekly page and `python weekly_job.py newer.csv`; the page states when it is replaying the bundled export.
- **Voice UX:** language selector, confirmation step, errors, intent preview, clarification chips, read-aloud.
- **Reviewer:** also rejects reworded sentences whose phrase order differs from the cited fact.
- **Golden dataset:** `data/golden.csv` hand labels for all 38 questions, compared in Eval 5.
- **Sources:** HDFC scheme addresses moved to `/product-solutions/overview/`; groww.in/pricing and two Help Centre pages re-checked; explainer bullets that no page supported were reworded; manifest split into retrieval, supporting and review sources.
- Total checks: 123.

## 26 Nov 2026 (fixes after an independent review)
- **Fact fix:** DP charges are per sell order, not per stock per day (checked against the Groww Help Centre FAQ).
- **Fact refresh:** expense ratios Mid Cap 0.73%, Large Cap 0.99%, ELSS 1.18% (Small Cap 0.79% and Gold FoF 0.20% unchanged), checked on the HDFC pages.
- **PII:** reviews are now redacted inside `pipeline.load_reviews`, so the Pattern Agent index can no longer hold raw text; IFSC and UPI patterns added.
- **Reviewer:** new `UNSUPPORTED_CLAIM` check (sentence must be backed by the retrieved fact; absolute wording such as "always" or "zero" rejected), also applied to human edits.
- **Fee count:** brokerage matching no longer counts every use of "charges" (41 became 21); the 366 figure is explained (1,067 records, 630 distinct, 366 after the length filter).
- **Evals:** a fourth section of 10 regression checks; total 65/65. Evals report Q-010 label corrected (refusal plus the exit-load fact).

## Capstone (Nov 2026)
- Added weekly loop inside the app, queue, the two-way connection, per-action gates, human edit path.
- Added Overview dashboard, Sources, Approvals, Canonical explainers, Evals pages.
- Added three evaluations (55 checks), samples, unit tests, CI, scheduled weekly run, Docker, optional n8n workflow.
- Fixed: return-figure questions now refused; canonical lookup and topic counting agree; canonical bullet matching ignores generic words.
- Reviews export replaced (8,629 rows with stable ids).

## Milestone 3: Multi-Agent Support Desk
Three parallel agents, orchestrator, reviewer, refinement (max 5), approval-gated record and email draft.

## Milestone 2: Product Insights Copilot
Review clustering, weekly pulse, fee explainer, approval-gated MCP workflow.

## Milestone 1: Mutual Fund FAQ Assistant
Cited RAG corpus over official pages with a facts-only refusal.
