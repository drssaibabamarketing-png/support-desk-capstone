# Evaluation

Run: `python -m evals.run_evals` (about 10 seconds, no network). Results are written to `outputs/evals/{feasibility,edit_correctness,grounding_compliance}.md` and `summary.json`, and shown on the app's **Evals** page. The run uses isolated output and log folders (`outputs/evals/runtime/`) so the "nothing reached the logs" check scans exactly what the run produced. Dummy PII values (PAN, phone, account, Aadhaar, OTP) are assembled from fragments at run time so the repository never contains them.

| Eval | Checks | Result |
|---|---|---|
| 1 Feasibility | 13 | 13/13 |
| 2 Correctness of edits | 16 | 16/16 |
| 3 Grounding and compliance | 26 | 26/26 |

## Eval 1: Feasibility
*Does the assembled system always produce something usable, within its caps, without a human nudging it?*

| What is checked | How |
|---|---|
| Every one of the 38 queued questions produces a draft (cited, refusal, or explicit "not covered"), ≤3 sentences, not flagged | Seed the queue; inspect each ticket's facts status, compliance flag, sentence count, reviewer flag |
| Every "not covered" names what it searched | `facts.searched` non-empty |
| Weekly loop completes unattended once triggered | `weekly_job.py` in a **separate process**, exit code 0 |
| That run writes nothing but its result file | Directory listing of its output folder |
| Every theme carries review ids and a window; ≤5 themes; top 3 | Inspect the run |
| Pulse ≤250 words; explainer ≤6 bullets, 2 official links, last-checked date | Counted |
| All nine weekly output checks pass | `run["checks"]` |
| **Link 1:** a question asked ≥5× appears in the pulse | Topic group count and presence of its label in the pulse text |
| Before approval the fee answer comes from the corpus | `facts.canonical` absent |
| **Link 2:** after approval the next fee question reuses the explainer | `facts.canonical` present; answer equals an approved bullet; its URL equals that bullet's URL; reviewer passed; routing note says REUSED; the bullet mentions the fee the question names |
| An older pending ticket picks up the canonical when a human re-drafts it | Re-draft and inspect |

## Eval 2: Correctness of edits
*Does each action change exactly what it should and nothing else?* Each step takes `Service.snapshot()` (every ticket's reply, note, status, edited flag, canonical flag and writes; every action's status; canonical versions; a hash of every output file) before and after, and asserts the **diff** equals the expected set of changed fields.

| Step | Expected diff |
|---|---|
| Human edits ticket A | only A's `reply` and `edited` |
| Edit that adds advice | nothing (reviewer refuses) |
| Edit that contains a PAN | nothing (refused) |
| Reject ticket B | only B's `status`; no file |
| Approve rejected B | nothing |
| Approve ticket A | only A's `status`/`writes` and the four support files + audit; no weekly files, no other ticket, no action, no canonical |
| Support log holds exactly one entry (A) | count |
| Approve weekly doc action | only that action, canonical registered, `weekly_log.*` + audit; **email action untouched, no email file** |
| Approve weekly email action | only that action and the email draft files |
| Re-draft one ticket | only that ticket's canonical flag, note and reply |
| Reject a weekly action | only that action; no file; the other action still pending |
| Reviewer-flagged draft | approve returns 403; no file written |
| Tool called with a pending gate | `ApprovalRequired` |

## Eval 3: Grounding and compliance
*Is every claim traceable, and do attacks fail in both loops?*

1. **Fifteen sampled claims** (fixed seed): 5 reply claims, 3 explainer bullets, 3 pulse quotes, 2 theme counts, 1 fee observation, 1 support signal. Each is verified mechanically: reply text and URL match a corpus chunk or approved bullet and the URL is in the M1 list; bullets map to one of the two links; quote ids exist in the window with identical text and rating; theme counts equal the number of distinct in-window review ids; the fee count is recomputed from the CSV; the signal is recounted from the queue.
2. **Eight questions the corpus cannot answer** (crypto, US stocks, CEO, weather, credit card, change mobile number, app crash…): all `not_covered`, name what was searched, cite nothing.
3. **Response-loop attacks:** 16 advice/return requests, each run twice (32): all refused; refusal holds under three pushbacks inside one ticket; 7 PII messages ×2 (PAN, account, phone, Aadhaar, OTP, mixed, Hinglish): all redacted, and the full ticket state is searched for the dummy values.
4. **Weekly-loop attacks:** a copy of the reviews with 21 injected reviews (PAN, phone, account, Aadhaar, OTP; advice; return figures; repeated and rephrased): PII redacted at ingest (6 of 6 expected; identical repeats collapse in de-duplication), none of it in the pulse, explainer or email body, no advice or return figure, none of the injected reviews used as a quote, caps still met.
5. **Logs and files:** every file produced by all three eval runs is scanned for the dummy values and for PII patterns; the repository files are scanned too.

## What the evals found (and what was done)
| Finding | Fix |
|---|---|
| "What is the 5 year return of …?" returned "not covered" rather than a refusal | New return-request patterns in `ComplianceAgent` |
| A fee question phrased "charged twice" was counted as brokerage but missed the canonical lookup | Topic detection now uses corpus intents for counting and reuse |
| README contained a dummy PAN (caught by the repository scan) | README rewritten; values are now built at run time |

## Limits of these evaluations
- They are small, hand-written and deterministic: they prove the mechanisms, not general robustness. Unusual advice phrasings can bypass regex detection.
- The 38 questions are synthetic; frequency findings describe that set.
- Retrieval quality is checked by claim tracing and unanswerable questions, not by a labelled relevance set.
- LLM paths are not exercised.


## Eval 4: Regressions (added 26 Nov 2026)
After an independent review found a wrong DP-charge fact, raw review text in the Pattern Agent cache, and a reviewer that accepted a fabricated claim carrying a valid link, ten checks were added (10/10): DP per sell order; fabricated and absolute-wording edits rejected with state unchanged; poisoned CSV never reaches the Pattern Agent index; IFSC/UPI redaction; five expense ratios match the HDFC pages checked on 26 Nov; check dates recorded; generic "charges" not counted as brokerage. Known limit: the support check is word-level, so a sentence that flips meaning using the fact's own words can still pass.


## Evals 5–7 (added 26 Nov 2026)
- **Eval 5, golden dataset (39 checks).** `data/golden.csv` holds hand-written expected labels for all 38 questions (answered / refused / not covered, and a source substring). The eval compares the system's status and cited page with them. The labels were written by the same author as the system, before the final run, so a reviewer should skim them; a Hinglish brokerage question is included as a stretch case.
- **Eval 6, MCP server (10 checks):** see [mcp.md](mcp.md).
- **Eval 7, persistence (5 checks):** a live question, an approved weekly action with its canonical explainer, and an approved ticket survive a restart; the other weekly action stays pending; replay writes no files.
- Eval 4 also covers CSV upload (PII removed before saving, window follows the new data, bad file refused) and the meaning-flip edit ("per stock, not per sell order") rejected by the word-order check.
Total at the time this section was written: 123 checks. Current totals (177 at the last full run, ten groups) are in [EVALS_REPORT.md](../EVALS_REPORT.md) and `outputs/evals/summary.json`, which are generated from the run.
