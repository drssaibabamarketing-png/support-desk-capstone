# Data dictionary

## `data/reviews.csv` (8,629 rows)
Public Google Play reviews for Groww, 5 Jul 2026 12:45 to 29 Aug 2026 12:27, prepared by `scripts_prepare.py` (title and text joined, PII-redacted; 0 redactions were needed).

| Column | Type | Notes |
|---|---|---|
| `rid` | string | `R` + 1-based data-row number in the raw export. Stable id used by every theme, quote and count |
| `review_text` | string | Review text after redaction |
| `rating` | int 1–5 | Play Store stars |
| `date` | ISO timestamp | Review time; the weekly window is the newest 7 days of this column |

`data/reviews_sample.csv` is a 40-row excerpt of the same file.

## `data/questions.csv` (38 rows; synthetic)
| Column | Notes |
|---|---|
| `q_id` | `Q-001…Q-038` |
| `received_at` | ISO timestamp inside the weekly window (22–29 Aug 2026) |
| `text` | Demo question; contains no personal data. Written for the demo, **not real customer data** |

## `data/source_checks.json`
`{"default": "22 Oct 2026", "sources": {"<url>": "<dd Mon yyyy>"}}`. Drives every "Last checked" line (reply footers, explainer, Sources page). Edit after re-opening a source.

## Weekly run object (`Service.run_weekly()`)
| Field | Meaning |
|---|---|
| `run_id` | `W-` + hash of window and pulse |
| `window`, `window_exact`, `days` | Dates covered and the exact timestamps |
| `n_reviews`, `rows_in_export`, `pii_redacted_at_ingest` | Counts |
| `themes[]` | `label`, `count`, `share_pct`, `avg_rating`, `negative_pct`, `review_ids[]`, `window`, `is_top3` |
| `quotes[]` | `rid`, `quote`, `rating`, `theme` |
| `fee` | `fee`, `mentions`, `negative_mentions`, `pct_of_reviews`, `confusion_mentions`, `evidence[]`, `review_ids[]`, `all_candidates[]` |
| `fee_trend[]` | `week_end`, `reviews`, `mentions`, `negative` per 7-day bin |
| `signals[]` | Topics asked ≥5× in the window: `key`, `label`, `count`, `q_ids[]`, `reused` |
| `question_groups[]` | All topic groups in the window |
| `pulse`, `pulse_words` | Text and word count |
| `explainer` | `fee`, `bullets[{text, source_n, source_url}]`, `sources[{n, name, url, last_checked}]`, `last_checked` |
| `checks[]` | `(name, ok, detail)` ×9 |
| `action_ids[]` | The two pending actions |

## Ticket (`Desk.tickets[tid]`)
`message` (redacted), `pii_removed[{type,count}]`, `outputs{facts, pattern, compliance}`, `draft{reply{sentences, body, footer, full_text, citation_url, last_checked}, routing{team, priority, hold, note}}`, `review{passed, failures[]}`, `review_attempts[]`, `flagged`, `send_blocked`, `refinements_used`, `fired_log[]`, `timing`, `counters`. No raw text is kept.

## Queue metadata (`Service.meta[tid]`)
`q_id`, `received_at`, `key` (topic key), `label`, `status` (`pending|approved|rejected`), `edited`, `edit_count`, `writes[]`, `gate`.

## Topic keys
`fee:<Brokerage & trade charges | DP / depository charges on selling | Auto square-off / closing charges | Mutual fund exit load / expense ratio>`, `faq:<intent>`, `advice`, `other:<review theme>`.

## Canonical record (`Service.canonical[fee]`)
`fee`, `bullets[]`, `sources[]`, `last_checked`, `version`, `approved_at`, `action_id`, `run_id`.

## Written files (`outputs/`, git-ignored at runtime)
`weekly_log.md/.jsonl`, `weekly_pulse_draft.eml/.txt`, `support_log.md/.jsonl`, `support_reply_draft.eml/.txt`, `audit_log.jsonl`. Desk logs in `logs/desk_log.jsonl` hold only event name, ids, hashes, agent names, codes and counts.


## Added 26 Nov 2026
- `data/golden.csv`: `q_id, expected_status (answered | refused | not_covered), expected_source_contains, why`. Hand-written labels for the 38 questions.
- `logs/state.db` (SQLite, table `events(id, ts, kind, body)`): kinds `submit` (redacted text), `edit`, `ticket`, `action`, `reviews`. No raw personal data.
- `logs/uploaded_reviews.csv`: the redacted copy of an uploaded reviews file (columns rid, review_text, rating, date).
- `outputs/receipts/<id>.json` / `.used`: signed approval receipts for the MCP server.
