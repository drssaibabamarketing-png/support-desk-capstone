"""Builds data/demo_snapshot.json: the ONLY data the public /demo page shows.

Run: python make_demo.py

Sanitised by construction:
  * a throwaway Service in a temp folder (output, logs and SQLite journal all redirected before any project import),
    so the live desk's queue, journal, audit log and written files are never read;
  * questions: the synthetic seed set (data/questions.csv) plus five fixed sample questions; the one that shows
    redaction uses a dummy PAN assembled at run time, and only the redacted text is kept;
  * weekly: the bundled public-review replay (data/reviews.csv, already redacted), counts and texts only;
  * no approval actions, gates, receipts, audit lines, written files or timestamps of human decisions are exported;
  * the snapshot is refused (exit 1) if pii.detect finds anything in it.
Review the diff of data/demo_snapshot.json before committing it.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="demo_build_"))
os.environ["DESK_OUT"], os.environ["DESK_LOGS"], os.environ["DESK_DB"] = str(TMP / "out"), str(TMP / "logs"), str(TMP / "demo.db")
os.environ.pop("REVIEWS_CSV", None)
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import pii  # noqa: E402
from service import Service  # noqa: E402

OUT = ROOT / "data" / "demo_snapshot.json"
PAN = "ABCDE" + "1234F"                         # dummy, never a real person's; only its redacted form is stored
SAMPLES = [("Fee question, answered from the approved canonical explainer", "Why was brokerage deducted again when I sold my shares?"),
           ("Scheme fact from the official corpus", "What is the exit load of HDFC Small Cap Fund?"),
           ("Question the official sources cannot answer", "Do HDFC funds invest in cryptocurrency?"),
           ("Advice request (refused)", "Should I redeem my HDFC Small Cap Fund units?"),
           ("Message containing a PAN (removed before storage)", f"My PAN is {PAN}. Why is a DP charge applied when I sell?")]


def ticket_view(svc: Service, tid: str, kind: str) -> dict:
    t = svc.desk.tickets[tid]
    f, d = t["outputs"]["facts"], t["draft"]
    return {"kind": kind, "question": t["message"], "intent": svc.intent_of(t),
            "pii_removed": [x["type"] for x in t["pii_removed"]],
            "facts_status": f["status"], "searched": f.get("searched", [])[-3:] if f["status"] != "covered" else [],
            "canonical": bool(f.get("canonical")), "reply": d["reply"]["full_text"], "citation_url": d["reply"]["citation_url"],
            "last_checked": d["reply"]["last_checked"], "routing_note": d["routing"]["note"], "hold": d["routing"]["hold"],
            "reviewer_passed": t["review"]["passed"], "failure_codes": [x["code"] for x in t["review"]["failures"]],
            "pattern": {k: t["outputs"]["pattern"][k] for k in ("trend", "similar_count", "theme")},
            "agents_fired": t["fired_log"][0]["agents_fired"]}


def build() -> dict:
    svc = Service()
    svc.seed()
    run = svc.run_weekly()
    svc.decide_action(run["action_ids"][0], True)     # inside the temp folder only: makes the explainer canonical for sample 1
    tickets = [ticket_view(svc, svc.submit_question(q), kind) for kind, q in SAMPLES]
    groups = [{"label": g["label"], "count": g["count"]} for g in svc.question_groups(
        svc.window_end - __import__("pandas").Timedelta(days=config.WEEK_DAYS), svc.window_end) if g["key"] != "advice"]
    return {
        "generated_by": "make_demo.py", "generated_on": config.today().isoformat(),
        "data_note": ("Sample data only: synthetic questions written for this demo and a replay of the bundled, redacted public "
                      "Play Store review export. No live queue, ticket, approval, audit or written-file data."),
        "weekly": {"window": run["window"], "n_reviews": run["n_reviews"], "rows_in_export": run["rows_in_export"],
                   "pulse": run["pulse"], "pulse_words": run["pulse_words"],
                   "themes": [{k: t[k] for k in ("label", "count", "share_pct", "negative_pct", "is_top3")} for t in run["themes"]],
                   "fee": {k: run["fee"][k] for k in ("fee", "mentions", "negative_mentions", "pct_of_reviews")},
                   "explainer": run["explainer"], "checks": [[n, bool(ok), str(det)] for n, ok, det in run["checks"]]},
        "sample_question_topics": groups,
        "tickets": tickets,
    }


def main() -> int:
    try:
        snap = build()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    text = json.dumps(snap, ensure_ascii=False, indent=1)
    leaked = pii.detect(text)
    if leaked or PAN in text:
        print("REFUSED: the snapshot contains PII-like data:", leaked)
        return 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    print("wrote", OUT.relative_to(ROOT), f"({len(snap['tickets'])} sample tickets, weekly window {snap['weekly']['window']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
