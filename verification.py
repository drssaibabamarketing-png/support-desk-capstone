"""Source-verification status: is each official source (and each cited fact) confirmed recently enough?

Statuses (worst first):
  overdue      last recorded check is older than the re-check interval (config.TIME_SENSITIVE_MAX_DAYS, 60 days, unchanged)
  unconfirmed  no check is recorded for this URL, or the page was checked only for other fields (field_scope)
  due_soon     the interval runs out within DUE_SOON_DAYS
  ok           checked within the interval, and (if scoped) this fact's field was among those checked

This module only REPORTS. It never edits data/source_checks.json and never invents a date: a date changes only when a
person opens the page and records it there. Replies are still blocked only by the reviewer's existing STALE_FACT rule
(time-sensitive figures); everything else gets a visible warning.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import config

DUE_SOON_DAYS = 14
RANK = {"overdue": 0, "unconfirmed": 1, "due_soon": 2, "ok": 3}
LABEL = {"overdue": "verification overdue", "unconfirmed": "verification unconfirmed", "due_soon": "re-check due soon", "ok": "verified"}
FIELD_LABEL = {"expense_ratio": "expense ratio", "min_sip": "minimum SIP", "exit_load": "exit load", "benchmark": "benchmark",
               "riskometer": "riskometer", "fund_manager": "fund manager", "objective": "investment objective", "lock_in": "lock-in"}


def _checks() -> dict:
    try:
        return json.loads(config.SOURCE_CHECKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _parse(d: str | None) -> date | None:
    try:
        return datetime.strptime(d, "%d %b %Y").date() if d else None
    except ValueError:
        return None


def source_status(url: str, today: date | None = None) -> dict:
    """Status of one official URL as a whole."""
    today = today or config.today()
    data = _checks()
    recorded = (data.get("sources") or {}).get(url)
    checked = _parse(recorded)
    limit = config.TIME_SENSITIVE_MAX_DAYS
    scope = {k: v for k, v in (data.get("field_scope") or {}).items() if k != "_note"}.get(url)
    out = {"url": url, "last_checked": recorded, "age_days": (today - checked).days if checked else None,
           "due_by": (checked + timedelta(days=limit)).strftime("%d %b %Y") if checked else None,
           "partial_fields": [FIELD_LABEL.get(f, f) for f in scope["checked_fields"]] if scope else None}
    if not checked:
        out.update(status="unconfirmed", reason="no check of this page is recorded in data/source_checks.json")
    elif out["age_days"] > limit:
        out.update(status="overdue", reason=f"last checked {recorded}, {out['age_days']} days ago (re-check interval {limit} days)")
    elif scope:
        out.update(status="unconfirmed", reason=f"checked {recorded} only for {', '.join(out['partial_fields'])}; other facts on this page are not re-confirmed")
    elif out["age_days"] > limit - DUE_SOON_DAYS:
        out.update(status="due_soon", reason=f"last checked {recorded}; re-check due by {out['due_by']}")
    else:
        out.update(status="ok", reason=f"checked {recorded}")
    out["label"] = LABEL[out["status"]]
    return out


def fact_status(url: str | None, fact_intents: list[str] | None = None, today: date | None = None) -> dict | None:
    """Status of one cited fact: the page's status, narrowed by the page's check scope. None if nothing is cited."""
    if not url:
        return None
    s = source_status(url, today)
    if s["partial_fields"] is not None and s["status"] != "overdue":
        data = _checks()
        checked = set(data["field_scope"][url]["checked_fields"])
        intents = set(fact_intents or [])
        if intents & checked:                              # this fact IS one of the fields compared on the check date
            age = s["age_days"]
            st = "due_soon" if age > config.TIME_SENSITIVE_MAX_DAYS - DUE_SOON_DAYS else "ok"
            s = {**s, "status": st, "label": LABEL[st], "reason": f"checked {s['last_checked']} for this field"
                 + (f"; re-check due by {s['due_by']}" if st == "due_soon" else "")}
        else:
            what = ", ".join(FIELD_LABEL.get(i, i) for i in sorted(intents)) or "this statement"
            s = {**s, "status": "unconfirmed", "label": LABEL["unconfirmed"],
                 "reason": f"the page was checked {s['last_checked']} only for {', '.join(s['partial_fields'])}; {what} was not re-confirmed"}
    return s


def manual_list(urls, today: date | None = None) -> list[dict]:
    """Every URL that needs a person to open it, worst first."""
    rows = [source_status(u, today) for u in sorted(set(urls))]
    return sorted([r for r in rows if r["status"] != "ok"], key=lambda r: (RANK[r["status"]], r["url"]))


def summary(urls, today: date | None = None) -> dict:
    rows = [source_status(u, today) for u in set(urls)]
    return {k: sum(1 for r in rows if r["status"] == k) for k in RANK}
