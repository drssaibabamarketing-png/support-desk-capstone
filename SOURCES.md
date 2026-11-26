# Source Manifest

Every official URL used by this project, split by **how it is used**, so a reviewer can see exactly which pages back an answer. Dates are the last time the page was opened and compared by hand (`data/source_checks.json`); the UI shows them next to every reply and explainer.

| Group | URLs | Meaning |
|---|---|---|
| A. Retrieval sources (can be cited in a reply) | 20 | `corpus.ALLOWED_URLS`: the only links the reviewer accepts |
| B. Of which, actually carrying corpus facts today | 16 | URLs that at least one retrieval chunk cites |
| C. Supporting references (listed in the registry, never cited) | 16 | variants and alternate addresses of pages in A |
| D. Review collection source | 1 | Play Store listing; **not** an official investment document |

Official URLs in A + C: **36**.

## A. Retrieval sources
| # | URL | Chunks citing it | Last checked |
|---|---|---|---|
| 1 | https://groww.in/help | 0 | 22 Oct 2026 |
| 2 | https://groww.in/help/brokerage-and-taxes/charges-for-delivery/what-are-the-different-charges-mentioned-in-the-report | 0 | 26 Nov 2026 |
| 3 | https://groww.in/help/stocks/searchable/are-dp-charges-per-stock-or-per-order | 0 | 26 Nov 2026 |
| 4 | https://groww.in/pricing | 18 | 26 Nov 2026 |
| 5 | https://investor.sebi.gov.in/ | 2 | 22 Oct 2026 |
| 6 | https://www.amfiindia.com/ | 4 | 22 Oct 2026 |
| 7 | https://www.amfiindia.com/investor-corner | 6 | 22 Oct 2026 |
| 8 | https://www.hdfcfund.com/about-us/corporate-governance | 1 | 22 Oct 2026 |
| 9 | https://www.hdfcfund.com/investor-services/download-statements/account-statement | 1 | 22 Oct 2026 |
| 10 | https://www.hdfcfund.com/investor-services/download-statements/capital-gains-statement | 1 | 22 Oct 2026 |
| 11 | https://www.hdfcfund.com/investor-services/downloads/forms | 1 | 22 Oct 2026 |
| 12 | https://www.hdfcfund.com/investor-services/kyc | 2 | 22 Oct 2026 |
| 13 | https://www.hdfcfund.com/product-solutions/overview/hdfc-elss-tax-saver/direct | 8 | 26 Nov 2026 |
| 14 | https://www.hdfcfund.com/product-solutions/overview/hdfc-gold-fund/direct | 7 | 26 Nov 2026 |
| 15 | https://www.hdfcfund.com/product-solutions/overview/hdfc-large-cap-fund/direct | 7 | 26 Nov 2026 |
| 16 | https://www.hdfcfund.com/product-solutions/overview/hdfc-mid-cap-opportunities-fund/direct | 7 | 26 Nov 2026 |
| 17 | https://www.hdfcfund.com/product-solutions/overview/hdfc-small-cap-fund/direct | 7 | 26 Nov 2026 |
| 18 | https://www.hdfcfund.com/statutory-disclosure/nav-and-idcw | 0 | 22 Oct 2026 |
| 19 | https://www.sebi.gov.in/legal/master-circulars/may-2023/master-circular-for-mutual-funds_71438.html | 1 | 22 Oct 2026 |
| 20 | https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doFaq=yes | 1 | 22 Oct 2026 |

## C. Supporting references (not cited)
| # | URL |
|---|---|
| 1 | https://www.hdfcfund.com/about-us/corporate-governance/codes-policies |
| 2 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-elss-tax-saver-fund |
| 3 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-elss-tax-saver-fund/regular |
| 4 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-gold-etf-fund-fund |
| 5 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-gold-etf-fund-fund/regular |
| 6 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-large-cap-fund |
| 7 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-large-cap-fund/regular |
| 8 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-mid-cap-opportunities-fund |
| 9 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-mid-cap-opportunities-fund/regular |
| 10 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-small-cap-fund |
| 11 | https://www.hdfcfund.com/explore/mutual-funds/hdfc-small-cap-fund/regular |
| 12 | https://www.hdfcfund.com/nav-and-idcw |
| 13 | https://www.hdfcfund.com/services/additional-info/request-statement |
| 14 | https://www.hdfcfund.com/services/consolidated-account-statement |
| 15 | https://www.hdfcfund.com/services/forms |
| 16 | https://www.hdfcfund.com/services/kyc-redressal-complaints |

## D. Review collection source
- https://play.google.com/store/apps/details?id=com.nextbillion.groww  (public Play Store reviews exported to `data/reviews.csv`; personal data removed at preparation and again at ingest)

## Verification status and manual checks
The app computes a status for every source and every cited fact (`verification.py`) and shows a warning wherever one is **overdue** (last check older than the 60-day re-check interval), **unconfirmed** (no check recorded, or the page was checked only for other fields) or **due soon** (within 14 days of the interval): on the ticket, the queue, the weekly and canonical explainers, the Sources page, the public demo, and as a banner for reviewers. The list of URLs that need a person is in [SOURCE_VERIFICATION.md](SOURCE_VERIFICATION.md) (regenerate with `python tools/source_status.py --write`; it exits 1 while any source is overdue or unconfirmed). Dates change only when someone has opened the page; the app never writes them.

**Recorded check scope.** `data/source_checks.json` now records, under `field_scope`, that the five HDFC scheme pages were compared on 26 Nov 2026 only for expense ratio, minimum SIP and exit load (as the note below always said). Their benchmark, riskometer, fund manager, objective and lock-in facts are therefore shown as **unconfirmed** until checked. Note: the customer-facing reply footer for those facts still prints the page's date (`Last checked: 26 Nov 2026`).

**Citation fix.** The DP-charges explainer's source [2], which backs "per sell order, not per stock", is now the Help Centre FAQ that was checked for exactly that claim, instead of the Help Centre home page.

## Verification notes
- Checked on **26 Nov 2026**: the five HDFC scheme pages (expense ratio, minimum SIP, exit load; the pages now live under `/product-solutions/overview/`), `groww.in/pricing`, and two Groww Help Centre pages (DP charges per order; charges mentioned in the report).
- The HDFC pages show **no as-of date** for the expense ratio, so a stored value is current only on its check date.
- Not re-opened this release (older dates shown): `groww.in/help` (home), the SEBI and AMFI pages, and the HDFC service pages (statements, KYC, forms).
- The mapping of each fee-explainer bullet to its source was assigned by hand and checked against the pages above; the weekly explainer cites only [1] the pricing page or [2] the specific Help Centre page.
