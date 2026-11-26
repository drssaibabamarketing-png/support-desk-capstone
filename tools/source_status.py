"""Lists the official sources that need a person to open them (overdue, unconfirmed, or due soon), from
data/source_checks.json. It never changes a date.

  python tools/source_status.py            print the list; exit 1 if any source is overdue or unconfirmed
  python tools/source_status.py --write    also write SOURCE_VERIFICATION.md (dated, so it is a snapshot)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
import corpus  # noqa: E402
import verification as v  # noqa: E402


def main() -> int:
    today = config.today()
    rows = v.manual_list(corpus.ALLOWED_URLS, today)
    s = v.summary(corpus.ALLOWED_URLS, today)
    lines = ["# Source verification: manual checks needed", "",
             f"Generated {today.strftime('%d %b %Y')} by `python tools/source_status.py --write` from `data/source_checks.json`. "
             f"This is a snapshot: statuses change with the date, so regenerate it before relying on it. The app shows the live status.", "",
             f"Re-check interval: {config.TIME_SENSITIVE_MAX_DAYS} days (`TIME_SENSITIVE_MAX_DAYS`); \"due soon\" = within {v.DUE_SOON_DAYS} days of it.", "",
             f"**{len(corpus.ALLOWED_URLS)} citable sources: {s['ok']} verified, {s['due_soon']} due soon, {s['unconfirmed']} unconfirmed, {s['overdue']} overdue.**", "",
             "## How to clear an item", "",
             "1. Open the URL and compare every fact the corpus serves from it (`corpus_registry.py`, `pipeline.FEE_KB`).",
             "2. Fix any fact that changed, in code, with a regression test.",
             "3. Only then record the date you checked in `data/source_checks.json` (`sources`), and for a scheme page list the fields you compared in `field_scope` (or remove the scope once every field is checked).",
             "4. Never enter a date for a page you did not open.", "",
             "## Sources needing a person", "", "| Status | Source | Last checked | Why |", "|---|---|---|---|"]
    lines += [f"| {r['label']} | {r['url']} | {r['last_checked'] or 'never'} | {r['reason']} |" for r in rows] or ["| - | none | - | - |"]
    text = "\n".join(lines) + "\n"
    print(text)
    if "--write" in sys.argv:
        with open(ROOT / "SOURCE_VERIFICATION.md", "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return 1 if (s["overdue"] or s["unconfirmed"]) else 0


if __name__ == "__main__":
    sys.exit(main())
