# Source verification: manual checks needed

Generated 26 Nov 2026 by `python tools/source_status.py --write` from `data/source_checks.json`. This is a snapshot: statuses change with the date, so regenerate it before relying on it. The app shows the live status.

Re-check interval: 60 days (`TIME_SENSITIVE_MAX_DAYS`); "due soon" = within 14 days of it.

**20 citable sources: 15 verified, 0 due soon, 5 unconfirmed, 0 overdue.**

## How to clear an item

1. Open the URL and compare every fact the corpus serves from it (`corpus_registry.py`, `pipeline.FEE_KB`).
2. Fix any fact that changed, in code, with a regression test.
3. Only then record the date you checked in `data/source_checks.json` (`sources`), and for a scheme page list the fields you compared in `field_scope` (or remove the scope once every field is checked).
4. Never enter a date for a page you did not open.

## Sources needing a person

| Status | Source | Last checked | Why |
|---|---|---|---|
| verification unconfirmed | https://www.hdfcfund.com/product-solutions/overview/hdfc-elss-tax-saver/direct | 26 Nov 2026 | checked 26 Nov 2026 only for expense ratio, minimum SIP, exit load; other facts on this page are not re-confirmed |
| verification unconfirmed | https://www.hdfcfund.com/product-solutions/overview/hdfc-gold-fund/direct | 26 Nov 2026 | checked 26 Nov 2026 only for expense ratio, minimum SIP, exit load; other facts on this page are not re-confirmed |
| verification unconfirmed | https://www.hdfcfund.com/product-solutions/overview/hdfc-large-cap-fund/direct | 26 Nov 2026 | checked 26 Nov 2026 only for expense ratio, minimum SIP, exit load; other facts on this page are not re-confirmed |
| verification unconfirmed | https://www.hdfcfund.com/product-solutions/overview/hdfc-mid-cap-opportunities-fund/direct | 26 Nov 2026 | checked 26 Nov 2026 only for expense ratio, minimum SIP, exit load; other facts on this page are not re-confirmed |
| verification unconfirmed | https://www.hdfcfund.com/product-solutions/overview/hdfc-small-cap-fund/direct | 26 Nov 2026 | checked 26 Nov 2026 only for expense ratio, minimum SIP, exit load; other facts on this page are not re-confirmed |
