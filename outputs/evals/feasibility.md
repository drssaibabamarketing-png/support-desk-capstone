# Eval 1: Feasibility

Result: **13/13 checks pass**

| Check | Result | Detail |
|---|---|---|
| every one of the 38 queued questions produces a draft (cited, refusal, or explicit 'not covered'), 3 sentences or fewer, not flagged | PASS | 38/38 ok; covered 28, refused advice/returns 4, not covered 6; failures: none |
| every 'not covered' result names what was searched | PASS | 10 not-covered results |
| weekly loop completes with no manual intervention once triggered (separate process, exit code 0) | PASS | exit 0; 1.0s; 366 reviews; signals ['Groww brokerage and charges x8', 'HDFC scheme exit load x5'] |
| the unattended run wrote nothing but its result file (writes stay pending at the gate) | PASS | files: ['weekly_job_result.json'] |
| every theme carries review ids and a stated window | PASS | 5 themes, window 2026-08-22 to 2026-08-29, ids per theme: [191, 55, 44, 39, 37] |
| at most 5 themes and 3 top themes | PASS | 5 themes |
| pulse inside its word cap (250) | PASS | 198 words |
| explainer inside its bullet cap (6), 2 official links, last-checked date | PASS | 6 bullets; ['https://groww.in/pricing', 'https://groww.in/help/brokerage-and-taxes/charges-for-delivery/what-are-the-different-charges-mentioned-in-the-report']; checked 26 Nov 2026 |
| all weekly output checks pass | PASS | 9/9 |
| LINK 1: a question seen >= 5 times in the window appears in the pulse | PASS | 'Groww brokerage and charges' x8 -> in pulse: True |
| before approval the fee answer is drafted from the corpus (no canonical explainer yet) | PASS | canonical: none |
| LINK 2: after the explainer is approved, the response loop reuses it instead of drafting fresh | PASS | canonical v1 bullet 1 (mentions brokerage, as the question does); answer == approved bullet: True; reviewer passed: True |
| an older pending brokerage ticket picks up the canonical answer when a human re-drafts it | PASS | Q-004 re-drafted |
