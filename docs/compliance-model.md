# Compliance model: rules, where they are enforced, and what is not claimed

## Threat model
A compliance team worries about five things; each has a control in code.

| Risk | Control | Test |
|---|---|---|
| Personal data stored or logged | Redaction at the first statement of `Desk.submit`; weekly ingest redaction; logs carry ids/hashes/codes; `call_tool` PII re-scan | Eval 3 (14 messages, poisoned CSV, scan of all logs and files) |
| Investment advice or buy/sell wording | Request detection → refusal template; draft scan for advice language; reviewer hard fail; quotes filtered | Eval 3 (32 attempts; pushback; poisoned reviews) |
| Return or performance figures | Return-request detection; draft scan for return claims; any figure must appear in the retrieved fact | Eval 3, M3 evidence |
| Unsourced claims | Exactly one allowed link per non-standard sentence, equal to the retrieved fact's | Eval 3 (15 claims) |
| A write nobody approved | Per-action `ApprovalGate`; `call_tool` refuses otherwise; flagged drafts can't be approved | Eval 2 |

## Rule → enforcement map
| Rule in the brief | Where in code |
|---|---|
| Facts-only | `orchestrator` templates; `reviewer.review`; `ComplianceAgent.scan_draft` |
| No recommendations / buy / sell | `ADVICE_REQUEST`, `ADVICE_DRAFT` patterns in `agents.py` |
| No return or performance figures | `RETURN_CLAIM`; `UNGROUNDED_FIGURE` check |
| No PII anywhere | `pii.PATTERNS` (OTP, email, PAN, account/folio, Aadhaar, phone, long digit run) |
| One source link per claim | `reviewer.review` step 2; `corpus.ALLOWED_URLS` |
| Public sources only | `SOURCES.md`; allow-list; no scraping at run time |
| "Not covered" names what was searched | `agents.validate_output` |
| Theme → review ids; counts state window | `weekly.build` theme rows; `weekly` checks |
| Nothing written without that action's approval | `mcp_layer.call_tool` |
| Caps (3 sentences, 250 words, 6 bullets) | reviewer; `weekly._pulse`; `build_explainer` |

## Why the lines are where they are
- **Generate nothing factual.** The strongest safeguard against a hallucinated claim is not asking a model to write one. Replies are templates around a single retrieved sentence.
- **Refuse by detection, not by prompt.** Advice is detected on the way in (so the refusal template is chosen) and on the way out (so a draft that slipped through is blocked). Neither depends on a model behaving.
- **Redact first, store nothing else.** The raw text exists only inside the first function call. Everything after sees the redacted form.
- **Gate every write separately.** A compliance reviewer can read the exact content of one action and approve or reject it without approving anything else.
- **Say so out loud.** "Not covered", the HOLD note, the flagged-draft banner and the last-checked dates all state where the system's knowledge ends.

## What is not claimed
- Detection is rule-based; a novel phrasing can pass. The reply would still contain only a cited fact or a "not covered" message.
- Redaction patterns target Indian identifiers and common formats, not every possible form of personal data. Free-text names and addresses are not detected.
- Source facts are only as fresh as their last-checked date.
- This is a coursework prototype, not a reviewed compliance product.


## Access control and request safety (added 26 Nov 2026)
- **Reviewer login (fail closed).** The live desk (overview numbers, queue, tickets, weekly pulse and its actions, approvals, audit log, canonical explainers, sources-by-ticket, written files, the intent-preview API) and every state-changing request, including adding a question, need a logged-in reviewer. Anonymous visitors see only `/demo` (a committed snapshot of synthetic sample data built by `make_demo.py`; refused if it contains anything PII-like), `/evals`, `/login` and `/healthz` (no operational numbers). Login uses a constant-time compare, an 8-hour session cookie (HttpOnly, SameSite=Lax, Secure on HTTPS) and a 5-attempts-a-minute limit per address. With no password nobody is a reviewer: the live desk is closed and a banner says so (there is no open mode in which anyone can approve). The login redirect only follows same-site paths. The login limit keys on the real client address (`PROXY_HOPS` for proxies), not a client-supplied `X-Forwarded-For`. Every page sends a Content-Security-Policy that lets only same-origin scripts and per-request nonce-tagged inline blocks run (no inline handlers, no third-party scripts, no framing); HSTS on HTTPS. The Docker build context excludes the receipt signing key, receipts, runtime writes and databases.
- **CSRF.** Every POST needs a token the server adds to each form (header `X-CSRF-Token` for fetch calls). The token-protected `/api/weekly/run` uses `X-Token` instead.
- **Headers:** `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`.
- **Uploads:** 5 MB cap; text is redacted before the file is saved.
- **Not claimed:** no per-user accounts, no audit of who approved (one shared password).
