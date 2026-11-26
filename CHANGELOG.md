# Changelog

## 26 Nov 2026 (owner decisions before deployment)
- **Unconfirmed facts blocked:** answers citing a fact outside a page's recorded check scope (benchmark, riskometer, lock-in, fund manager, objective on the HDFC scheme pages) are still drafted, but print "Last checked: not confirmed (official source check pending)" instead of the page's 26 Nov date and fail review with `UNCONFIRMED_SOURCE` only, so approval is refused. A "not confirmed" footer on a verified fact still fails `MISSING_LAST_CHECKED`. The reply parser now treats a dateless footer as a footer, not a sentence.
- **Evals (approved expectation changes, nothing else loosened):** feasibility now requires the 4 unconfirmed-source questions (Q-014, Q-024, Q-037, Q-038) to be flagged `UNCONFIRMED_SOURCE` only while every other question stays unflagged, plus a new check that their approval is refused; the PII check still requires full redaction and allows only `UNCONFIRMED_SOURCE` as a review failure. Every eval detail is now redacted before it is written (a failing check had copied a fake OTP into a report), with a new regression check. Totals: 177/177; unit tests 40 run, 33 pass, 7 voice skipped.
- **Disclosures:** voice browser tests skipped (Playwright not installed, by decision); Render free plan, state not durable; dependencies not pinned, `PYTHON_VERSION=3.11.9` explicit. README deploy steps now say Render **Blueprint**.

## 26 Nov 2026 (Claude Code audit and fixes)
Work moved from Claude Chat to Claude Code. The folder was put under git (baseline commit 40f8381 = the handed-over state); each step below is its own commit with regression tests that fail on the previous code. No existing test or eval assertion was weakened.
- **Security, receipts:** single use was not atomic on Windows (rename claim; concurrent renames all "succeeded"), so one approval could authorise several MCP writes. Now an exclusive-create claim; losers get a clean refusal.
- **Data integrity, weekly approvals:** re-running identical content reopened an approved action (duplicate doc entry, canonical v2). Approved actions are final; rejected ones are re-offered under a new id. The run id also hashes the explainer.
- **Data integrity, decisions:** approved and journalled only after the writes succeed; retries never duplicate a write.
- **Access (owner's decision):** live desk reviewer-only and fail closed (no open demo mode); every change, including adding a question, needs a reviewer; public read-only `/demo` on synthetic sample data (`make_demo.py`); `/healthz` no longer reports counts.
- **Weekly API:** `/api/weekly/run` disabled unless `WEEKLY_TOKEN` is set; constant-time check.
- **Hardening:** login rate limit no longer trusts `X-Forwarded-For` (`PROXY_HOPS` for real proxies); Content-Security-Policy with per-request nonces; HSTS on HTTPS; `.dockerignore` keeps the signing key, receipts and runtime state out of images; login redirect rejects `/\host`.
- **Persistence:** refinements (redacted) and re-drafts journalled and replayed; an accepted edit restored after the stale date keeps its wording but stays blocked.
- **Sources (owner's decision, no dates invented, 60 days unchanged):** `verification.py` warns wherever a source is overdue, unconfirmed or due soon; `field_scope` records that the HDFC scheme pages were checked on 26 Nov only for expense ratio, minimum SIP and exit load; `tools/source_status.py` writes SOURCE_VERIFICATION.md; the DP explainer cites the DP FAQ page actually checked.
- **CI and tooling:** `weekly.yml` did not parse and used `secrets` in a step `if:`; the evals crashed on Windows (SQLite connections never closed); `scan_repo.py` scans what git would publish; `make_evals_report.py` writes UTF-8 and states facts about the run (voice tests skipped, platform, source status); render.yaml states that the free plan loses state.
- **Evals:** 175 checks (3 access checks, 2 source-verification checks, and a strict companion to an existing brokerage-count check that could never fail, which is kept unchanged). Unit tests: 37 (30 pass, 7 voice skipped without Playwright).

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
