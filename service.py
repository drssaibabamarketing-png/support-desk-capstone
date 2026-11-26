"""The Support Desk service: one object that owns both loops and the link between them.

  response loop : queue of questions -> Desk (3 agents in parallel, orchestrator, reviewer) -> human edit/approve/reject
  weekly loop   : reviews CSV -> pulse + explainer -> two PENDING actions -> human approves each one separately
  link          : (a) questions seen >= 5 times in the window are passed into the weekly pulse (`signals`)
                  (b) an APPROVED weekly explainer is registered as the canonical answer the Facts agent reuses

State rules: every write goes through mcp_layer.call_tool with that action's own ApprovalGate. Nothing here writes a file
by itself. `snapshot()` is a deterministic view of all state, used by the edit-correctness eval to diff before/after.
"""
from __future__ import annotations

import contextlib
import copy
import csv
import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime

import pandas as pd

import config
import mcp_layer as mcp
import pii
import pipeline
import reviewer as reviewer_mod
import weekly
from corpus import detect_intents, detect_schemes
from desk import Desk, log_event

_FEE_RX = {k: re.compile(v, re.I) for k, v in pipeline.FEE_TYPES.items()}


def fee_topic(message: str) -> str | None:
    """Which Groww fee topic a message is about (specific before generic), or None. Used for canonical reuse and counting."""
    intents = set(detect_intents(message))
    if "dp_charges" in intents:
        return "DP / depository charges on selling"
    if "square_off" in intents:
        return "Auto square-off / closing charges"
    if intents & {"exit_load", "expense_ratio"}:
        return "Mutual fund exit load / expense ratio"
    if "brokerage" in intents:                       # brokerage, charges, charged, fee, deduct...
        return "Brokerage & trade charges"
    for name in weekly.FEE_ORDER:
        if _FEE_RX[name].search(message):
            return name
    return None


_GENERIC = {"share", "stock", "sell", "sold", "deduct", "charg", "order", "fees", "when", "again", "what", "that", "this",
            "have", "with", "from", "your", "were", "been", "does", "about", "please", "tell", "much", "many", "apply", "applied"}


def _words(s: str) -> set[str]:
    """Content-word stems (first 5 letters) with generic words removed, so 'sold shares' cannot out-vote 'brokerage'."""
    return {w[:5] for w in re.findall(r"[a-z]{4,}", s.lower()) if w[:5] not in _GENERIC and w[:6] not in _GENERIC}


class Journal:
    """Append-only SQLite journal of HUMAN decisions and live questions (redacted text only), replayed at start-up so a restart
    does not lose approvals, edits or the canonical explainers. Best-effort: a journal failure never blocks the desk.
    The database lives in DESK_DB (default <logs>/state.db). It survives restarts only where that path is on a persistent disk
    (a Docker volume, a Render paid disk); on an ephemeral filesystem it is lost with the container."""

    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("DESK_DB") or str(config.LOGS / "state.db")
        self.on = True
        try:
            config.LOGS.mkdir(parents=True, exist_ok=True)
            with self._conn() as c:
                c.execute("create table if not exists events (id integer primary key autoincrement, ts text, kind text, body text)")
        except Exception:                                    # noqa: BLE001
            self.on = False

    @contextlib.contextmanager
    def _conn(self):
        """Commit on success, roll back on error, and ALWAYS close. `with sqlite3.connect()` alone only commits; the open
        handle then keeps the file locked on Windows (the evals could not move state.db) and leaks a connection per call."""
        c = sqlite3.connect(self.path)
        try:
            with c:
                yield c
        finally:
            c.close()

    def add(self, kind: str, **body) -> None:
        if not self.on:
            return
        try:
            with self._conn() as c:
                c.execute("insert into events (ts, kind, body) values (?,?,?)",
                          (datetime.now().isoformat(timespec="seconds"), kind, json.dumps(body, ensure_ascii=False)))
        except Exception:                                    # noqa: BLE001
            pass

    def events(self) -> list[tuple[str, dict]]:
        if not self.on:
            return []
        try:
            with self._conn() as c:
                return [(k, json.loads(b)) for k, b in c.execute("select kind, body from events order by id")]
        except Exception:                                    # noqa: BLE001
            return []


class Service:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.journal = Journal()
        self._replaying = False
        self._restored = False
        self.canonical: dict[str, dict] = {}                 # fee -> approved explainer record
        self.desk = Desk(canonical=self.canonical_lookup)
        self.order: list[str] = []                           # ticket ids in queue order
        self.meta: dict[str, dict] = {}                      # tid -> queue metadata (no message text)
        self.actions: dict[str, dict] = {}                   # action id -> action
        self.runs: list[dict] = []
        self._qn = 0
        self.reviews_path = str(config.REVIEWS_CSV)
        self.reviews_source = "bundled export (historical replay)"
        self.window_end = self._review_end()

    # ------------------------------------------------------------------ helpers
    def _review_end(self) -> datetime:
        d = pd.read_csv(self.reviews_path, usecols=["date"])["date"]
        return pd.to_datetime(d).max().to_pydatetime()

    def use_reviews(self, data: bytes, filename: str = "upload.csv", replay: bool = False) -> dict:
        """Replace the reviews source with an uploaded CSV. Text is redacted BEFORE the copy is saved, so raw PII never touches disk.
        The weekly window becomes the newest 7 days of the NEW file. Returns {ok, ...} or {ok: False, error}."""
        import io
        from agents import PatternAgent
        try:
            raw = pd.read_csv(io.BytesIO(data))
            tcol, rcol, dcol = (pipeline._pick(raw, k) for k in ("text", "rating", "date"))
            if tcol is None or rcol is None or dcol is None:
                return {"ok": False, "error": "The CSV needs a review text, a rating and a date column "
                        f"(accepted names: {pipeline.COLUMN_ALIASES['text']} / {pipeline.COLUMN_ALIASES['rating']} / {pipeline.COLUMN_ALIASES['date']})."}
            df = pd.DataFrame({"rid": raw["rid"].astype(str) if "rid" in raw.columns else [f"U{i + 1}" for i in range(len(raw))],
                               "review_text": raw[tcol].astype(str).map(lambda t: pii.redact(t)[0]),
                               "rating": pd.to_numeric(raw[rcol], errors="coerce"), "date": pd.to_datetime(raw[dcol], errors="coerce")})
            df = df.dropna(subset=["rating", "date"])
            if len(df) < 30:
                return {"ok": False, "error": f"Only {len(df)} usable rows (need at least 30 with text, rating and date)."}
            end = df["date"].max()
            if len(df[df["date"] > end - pd.Timedelta(days=config.WEEK_DAYS)]) < 10:
                return {"ok": False, "error": "Fewer than 10 reviews fall in the newest 7 days of this file."}
        except Exception as e:                                # noqa: BLE001
            return {"ok": False, "error": f"Could not read that file as a reviews CSV ({type(e).__name__})."}
        with self.lock:
            config.LOGS.mkdir(parents=True, exist_ok=True)
            path = config.LOGS / "uploaded_reviews.csv"
            df.to_csv(path, index=False)
            self.reviews_path = str(path)
            self.reviews_source = f"uploaded file '{re.sub(r'[^A-Za-z0-9._ -]', '', filename)[:60]}'"
            config.REVIEWS_CSV = path
            PatternAgent._idx = None
            self.window_end = self._review_end()
            if not replay:
                self.journal.add("reviews", filename=filename)
        return {"ok": True, "rows": int(len(df)), "newest": end.date().isoformat()}

    def now(self) -> str:
        return (self.window_end if config.DEMO_CLOCK else datetime.now()).isoformat(timespec="seconds")

    def canonical_lookup(self, message: str) -> dict | None:
        fee = fee_topic(message)
        rec = self.canonical.get(fee) if fee else None
        if not rec:
            return None
        bullets = rec["bullets"]
        q = _words(message)
        best = max(range(len(bullets)), key=lambda i: (len(q & _words(bullets[i]["text"])), -i))
        b = bullets[best]
        return {"fee": fee, "answer": b["text"], "citation_url": b["source_url"], "version": rec["version"],
                "approved_at": rec["approved_at"], "bullet_index": best + 1, "explainer_id": rec["action_id"]}

    # ------------------------------------------------------------------ response loop
    def topic_of(self, t: dict) -> tuple[str, str]:
        o, msg = t["outputs"], t["message"]
        if o["compliance"]["advice_requested"]:
            return "advice", "Advice / returns requests (refused)"
        schemes = detect_schemes(msg)
        fee = None if schemes else fee_topic(msg)
        f = o["facts"]
        if not fee and not schemes and f.get("scheme_id") == "groww_fees":
            fee = "Brokerage & trade charges"
        if fee:
            label = {"Brokerage & trade charges": "Groww brokerage and charges",
                     "DP / depository charges on selling": "Groww DP (depository) charges",
                     "Auto square-off / closing charges": "Groww auto square-off charges",
                     "Mutual fund exit load / expense ratio": "Exit load / expense ratio"}[fee]
            return "fee:" + fee, label
        if f["status"] == "covered":
            intent = (f.get("intents") or ["fact"])[0]
            label = {"exit_load": "HDFC scheme exit load", "expense_ratio": "HDFC scheme expense ratio",
                     "min_sip": "HDFC scheme minimum SIP", "lock_in": "ELSS lock-in", "statement": "Account statement",
                     "capital_gains": "Capital gains statement", "kyc": "KYC", "riskometer": "Riskometer",
                     "benchmark": "Benchmark"}.get(intent, f"Factual question ({intent})")
            return f"faq:{intent}", label
        theme = o["pattern"].get("theme") or "Other"
        return f"other:{theme}", f"Not covered: {theme}"

    def intent_of(self, t: dict) -> str:
        o = t["outputs"]
        if o["compliance"]["advice_requested"]:
            return "Advice / returns request (refused)"
        if o["facts"].get("canonical"):
            return "Fee question (canonical explainer reused)"
        if o["facts"]["status"] == "covered":
            return "Factual question (corpus)"
        return "Not covered (routed to a team)"

    def submit_question(self, text: str, q_id: str | None = None, received_at: str | None = None) -> str:
        with self.lock:
            t = self.desk.submit(text[:2000], session_id="queue")        # raw text redacted inside submit, first line
            del text
            self._qn += 1
            key, label = self.topic_of(t)
            self.meta[t["tid"]] = {
                "q_id": q_id or f"Q-{self._qn:03d}", "received_at": received_at or self.now(), "key": key,
                "label": label, "status": "pending", "edited": False, "edit_count": 0, "writes": [],
                "gate": mcp.ApprovalGate("Append record to support log + create reply email draft (never sent)"),
            }
            self.order.append(t["tid"])
            if q_id is None and not self._replaying:           # a live question (not the seeded set): journal the REDACTED text
                self.journal.add("submit", q_id=self.meta[t["tid"]]["q_id"], text=t["message"], received_at=self.meta[t["tid"]]["received_at"])
            return t["tid"]

    def seed(self) -> int:
        with open(config.QUESTIONS_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.submit_question(row["text"], row["q_id"], row["received_at"])
        return len(self.order)

    def edit_draft(self, tid: str, body: str) -> dict:
        """A human edits the reply BODY of one ticket. The edit must pass the same reviewer; otherwise nothing changes."""
        with self.lock:
            t, m = self.desk.tickets[tid], self.meta[tid]
            if m["status"] != "pending":
                return {"ok": False, "error": f"ticket already {m['status']}"}
            body = (body or "").strip()
            if pii.detect(body):
                return {"ok": False, "error": "The edit contains personal data (" + ", ".join(pii.detect(body)) + "). Remove it; nothing was changed."}
            checked = t["draft"]["reply"]["last_checked"]
            cand = copy.deepcopy(t["draft"])
            full = f"{body}\n\nLast checked: {checked}"
            sents, _ = reviewer_mod.split_reply(full)
            cand["reply"].update(body=body, full_text=full, sentences=[{"text": s["text"], "type": "edited"} for s in sents])
            rv = reviewer_mod.review(cand, t["outputs"]["facts"], self.desk.compliance)
            # On REPLAY, an edit that was accepted when it was made is re-applied even if the only failure now is
            # STALE_FACT (time has passed since the source check): the human's wording is kept, and the ticket stays
            # flagged so it cannot be approved until the source is re-checked. Before this, the edit was silently lost.
            stale_only = bool(rv["failures"]) and all(f["code"] == "STALE_FACT" for f in rv["failures"])
            if not rv["passed"] and not (self._replaying and stale_only):
                if self._replaying:
                    log_event({"event": "edit_not_restored", "ticket": tid, "q_id": m["q_id"],
                               "failure_codes": [f["code"] for f in rv["failures"]]})
                return {"ok": False, "error": "The reviewer rejected the edit: " + "; ".join(f"{f['code']}" for f in rv["failures"])
                        + ". Nothing was changed.", "failures": rv["failures"]}
            t["draft"], t["review"] = cand, rv
            t["flagged"] = t["send_blocked"] = not rv["passed"]
            m["edited"], m["edit_count"] = True, m["edit_count"] + 1
            log_event({"event": "human_edit", "ticket": tid, "q_id": m["q_id"], "reviewer": "pass" if rv["passed"] else "STALE_FACT (restored, flagged)"})
            if not self._replaying:
                self.journal.add("edit", q_id=m["q_id"], body=body)
            return {"ok": True}

    def redraft_with_canonical(self, tid: str) -> dict:
        """Re-run Facts + orchestrator + reviewer on ONE pending ticket (e.g. after an explainer was approved)."""
        with self.lock:
            t, m = self.desk.tickets[tid], self.meta[tid]
            if m["status"] != "pending":
                return {"ok": False, "error": f"ticket already {m['status']}"}
            t["outputs"]["facts"] = self.desk.facts.run(t["message"])
            t["counters"]["facts"] += 1
            fired = ["facts"] + self.desk._draft_and_review(t)
            t["fired_log"].append({"turn": len(t["fired_log"]), "what": "re-draft (canonical explainer check)", "agents_fired": fired})
            m["edited"] = False
            m["key"], m["label"] = self.topic_of(t)
            self.desk._log(t, "redraft", fired)
            if not self._replaying:                          # a later edit is reviewed against THIS draft's fact
                self.journal.add("redraft", q_id=m["q_id"])
            return {"ok": True, "canonical": bool(t["outputs"]["facts"].get("canonical"))}

    def refine(self, tid: str, instruction: str) -> dict:
        """A reviewer's refinement note for one pending ticket. Journalled (redacted) so a restart keeps it."""
        with self.lock:
            m = self.meta[tid]
            if m["status"] != "pending":
                return {"ok": False, "error": f"ticket already {m['status']}"}
            instr = pii.redact(instruction or "")[0]
            res = self.desk.refine(tid, instr)
            if res.get("ok") and not self._replaying:
                self.journal.add("refine", q_id=m["q_id"], instruction=instr)
            return res

    def decide_ticket(self, tid: str, approve: bool) -> dict:
        with self.lock:
            t, m = self.desk.tickets[tid], self.meta[tid]
            if m["status"] != "pending":
                return {"ok": False, "error": f"ticket already {m['status']}"}
            if approve and t["send_blocked"]:
                return {"ok": False, "status": 403, "error": "The reviewer flagged this draft; it cannot be approved."}
            m["gate"].decide(approve)
            if approve:
                # Atomic decision: the ticket becomes "approved" (and is journalled) only after BOTH writes succeeded.
                # On a failure the gate goes back to pending; writes that did complete are remembered, so approving
                # again performs only the missing ones and never appends a duplicate record.
                record, email = mcp.build_payloads(t)
                record["ticket_id"] = m["q_id"] + "/" + t["tid"]
                done = m.setdefault("written", {})
                try:
                    for tool, payload in (("append_support_record", record), ("create_email_draft", email)):
                        if tool not in done:
                            done[tool] = mcp.call_tool(tool, payload, m["gate"])
                except Exception as e:                           # noqa: BLE001
                    m["gate"].status, m["gate"].decided_at = "pending", None
                    log_event({"event": "ticket_write_failed", "ticket": tid, "q_id": m["q_id"], "error": type(e).__name__,
                               "completed": sorted(done)})
                    return {"ok": False, "status": 500, "error": f"A write failed ({type(e).__name__}); the ticket is still pending "
                            f"and was not recorded as approved. Completed: {', '.join(sorted(done)) or 'none'}. "
                            "Approving again performs only the missing write."}
                m["writes"] = list(done.items())
            m["status"] = "approved" if approve else "rejected"
            t["decision"] = m["gate"].status
            log_event({"event": "ticket_decision", "ticket": tid, "q_id": m["q_id"], "decision": m["status"]})
            if not self._replaying:
                self.journal.add("ticket", q_id=m["q_id"], status=m["status"])
            return {"ok": True}

    def will_write(self, tid: str) -> list[dict]:
        """Exactly what approving this ticket will write, and where (shown before the click)."""
        t = self.desk.tickets[tid]
        record, email = mcp.build_payloads(t)
        return [{"tool": "append_support_record", "where": f"{config.OUT.name}/support_log.md (+ .jsonl)",
                 "what": f"Ticket entry: redacted question, reply draft, citation, routing note ({len(json.dumps(record))} chars)"},
                {"tool": "create_email_draft", "where": f"{config.OUT.name}/support_reply_draft.eml (X-Unsent, never sent)",
                 "what": f"Subject: {email['subject']}"}]

    # ------------------------------------------------------------------ the link: question counts
    def question_groups(self, start: datetime, end: datetime) -> list[dict]:
        groups: dict[str, dict] = {}
        for tid in self.order:
            m = self.meta[tid]
            ts = datetime.fromisoformat(m["received_at"])
            if not (start < ts <= end):
                continue
            g = groups.setdefault(m["key"], {"key": m["key"], "label": m["label"], "count": 0, "q_ids": [], "reused": 0})
            g["count"] += 1
            g["q_ids"].append(m["q_id"])
            g["reused"] += 1 if self.desk.tickets[tid]["outputs"]["facts"].get("canonical") else 0
        return sorted(groups.values(), key=lambda g: -g["count"])

    # ------------------------------------------------------------------ weekly loop
    def run_weekly(self) -> dict:
        with self.lock:
            end = self.window_end
            start = end - pd.Timedelta(days=config.WEEK_DAYS)
            groups = self.question_groups(start.to_pydatetime() if hasattr(start, "to_pydatetime") else start, end)
            sig = [g for g in groups if g["count"] >= config.RECURRING_QUESTION_MIN and g["key"] != "advice"
                   and not g["key"].startswith("other:")]
            run = weekly.build(self.reviews_path, sig)
            # the id covers everything a weekly action writes, so identical id <=> identical content
            run["run_id"] = "W-" + hashlib.sha1((run["window"] + run["pulse"] + run["explainer_text"]).encode()).hexdigest()[:6]
            run["question_groups"] = groups
            run["created"] = self.now()
            for a in self.actions.values():                         # a DIFFERENT run's pending actions are superseded
                if a["status"] == "pending" and a["run_id"] != run["run_id"]:
                    a["status"] = "superseded"
            run["action_ids"] = []
            specs = [("append_weekly_record", f"{config.OUT.name}/weekly_log.md (+ .jsonl)", "Append pulse + fee explainer entry (with review ids per theme) to the team doc"),
                     ("create_weekly_email", f"{config.OUT.name}/weekly_pulse_draft.eml (X-Unsent, never sent)", "Create the weekly pulse email draft")]
            for tool, where, what in specs:
                # Re-running identical content must never reopen an APPROVED action: its file was already written, and a
                # second approval would append a duplicate entry and bump the canonical version. A pending action keeps
                # its gate. A rejected or superseded one wrote nothing, so the same content may be offered again, but as
                # a NEW action with a new id: the earlier record and its decision are kept, never overwritten.
                same = [a for a in self.actions.values() if a["run_id"] == run["run_id"] and a["tool"] == tool]
                live = next((a for a in same if a["status"] in ("pending", "approved")), None)
                if live:
                    run["action_ids"].append(live["id"])
                    continue
                aid = f"{run['run_id']}:{tool}" + (f":{len(same) + 1}" if same else "")
                self.actions[aid] = {"id": aid, "run_id": run["run_id"], "tool": tool, "where": where, "what": what,
                                     "status": "pending", "gate": mcp.ApprovalGate(what), "result": None}
                run["action_ids"].append(aid)
            self.runs = [r for r in self.runs if r["run_id"] != run["run_id"]] + [run]
            log_event({"event": "weekly_run", "run": run["run_id"], "window": run["window"], "reviews": run["n_reviews"],
                       "themes": len(run["themes"]), "pulse_words": run["pulse_words"], "signals": [s["key"] for s in sig]})
            return run

    def latest_run(self) -> dict | None:
        return self.runs[-1] if self.runs else None

    def action_payload(self, aid: str) -> dict:
        a = self.actions[aid]
        run = next(r for r in self.runs if r["run_id"] == a["run_id"])
        if a["tool"] == "append_weekly_record":
            return {"run_id": run["run_id"], "window": run["window"], "pulse": run["pulse"],
                    "explainer": run["explainer_text"], "entry_md": weekly.entry_markdown(run, "{approval time}")}
        return {"to": "", "subject": f"Weekly product pulse {run['window']} (draft, run {run['run_id']})",
                "body": weekly.email_body(run)}

    def decide_action(self, aid: str, approve: bool) -> dict:
        with self.lock:
            a = self.actions[aid]
            if a["status"] != "pending":
                return {"ok": False, "error": f"action already {a['status']}"}
            a["gate"].decide(approve)
            if approve:
                # Atomic decision: "approved", the canonical explainer and the journal row only after the write succeeded.
                payload = self.action_payload(aid)
                if a["tool"] == "append_weekly_record":
                    payload["entry_md"] = payload["entry_md"].replace("{approval time}", a["gate"].decided_at)
                try:
                    a["result"] = mcp.call_tool(a["tool"], payload, a["gate"])
                except Exception as e:                           # noqa: BLE001
                    a["gate"].status, a["gate"].decided_at = "pending", None
                    log_event({"event": "action_write_failed", "action": aid, "error": type(e).__name__})
                    return {"ok": False, "error": f"The write failed ({type(e).__name__}); the action is still pending and "
                            "was not recorded as approved."}
                if a["tool"] == "append_weekly_record":
                    self._register_canonical(a, next(r for r in self.runs if r["run_id"] == a["run_id"]))
            a["status"] = "approved" if approve else "rejected"
            log_event({"event": "action_decision", "action": aid, "decision": a["status"]})
            if not self._replaying:
                self.journal.add("action", tool=a["tool"], window=next(r for r in self.runs if r["run_id"] == a["run_id"])["window"],
                                 status=a["status"], decided_at=a["gate"].decided_at)
            return {"ok": True}

    def _register_canonical(self, a: dict, run: dict) -> None:
        exp = run["explainer"]
        prev = self.canonical.get(exp["fee"])
        self.canonical[exp["fee"]] = {"fee": exp["fee"], "bullets": exp["bullets"], "sources": exp["sources"],
                                      "last_checked": exp["last_checked"], "version": (prev["version"] + 1) if prev else 1,
                                      "approved_at": a["gate"].decided_at[:10], "action_id": a["id"], "run_id": run["run_id"]}

    def restore(self) -> dict:
        """Replay the journal: live questions, human edits, ticket and weekly decisions, canonical explainers. Writes nothing."""
        n = {"questions": 0, "refinements": 0, "redrafts": 0, "edits": 0, "tickets": 0, "actions": 0}
        with self.lock:
            if self._restored:                                  # idempotent: replaying twice must not duplicate anything
                return n
            self._restored = True
            self._replaying = True
            try:
                for kind, b in self.journal.events():
                    if kind == "reviews":
                        p = config.LOGS / "uploaded_reviews.csv"
                        if p.exists():
                            self.use_reviews(p.read_bytes(), b.get("filename", "upload.csv"), replay=True)
                            self.run_weekly()
                    elif kind == "submit":
                        if self._tid(b["q_id"]) is None:        # never create a second ticket for the same journalled question
                            self.submit_question(b["text"], b["q_id"], b["received_at"]); n["questions"] += 1
                    elif kind == "refine":
                        tid = self._tid(b["q_id"])
                        if tid and self.meta[tid]["status"] == "pending" and self.refine(tid, b["instruction"]).get("ok"):
                            n["refinements"] += 1
                    elif kind == "redraft":
                        tid = self._tid(b["q_id"])
                        if tid and self.meta[tid]["status"] == "pending" and self.redraft_with_canonical(tid).get("ok"):
                            n["redrafts"] += 1
                    elif kind == "edit":
                        tid = self._tid(b["q_id"])
                        if tid and self.edit_draft(tid, b["body"]).get("ok"):
                            n["edits"] += 1
                    elif kind == "ticket":
                        tid = self._tid(b["q_id"])
                        if tid and self.meta[tid]["status"] == "pending":
                            m = self.meta[tid]
                            m["gate"].decide(b["status"] == "approved"); m["status"] = b["status"]
                            self.desk.tickets[tid]["decision"] = b["status"]
                            m["writes"] = [("restored from journal (files were written when it was approved)", {})]
                            n["tickets"] += 1
                    elif kind == "action":
                        a = next((x for x in self.actions.values() if x["tool"] == b["tool"] and x["status"] == "pending"
                                  and next(r for r in self.runs if r["run_id"] == x["run_id"])["window"] == b["window"]), None)
                        if a:
                            a["gate"].decide(b["status"] == "approved"); a["gate"].decided_at = b["decided_at"]; a["status"] = b["status"]
                            a["result"] = {"restored": True}
                            if b["status"] == "approved" and a["tool"] == "append_weekly_record":
                                self._register_canonical(a, next(r for r in self.runs if r["run_id"] == a["run_id"]))
                            n["actions"] += 1
            finally:
                self._replaying = False
        return n

    def _tid(self, q_id: str) -> str | None:
        return next((t for t in self.order if self.meta[t]["q_id"] == q_id), None)

    # ------------------------------------------------------------------ state view for diffs and the UI
    def snapshot(self) -> dict:
        tickets = {}
        for tid, t in self.desk.tickets.items():
            m = self.meta[tid]
            tickets[tid] = {"reply": t["draft"]["reply"]["full_text"], "note": t["draft"]["routing"]["note"],
                            "status": m["status"], "edited": m["edited"], "flagged": t["flagged"],
                            "facts": t["outputs"]["facts"]["status"], "canonical": bool(t["outputs"]["facts"].get("canonical")),
                            "writes": [w[0] for w in m["writes"]]}
        files = {}
        if config.OUT.exists():
            for p in sorted(config.OUT.iterdir()):
                if p.is_file():
                    files[p.name] = hashlib.sha1(p.read_bytes()).hexdigest()[:10]
        return {"tickets": tickets, "actions": {k: a["status"] for k, a in self.actions.items()},
                "canonical": {k: v["version"] for k, v in self.canonical.items()}, "files": files}


def diff(before: dict, after: dict) -> list[str]:
    out = []

    def walk(a, b, path=""):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                if k not in a:
                    out.append(f"+ {path}/{k}")
                elif k not in b:
                    out.append(f"- {path}/{k}")
                else:
                    walk(a[k], b[k], f"{path}/{k}")
        elif a != b:
            out.append(f"~ {path}")
    walk(before, after)
    return out
