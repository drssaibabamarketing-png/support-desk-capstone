# Eval 4: Regressions found by an outside review (26 Nov)

Result: **20/20 checks pass**

| Check | Result | Detail |
|---|---|---|
| DP-charge fact says per sell order and never per stock per day | PASS | Selling delivery shares also attracts depository (DP) charges, applied per sell order, not per stock. |
| the fee knowledge base no longer contains the old per-stock wording | PASS |  |
| fabricated claim with a valid source link is rejected by the reviewer | PASS | The reviewer rejected the edit: UNSUPPORTED_CLAIM. Nothing was changed. |
| rejected fabricated edit changed nothing | PASS |  |
| second fabricated claim (absolute wording) is also rejected | PASS | The reviewer rejected the edit: UNSUPPORTED_CLAIM; RETURN_CLAIM. Nothing was changed. |
| meaning-flip using the fact's own words (per stock, not per sell order) is rejected | PASS | The reviewer rejected the edit: UNSUPPORTED_CLAIM. Nothing was changed. |
| Pattern Agent index built from a poisoned CSV holds no raw PII (cached text scanned) | PASS | scanner hits: [] |
| IFSC and UPI-style identifiers are redacted | PASS |  |
| five expense ratios match the HDFC pages as checked on 26 Nov 2026 | PASS | 0.73 / 0.79 / 0.20 / 0.99 / 1.18 |
| scheme pages and the DP FAQ carry the 26 Nov 2026 check date | PASS |  |
| uploading a newer reviews CSV works and the saved copy holds no raw PII | PASS | {'ok': True, 'rows': 8629, 'newest': '2026-09-28'} |
| the weekly window moves to the newest 7 days of the uploaded file | PASS | 2026-09-21 to 2026-09-28 |
| a file without review, rating and date columns is refused | PASS |  |
| a fresh expense-ratio answer (checked 26 Nov 2026) is served and passes review | PASS | For the HDFC Large Cap Fund, expense ratio is 0.99% ([source](https:// |
| the same answer 3+ months after the last check is blocked as STALE_FACT and cannot be approved | PASS | ['STALE_FACT'] |
| non-time-sensitive answers (brokerage explanation) are not blocked by the staleness rule | PASS |  |
| a generic 'charges' complaint is not counted as brokerage | PASS | {'fee': 'Brokerage & trade charges', 'mentions': 1, 'negative_mentions': 1, 'pct_of_reviews': 50.0} |
| strict: of the two complaints only the explicit brokerage one is counted (mentions == 1, review id b) | PASS | {'fee': 'Brokerage & trade charges', 'mentions': 1, 'review_ids': ['b']} |
| a fact outside a page's recorded check scope (benchmark) is 'unconfirmed'; a checked field (minimum SIP) is verified | PASS |  |
| after the 60-day interval every citable source is listed for manual verification as overdue, and no date was changed | PASS | 20 of 20 |
