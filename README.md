<div align="center">

# The Support Desk

**One system for support and product: reviews become themes, questions become cited drafts, and the weekly fee explainer becomes the answer support reuses. A human approves every write.**

![Python](https://img.shields.io/badge/python-3.11-0F8B6D) ![Flask](https://img.shields.io/badge/flask-3-0F8B6D) ![Evals](https://img.shields.io/badge/evals-177%2F177-0F8B6D) ![Tests](https://img.shields.io/badge/unit%20tests-33%20pass%20%C2%B7%207%20voice%20skipped-0F8B6D) ![License](https://img.shields.io/badge/license-MIT-5C6963)

NextLeap Applied Generative AI Bootcamp · Cohort 7 · Capstone · Product: **Groww** with **HDFC Mutual Fund** schemes

**Live prototype:** _add your Render URL here_ &nbsp;·&nbsp; **Docs:** [`docs/`](docs/) &nbsp;·&nbsp; **Evals:** [`outputs/evals/`](outputs/evals/)

<img src="docs/screenshots/01-overview.png" alt="Overview dashboard" width="880">

</div>

## Submission deliverables
| Portal field | Where |
|---|---|
| GitHub repository | this repo |
| Deployed application link | top of this README (add after the Render deploy) |
| 5 minute demo video | Google Drive link, access "Anyone with the link"; script in [docs/ui-guide.md](docs/ui-guide.md) |
| Evals report (golden dataset, adversarial tests, scores) | [EVALS_REPORT.md](EVALS_REPORT.md) |
| Source manifest (30+ official URLs) | [SOURCES.md](SOURCES.md) |

## Contents
[The problem](#the-problem) · [What it does](#what-it-does) · [The connection](#the-connection-between-the-loops) · [Architecture](#architecture) · [Screens](#screens) · [Quick start](#quick-start) · [MCP and the approval gate](#mcp-and-the-approval-gate) · [Scope enforcement](#scope-enforcement-in-code) · [Evaluation](#evaluation) · [The fee issue](#the-fee-issue-from-the-reviews) · [Samples](#samples) · [Documentation](#documentation) · [Repository layout](#repository-layout) · [Design decisions](#design-decisions) · [Known limits](#known-limits) · [Deploy](#deploy)

## The problem
Support answers the same fee question dozens of times a month, writing it fresh each time and sometimes getting it wrong. Product reads a dashboard that says "pricing confusion is up" without saying **which** fee or what support has been telling people. The missing data is in three places: what the official documents say, what users are confused about, and how often. This project puts all three behind one system.

## What it does
| | Weekly loop (product) | Response loop (support) |
|---|---|---|
| **In** | Reviews CSV, newest 7 days (366 usable reviews, 22–29 Aug 2026) | Queue of user questions |
| **Work** | ≤5 themes → top 3 → the recurring fee confusion | Three agents in parallel (Facts, Pattern, Compliance) → orchestrator → reviewer |
| **Out** | Pulse ≤250 words with quotes, counts, review ids and 3 actions; fee explainer ≤6 bullets with 2 official links and a last-checked date | Reply ≤3 sentences with one source link and last-checked date, plus an internal routing note |
| **Human** | Approves the doc append and the email draft **separately** | Approves, edits or rejects each draft |

Nothing is written or sent without a human approving that specific action. Email is created as an unsent draft.

## The connection between the loops
<img src="docs/img/connection.png" alt="The two connections" width="760">

1. **Questions → pulse.** A topic asked **5 or more times** inside the weekly window appears in the pulse as a "Support desk signal" (in the shipped queue: *Groww brokerage and charges* ×8, *HDFC scheme exit load* ×5).
2. **Explainer → answers.** When a human approves the weekly doc entry, its fee explainer becomes the **canonical answer**. The Facts agent then answers matching fee questions with the best-fitting approved bullet and its link, and the routing note says *"REUSED canonical explainer … v1, not drafted fresh"*. The **Canonical explainers** page lists every ticket that reused it.

## Architecture
<img src="docs/img/system.png" alt="System architecture" width="760">

More diagrams (weekly sequence, response sequence, approval states) in [docs/architecture.md](docs/architecture.md).

## Screens
| | |
|---|---|
| <img src="docs/screenshots/03-weekly-pulse.png" alt="Weekly pulse"> **Weekly pulse:** themes with expandable review ids, quotes, nine checks, two approval cards | <img src="docs/screenshots/05-ticket-canonical.png" alt="Ticket"> **Ticket:** canonical reuse, edit, reviewer, the two writes listed before approval |
| <img src="docs/screenshots/04-approvals.png" alt="Approvals"> **Approvals:** exact content and audit log | <img src="docs/screenshots/06-canonical.png" alt="Canonical explainers"> **Canonical explainers** and where they were reused |
| <img src="docs/screenshots/02-queue.png" alt="Queue"> **Queue:** intent, draft, citation, reviewer flag | <img src="docs/screenshots/08-sources.png" alt="Sources"> **Sources:** every link with its last-checked date |

| <img src="docs/screenshots/11-voice-clarify.png" alt="Voice and clarification"> **Voice:** language, confirmation, intent preview, clarification chips | <img src="docs/screenshots/12-weekly-upload.png" alt="Weekly data source"> **Weekly data:** states it is a replay; upload a newer CSV |
| <img src="docs/screenshots/10-login.png" alt="Reviewer login"> **Reviewer login:** the live desk is reviewer-only; everyone else sees the public sample demo (`/demo`) | |

Also: Overview (above), Evals, Written files. UI guide and a 3-minute demo script: [docs/ui-guide.md](docs/ui-guide.md).

## Quick start
```bash
pip install -r requirements.txt          # requirements-dev.txt adds the test-only extras
python app.py                         # http://localhost:5000
python -m unittest discover -s tests -v
python -m evals.run_evals             # regenerates outputs/evals/*
python make_samples.py                # regenerates outputs/samples/*
python mcp_server.py                  # the MCP server (stdio); normally started by an MCP client
python tools/mcp_demo.py              # discovery + refused / allowed / replayed calls over the real protocol
python tools/scan_repo.py             # pre-submission scan of what git would publish: PII, secrets, stray generated files
python tools/source_status.py --write # lists official sources needing manual verification (exit 1 while any is overdue/unconfirmed)
REVIEWER_PASSWORD=choose-one python app.py   # the live desk needs it; without it only the public sample demo (/demo) is available
python make_demo.py                   # rebuilds data/demo_snapshot.json, the only data the public demo shows
python weekly_job.py                  # the scheduled, headless weekly run
docker compose up --build             # optional
```
No API key is needed: the agents are rules and retrieval. Environment variables are listed in [`.env.example`](.env.example).

**Try it (90 seconds):** Weekly pulse → read the pulse → expand *Exact content* → approve **only** the doc action → Queue → add *"Why was brokerage deducted again when I sold my shares?"* → see *REUSED canonical explainer* → Approvals shows the email action still pending.

## What was added after an independent review (26 Nov)
| Area | Now |
|---|---|
| Access | Reviewer login + CSRF + security headers. The live queue, tickets, weekly actions, approvals, audit log and written files are reviewer-only; every change, including adding a question, needs a reviewer. The public sees a read-only demo built from synthetic sample data (`make_demo.py` → `data/demo_snapshot.json`). No password set = live desk closed (fail closed) |
| MCP | A **real MCP server** (`mcp_server.py`, stdio) that refuses any write without a signed, single-use human-approval receipt |
| Persistence | SQLite journal replayed at start-up (approvals, refinements, re-drafts, edits, live questions, canonical explainers, uploaded reviews; text is stored redacted) |
| Weekly data | Upload a newer reviews CSV on the Weekly page, or `python weekly_job.py newer.csv`; the page says when it is a replay |
| Voice | Consent notice (the browser may send audio to Google or Microsoft), English / Hindi / Kannada and more, listening / processing / success / error states, transcript review before submission, retry and typed fallback, clarification chips, read-aloud. Tested with a **mocked** recogniser in a real browser engine; **not** tested with a live microphone |
| Facts | DP charges per sell order; five expense ratios and three source pages re-checked on 26 Nov |
| Reviewer | Also rejects sentences unsupported by the cited fact, including reworded or reordered ones |
| Evals | 177 checks in ten groups, including a 38-question hand-labelled golden dataset |

## What changed in the Claude Code audit (26 Nov)
| Area | Defect found | Now |
|---|---|---|
| Approval receipts | On Windows, single use was not atomic (a rename claim): one approval could authorise several MCP writes | Exclusive-create claim; 1 winner in 1,000 concurrent rounds; losers get a clean refusal |
| Weekly approvals | Re-running identical content turned an approved action back to pending; approving again duplicated the doc entry and bumped the canonical version | Approved actions are never re-offered; rejected ones are re-offered under a new id with the rejection kept |
| Decisions | A ticket or action became approved before its writes ran | Approved and journalled only after the writes succeed; a retry performs only the missing write |
| Weekly API | `/api/weekly/run` was open to anyone when `WEEKLY_TOKEN` was unset | Disabled without a token; constant-time check |
| Access | Everyone could read the live queue, audit log and written files, and submit questions; no password meant anyone could approve | Live desk reviewer-only, fail closed; public read-only demo on synthetic sample data |
| Hardening | Login limit bypassable with `X-Forwarded-For`; no CSP; signing key could enter the Docker image | Real client address (`PROXY_HOPS`), nonce-based CSP, HSTS on HTTPS, `.dockerignore` |
| Persistence | Refinements and re-drafts not journalled; accepted edits dropped on restart after the stale date | Journalled and replayed; restored stale edits kept but blocked |
| Sources | Scheme-page facts other than expense ratio, minimum SIP and exit load carried a date they were not checked on | Those answers are drafted but blocked from approval (`UNCONFIRMED_SOURCE`) and show "Last checked: not confirmed"; warnings wherever a source is overdue, unconfirmed or due soon; [SOURCE_VERIFICATION.md](SOURCE_VERIFICATION.md) lists what needs a person |
| CI and tooling | `weekly.yml` did not parse; evals crashed on Windows (unclosed SQLite); one eval check could never fail; a failing eval could copy fake test PII into its report | Fixed, each with a test; the vacuous check is kept and a strict one added; every eval detail is redacted before writing |

## MCP and the approval gate
`mcp_layer.py` defines four tools (served over the real protocol by `mcp_server.py`, see below), each with a name, description and input schema: `append_weekly_record`, `create_weekly_email`, `append_support_record`, `create_email_draft`. All writes go through `call_tool(name, args, gate)`, which refuses unless **that action's own** `ApprovalGate` is approved, then checks required arguments, re-scans the payload for PII, writes, and appends an audit line. Gates exist per action (two weekly, one per ticket); a draft the reviewer flagged cannot be approved (403). Full reference with schemas, sequence diagrams, failure modes and how to swap in real Docs/Gmail MCP servers: **[docs/mcp.md](docs/mcp.md)**.

**Real MCP server.** `python mcp_server.py` speaks the Model Context Protocol over stdio (default) or streamable HTTP (`--transport streamable-http`). Each write tool needs a `receipt_id`: a signed, single-use record issued only when a human approved that exact action, bound to the tool and a hash of the exact arguments. Missing, forged, replayed, wrong-tool and edited-after-approval receipts are refused (Eval 6, 10 checks). Receipts expire after 15 minutes and are single-use. Set `MCP_TRANSPORT=stdio` and the web app itself writes through this server as a child process in the same container. **Stdio suits a single container; outside MCP clients need the HTTP transport, which is a separate process that must share the output folder and `APPROVAL_SECRET`** (see [docs/mcp.md](docs/mcp.md#transport-architecture-and-what-a-hosted-deployment-needs)). The hosted demo uses the in-process default. The tool bodies still write local files and an unsent `.eml`; no Google Docs or Gmail connector is attached.

![MCP receipt sequence](docs/img/mcp-receipt-sequence.png)

## Scope enforcement (in code)
| Rule | Enforced by |
|---|---|
| Facts-only; no advice, buy/sell, return or performance figures | Refusal template chosen by `ComplianceAgent`; reviewer hard-fails on advice language, return claims and figures not in the fact; weekly quotes pass `clean_ok`; human edits are re-reviewed |
| One source link per claim, from the M1 corpus | Reviewer: each non-standard sentence needs exactly one allowed link equal to the retrieved fact's; explainer bullets carry [1]/[2] markers |
| Corpus can't answer → say so and name what was searched | `validate_output` rejects a not-covered result without a `searched` list |
| No PII in data, UI, logs or agent state | `pii.redact` is the first line of `Desk.submit` and of weekly ingest; logs hold ids, hashes and codes; payload re-scan in `call_tool` |
| Every theme traces to review ids; every count states its window | Theme rows carry `review_ids` and `window` |
| Nothing written without approving that action | Per-action gates |

Rule-by-rule map and threat model: [docs/compliance-model.md](docs/compliance-model.md).

## Evaluation
`python -m evals.run_evals` runs ten groups of checks over the assembled system (about 30 s, no network except the local MCP subprocess). Results are saved in [`outputs/evals/`](outputs/evals/) and shown on the Evals page. **Last full run: 177/177** on Python 3.14 / Windows 11; unit tests 40 run, 33 pass, and the **7 voice browser tests are skipped** because Playwright is not installed (they have not been run in this environment).

| Eval | Result | What it proves |
|---|---|---|
| **Feasibility** | 14/14 | All 38 queued questions get a draft or explicit "not covered"; the 4 whose cited fact is unconfirmed (Q-014, Q-024, Q-037, Q-038) are flagged `UNCONFIRMED_SOURCE` only and approval is refused (403); weekly loop completes unattended in a separate process; caps held; both connections work |
| **Correctness of edits** | 16/16 | State is diffed before and after: an edit changes only its draft; rejecting leaves the queue untouched; approving one action never triggers another; flagged drafts and pending gates cannot write |
| **Grounding and compliance** | 27/27 | 15 sampled claims trace to a link or review id; 8 unanswerable questions say so; 32 advice/return attempts and 14 PII messages (rephrased, repeated) refused or redacted (the only review failure allowed is `UNCONFIRMED_SOURCE`); a poisoned reviews file leaves the pulse clean; no log, file or eval report holds sensitive or dummy test values |

| **Regressions** (outside review and Claude Code audit, 26 Nov) | 20/20 | Source-verification statuses (unconfirmed scope, overdue after 60 days, no date changed); a strict version of the brokerage-count check; DP charges are per sell order; fabricated and meaning-flipped claims that keep a valid source link are rejected; CSV upload is cleaned and moves the window; poisoned reviews never reach the Pattern Agent index; IFSC and UPI redacted; five expense ratios match the HDFC pages checked 26 Nov; generic "charges" no longer counted as brokerage |
| **Golden dataset** (hand labels in `data/golden.csv`) | 39/39 | status and cited page for all 38 questions, plus a summary row |
| **MCP server** (stdio and streamable HTTP) | 13/13 | discovery, refusals without a valid receipt, tampered or replayed receipt, validation failure, PII, audit, app routed through the server |
| **Persistence** | 5/5 | a restart keeps approvals, live questions and the canonical explainer; replay writes nothing |
| **Approval security** | 12/12 | rejection, duplicate and 12-way concurrent approvals, receipt expiry and 8-way replay race, edit isolation, database diffed before and after |
| **Privacy across pathways** | 10/10 | submit, refine, edit, preview API, CSV upload, Pattern Agent cache and vocabulary, SQLite, logs, browser storage, no audio route |
| **Assignment requirements** | 21/21 | weekly loop, response loop, connection and compliance asserted one by one; anonymous visitors cannot reach the live desk or change anything, and the public demo holds sample data only |

The evals found real bugs, including a persistence assertion that had been written too loosely (a restore run twice created duplicate tickets while the test still passed; the code is now idempotent and the assertion exact). Two earlier ones: (return-figure questions answered "not covered" instead of refused; fee questions counted as brokerage but missing the canonical answer). Both were fixed in code. Methodology and limits: [docs/evaluation.md](docs/evaluation.md).

## The fee issue from the reviews
**Brokerage and trade charges.** In 2026-08-22 to 2026-08-29, **21 of 366** unique substantive review texts (5.7%) mention it, **16 rated 1–2★**, 11 using confusion wording (hidden, extra, unclear, comparisons with other apps). The weekly count is level with the 18 Jul week (21 each) and above the other six bins (range 6–21). **How the 366 arises:** the export has 1,067 review records in the 7-day window, 630 distinct texts, and 366 after dropping texts under four words (so "Best", "Excellent" and repeats are not counted). The fee match uses explicit fee wording (brokerage, per order, hidden or extra charge and similar); an earlier version matched any use of the word "charges" and counted 41, which an outside review showed was too broad. Review ids are on the Weekly page.

## Samples
[`outputs/samples/sample_outputs.md`](outputs/samples/sample_outputs.md): five sample questions with drafts and routing notes (canonical reuse, scheme fact, not covered, advice refused, PAN redacted), the appended weekly doc entry, the weekly email draft, a support record and a reply draft. Reviews: [`data/reviews_sample.csv`](data/reviews_sample.csv) (40 rows) and the full redacted [`data/reviews.csv`](data/reviews.csv).

## Documentation
| Document | Contents |
|---|---|
| [problem-statement.md](docs/problem-statement.md) | The brief and a 28-row requirement → code → evidence table |
| [architecture.md](docs/architecture.md) | Components, sequences, state machine, trust boundaries, trade-offs |
| [mcp.md](docs/mcp.md) | Tool catalogue, schemas, gate protocol, audit log, failure modes, going live |
| [implementation-plan.md](docs/implementation-plan.md) | Stack, phases, decisions that changed |
| [deployment-plan.md](docs/deployment-plan.md) | Render, Docker, CI, scheduling, env vars, checklist |
| [evaluation.md](docs/evaluation.md) | What each eval checks, results, what they found, limits |
| [edge-cases.md](docs/edge-cases.md) | Cases with status: tested, checked or limit |
| [compliance-model.md](docs/compliance-model.md) | Threat model, rule → code map, what is not claimed |
| [data-dictionary.md](docs/data-dictionary.md) | CSV schemas, run and ticket objects |
| [ui-guide.md](docs/ui-guide.md) | Screens, demo script, design notes |
| [milestone-lineage.md](docs/milestone-lineage.md) | What came from Milestones 1–3 and what is new |
| [SOURCES.md](SOURCES.md) | Source manifest: every official URL and its use |
| [EVALS_REPORT.md](EVALS_REPORT.md) | Golden dataset, adversarial tests and scores in one file |

## Repository layout
```
app.py  service.py            Flask routes · both loops, gates, canonical store, snapshot/diff
weekly.py  pipeline.py        weekly loop · clustering, fee issue (from Milestone 2)
desk.py  agents.py            response loop · Facts / Pattern / Compliance (from Milestone 3)
orchestrator.py reviewer.py   reply + routing note · hard-fail review
corpus.py corpus_registry.py  Milestone 1 corpus and retrieval
mcp_layer.py mcp_server.py    four tools behind ApprovalGate · real MCP server with single-use receipts
verification.py               source-verification status (overdue / unconfirmed / due soon)
pii.py                        redaction
weekly_job.py                 headless weekly run (cron / Actions / n8n)
evals/run_evals.py  tests/    ten evaluation groups · unit tests
make_samples.py make_demo.py  sample outputs · public demo snapshot (data/demo_snapshot.json)
make_evals_report.py          EVALS_REPORT.md from the saved run
tools/                        scan_repo, source_status, mcp_demo
data/                         reviews.csv · reviews_sample.csv · questions.csv · golden.csv · source_checks.json · demo_snapshot.json
templates/ static/            UI
docs/                         documentation, diagrams (docs/diagrams/*.mmd), screenshots
outputs/evals  outputs/samples   saved evidence
Dockerfile docker-compose.yml render.yaml Procfile n8n-workflow.json .github/workflows/
```

## Design decisions
- **Three sources, one answer.** Official pages say what is true, reviews say what confuses people, the queue says how often. A fee answer cites the page, is counted in the pulse, and is checked against the review trend (a rising trend puts the ticket on HOLD).
- **Where the model stops being reliable, the system says so.** Nothing factual is generated: replies are templates around one retrieved sentence. When retrieval has nothing it says so and lists what it searched. The optional LLM may only rephrase and is re-reviewed.
- **A gate a compliance team could trust.** One gate per write, exact content shown before the click, no path around `call_tool`, server-side refusal for flagged drafts, re-reviewed edits, audit log.
- **Intent handling.** Each queue row shows a detected intent (factual, fee with canonical reuse, advice refused, not covered) and PII-removed flags. The brief lists no voice feature, so voice is an optional mic button on the question box.

## Known limits
- **The 38 queued questions are written for this demo (no real customer data).** "Asked 8 times" describes that set, not real traffic. The demo clock is pinned to the end of the reviews export (29 Aug 2026) so questions and reviews share one week. After a reviews upload the clock moves to the new data, so the seeded August questions no longer fall in the window.
- **"Same question" means same topic key** (rule-based), not semantic clustering.
- **Sources.** Answers citing a fact outside a page's recorded check (today: benchmark, riskometer, lock-in, fund manager and objective on the HDFC scheme pages) are **blocked from approval** and say "Last checked: not confirmed" until a person checks the page. Overdue, unconfirmed and due-soon sources carry a visible warning and are listed in [SOURCE_VERIFICATION.md](SOURCE_VERIFICATION.md). With no new manual checks, every source is overdue from 26 Jan 2027 and time-sensitive replies are blocked (`STALE_FACT`).
- **Reviews:** 8 weeks only; clusters are unsupervised and noisy, named by a lexicon. The pulse shows the top 3 by volume, so the small, very negative *Customer support & trust* theme (39 reviews, 87% rated 1–2★) is on the Weekly page but not in the pulse's top 3. One quote (R999) is a generic positive review. "366 reviews" means unique substantive texts (1,067 records in the window, 630 distinct, 366 with four or more words).
- **The weekly loop replays the bundled export** unless a newer CSV is uploaded. The scheduled GitHub Action therefore repeats the same window until a newer file is committed or uploaded.
- **The reviewer checks support by words and word order, not by meaning.** A sentence that preserves the fact's phrasing but is wrong for another reason is outside what it can see. Human edits get the same check and a harmless rewording may be refused.
- **Access:** one shared reviewer password; no per-user accounts or per-approver audit. Questions can only be added by a logged-in reviewer (customers do not submit directly).
- **Persistence is not durable on the hosted demo.** The submission runs on Render's **free plan**, which has no disk: the SQLite journal, approvals, edits, live questions and written files can be **lost on any restart, sleep or redeploy**. Durable persistence is not claimed. It needs a persistent disk (Docker volume or a paid Render disk; see render.yaml). The public demo uses synthetic data only; the live reviewer interface stays login-protected.
- **MCP:** a real server and a real protocol, but the tool bodies write local files and an unsent `.eml`; no Google Docs or Gmail connector is attached.
- **The default build is deterministic** (retrieval, rules, templates). The optional Groq path is off unless a key is set and is untested.
- **Advice detection is regex-based** and can be bypassed by unusual phrasing; the reply would still be a cited fact or "not covered".
- **Voice:** the 7 voice browser tests (real browser engine, mocked recogniser) are **skipped**: Playwright is deliberately not installed, so they have not been run in this environment. No live microphone test has been done. Browser speech recognition may send audio to the browser vendor's cloud; this app never receives or stores audio, and shows a consent notice first.
- **A ticket approval authorises two writes** (the support-log record and the reply draft) because they are one decision about one ticket; the weekly doc append and email draft are separate decisions. Both are shown before the click.
- **The HTTP MCP transport has no login of its own;** keep it on localhost or behind an authenticating proxy.
- **Dependencies are not pinned** (`requirements.txt` uses minimum versions). Render installs the newest compatible versions under the explicitly configured `PYTHON_VERSION=3.11.9`; the last full run used Python 3.14 locally, so the exact Render package set has not been tested beforehand and builds are not bit-for-bit reproducible. The Docker image and the n8n workflow were not built or run.
- More in [docs/edge-cases.md](docs/edge-cases.md).

## Deploy
1. Push this folder to a **new** GitHub repo (keeps Milestone 3 as submitted).
2. Render → New → **Blueprint** → select the repo. Only a Blueprint applies `render.yaml` (free plan, `PYTHON_VERSION=3.11.9`, build `pip install -r requirements.txt`, start `gunicorn app:app --workers 1 --threads 4 --timeout 120`, generated `REVIEWER_PASSWORD`, `SECRET_KEY` and `WEEKLY_TOKEN`, `COOKIE_SECURE=1`, `PROXY_HOPS=1`). A plain "Web Service" ignores `render.yaml`. Then set Settings → Health Check Path to `/healthz`.
3. Read the generated `REVIEWER_PASSWORD` in Render → Environment. Open the URL, check `/healthz`, log in as reviewer, click through Overview → Weekly pulse. Put the URL at the top of this README.
4. Optional schedule: the `weekly-loop` GitHub Action runs `weekly_job.py` every Monday 09:00 IST; add secrets `APP_URL` and `WEEKLY_TOKEN` (same value as the Render variable) to also trigger the hosted app. `n8n-workflow.json` is an optional alternative.

Details and checklist: [docs/deployment-plan.md](docs/deployment-plan.md).

---
MIT licence · Built for the NextLeap Applied Generative AI Bootcamp, Cohort 7.
