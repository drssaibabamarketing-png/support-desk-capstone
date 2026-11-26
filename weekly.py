"""The weekly loop: reviews CSV -> <=5 themes -> top 3 -> fee confusion -> pulse (<=250 words) + explainer (<=6 bullets).

Everything here is deterministic, key-free and runs without a human once triggered. Nothing is written:
the result is turned into two PENDING actions (doc append, email draft) that wait at the approval gate.

The connection to the response loop enters through `signals` (questions seen >= 5 times in the same window)
and leaves through the explainer, which becomes the canonical answer once a human approves the doc action.
"""
from __future__ import annotations

import re
from datetime import datetime

import config
import pii
import pipeline
from agents import ComplianceAgent

_COMP = ComplianceAgent()
FEE_ORDER = ["DP / depository charges on selling", "Auto square-off / closing charges",
             "Mutual fund exit load / expense ratio", "Brokerage & trade charges"]   # specific before generic

# which of the explainer's two sources backs each bullet (1 or 2); every bullet carries exactly one marker
CITE = {
    "Brokerage & trade charges": [1, 1, 1, 1, 2, 1],
    "DP / depository charges on selling": [1, 2, 1, 1, 1, 1],
    "Auto square-off / closing charges": [1, 1, 1, 1, 1, 1],
    "Mutual fund exit load / expense ratio": [1, 1, 1, 1, 1, 1],
}


def wc(text: str) -> int:
    return len(re.findall(r"\S+", text))


def clean_ok(text: str) -> bool:
    """Code-level filter used for every quote: no advice language, no return claims, no PII."""
    s = _COMP.scan_draft(text)
    return not (s["advice_language"] or s["return_claims"] or s["pii"])


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%d %b %Y")


def build_explainer(fee: dict) -> dict:
    kb = pipeline.FEE_KB[fee["fee"]]
    sources = []
    for i, (name, url) in enumerate(kb["sources"][:2], 1):
        sources.append({"n": i, "name": name, "url": url, "last_checked": config.last_checked_for(url)})
    cites = CITE[fee["fee"]][:config.EXPLAINER_BULLET_LIMIT]
    bullets = [{"text": b, "source_n": cites[i], "source_url": sources[cites[i] - 1]["url"]}
               for i, b in enumerate(kb["bullets"][:config.EXPLAINER_BULLET_LIMIT])]
    oldest = min((s["last_checked"] for s in sources), key=_dt)      # conservative: the older of the two dates
    return {"fee": fee["fee"], "bullets": bullets, "sources": sources, "last_checked": oldest}


def explainer_text(exp: dict) -> str:
    out = [f"**{exp['fee']}: what to know**"] + [f"- {b['text']} [{b['source_n']}]" for b in exp["bullets"]]
    out += ["", "Sources: " + " | ".join(f"[{s['n']}] {s['name']} ({s['url']})" for s in exp["sources"]),
            f"Last checked: {exp['last_checked']}"]
    return "\n".join(out)


def _trim(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0].rstrip(".,!?") + "…"


def _pulse(window: str, n: int, avg: float, top: list[dict], quotes: list[dict], fee: dict, signals: list[dict],
           qlen: int, with_signal_detail: bool) -> str:
    L = [f"**Weekly Product Pulse | {window}** ({n} reviews, avg {avg}/5)", "", "**Top themes**"]
    for t in top:
        L.append(f"- {t['label']}: {t['count']} reviews ({t['share_pct']}%), {t['negative_pct']}% rated 1-2★")
    L += ["", "**What users say**"]
    for q in quotes:
        L.append(f"- \"{_trim(q['quote'], qlen)}\" ({q['rid']}, {q['rating']}★)")
    L += ["", "**Key observation**",
          f"{fee['mentions']} reviews ({fee['pct_of_reviews']}%) mention {fee['fee'].lower()}; {fee['negative_mentions']} are "
          f"1-2★ and {fee['confusion_mentions']} use confusion words (hidden, extra, unclear, comparisons with other apps)."]
    if signals:
        L += ["", "**Support desk signal**"]
        for s in signals:
            extra = f", {s['reused']} answered from the canonical explainer" if with_signal_detail and s["reused"] else ""
            L.append(f"- \"{s['label']}\" asked {s['count']} times this week{extra}.")
    L += ["", "**Action ideas**",
          "1. Show a full charge breakup (brokerage, taxes, statutory charges) before the order is confirmed.",
          "2. Add a \"why was I charged?\" link beside every ledger and contract-note line.",
          "3. Give support one approved fee explainer and track charge-related questions weekly."]
    return "\n".join(L)


def fee_trend(csv_path, fee_name: str, end_ts, weeks: int = 8) -> list[dict]:
    """Weekly counts of reviews that mention the fee, over up to 8 weeks ending at the window end (7-day bins)."""
    import pandas as pd
    df, _ = pipeline.load_reviews(csv_path, weeks=weeks + 0.01)
    rx = re.compile(pipeline.FEE_TYPES[fee_name], re.I)
    df["m"] = df["text"].str.lower().map(lambda s: bool(rx.search(s)))
    df["bin"] = ((end_ts - df["date"]).dt.total_seconds() // (7 * 86400)).astype(int)
    out = []
    for b in range(weeks - 1, -1, -1):
        sub = df[df["bin"] == b]
        if len(sub):
            out.append({"week_end": (end_ts - pd.Timedelta(days=7 * b)).strftime("%d %b"), "reviews": int(len(sub)),
                        "mentions": int(sub["m"].sum()), "negative": int((sub["m"] & (sub["rating"] <= 2)).sum())})
    return out


def build(csv_path, signals: list[dict], week_days: int | None = None) -> dict:
    week_days = week_days or config.WEEK_DAYS
    df, info = pipeline.load_reviews(csv_path, weeks=week_days / 7)
    # defence in depth: the CSV is already redacted at preparation, ingest redacts again and counts what it found
    found = info.get("pii_redacted", 0)
    texts = []
    for t in df["text"]:
        r, f = pii.redact(t)
        found += sum(x["count"] for x in f)
        texts.append(r)
    df["text"] = texts
    df, themes = pipeline.cluster_reviews(df)
    top = pipeline.rank_top_themes(themes)
    quotes = pipeline.extract_quotes(df, top, ok=clean_ok)
    fee = pipeline.detect_fee_issue(df)
    start, end = info["window"]
    end_ts = df["date"].max()
    window = f"{start} to {end}"
    window_exact = f"{(end_ts - __import__('pandas').Timedelta(days=week_days)).isoformat(timespec='seconds')} to {end_ts.isoformat(timespec='seconds')}"
    avg = round(float(df["rating"].mean()), 2)
    pulse = ""
    for qlen, detail in [(160, True), (130, True), (110, True), (90, False), (70, False)]:
        pulse = _pulse(window, len(df), avg, top, quotes, fee, signals, qlen, detail)
        if wc(pulse) <= config.PULSE_WORD_LIMIT:
            break
    exp = build_explainer(fee)
    theme_rows = [{"label": t["label"], "count": t["count"], "share_pct": t["share_pct"], "avg_rating": t["avg_rating"],
                   "negative_pct": t["negative_pct"], "review_ids": t["review_ids"], "window": window,
                   "is_top3": t in top} for t in themes]
    scan = _COMP.scan_draft(pulse + "\n" + explainer_text(exp))
    checks = [
        ("<= 5 themes", len(themes) <= pipeline.MAX_THEMES, f"{len(themes)} themes"),
        ("every theme has review ids and a stated window", all(r["review_ids"] and r["window"] for r in theme_rows), window),
        ("3 quotes, each with a review id", len(quotes) == 3 and all(q["rid"] for q in quotes), f"{len(quotes)} quotes"),
        (f"pulse <= {config.PULSE_WORD_LIMIT} words", wc(pulse) <= config.PULSE_WORD_LIMIT, f"{wc(pulse)} words"),
        ("3 action ideas", len(re.findall(r"^\d\. ", pulse, re.M)) == 3, "numbered"),
        (f"explainer <= {config.EXPLAINER_BULLET_LIMIT} bullets", len(exp["bullets"]) <= config.EXPLAINER_BULLET_LIMIT, f"{len(exp['bullets'])} bullets"),
        ("explainer has 2 official links", len(exp["sources"]) == 2, ", ".join(s["url"] for s in exp["sources"])),
        ("explainer has 'last checked'", bool(exp["last_checked"]), exp["last_checked"]),
        ("no advice / return claim / PII in pulse or explainer", not (scan["advice_language"] or scan["return_claims"] or scan["pii"]), "scanned"),
    ]
    return {"window": window, "window_exact": window_exact, "days": week_days, "n_reviews": len(df), "avg_rating": avg,
            "rows_in_export": info["rows_in"], "pii_redacted_at_ingest": found,
            "themes": theme_rows, "top_labels": [t["label"] for t in top], "quotes": quotes, "fee": {
                k: fee[k] for k in ("fee", "mentions", "negative_mentions", "pct_of_reviews", "confusion_mentions",
                                    "evidence", "review_ids", "all_candidates")},
            "fee_trend": fee_trend(csv_path, fee["fee"], end_ts), "signals": signals, "pulse": pulse, "pulse_words": wc(pulse), "explainer": exp,
            "explainer_text": explainer_text(exp), "checks": checks}


def entry_markdown(run: dict, approved_at: str) -> str:
    th = "\n".join(f"- {t['label']}: {t['count']} reviews in {t['window']} (ids: {', '.join(t['review_ids'][:8])}"
                   f"{', …' if len(t['review_ids']) > 8 else ''}; {len(t['review_ids'])} ids stored in the run)" for t in run["themes"])
    return (f"\n---\n## Weekly pulse {run['window']} (run {run['run_id']}, approved {approved_at})\n\n"
            f"{run['pulse']}\n\n### Fee explainer (canonical for support)\n{run['explainer_text']}\n\n"
            f"### Evidence: review ids behind each theme\n{th}\n")


def email_body(run: dict) -> str:
    return (f"{run['pulse']}\n\n---\nFee explainer for support:\n{run['explainer_text']}\n\n"
            f"(Window {run['window']}; review ids per theme are in the team doc entry for run {run['run_id']}.)")
