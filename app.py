"""Flask UI for the Support Desk capstone. Thin routes over service.Service; every write goes through an approval gate."""
import hmac
import json
import os
import re
import secrets
import time

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape

import config
import corpus
import mcp_layer as mcp
from service import Service

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32), SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=bool(os.environ.get("COOKIE_SECURE")),
                  PERMANENT_SESSION_LIFETIME=8 * 3600)
if int(os.environ.get("PROXY_HOPS", "0")) > 0:                 # e.g. 1 on Render: trust exactly that many proxies
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=int(os.environ["PROXY_HOPS"]), x_proto=int(os.environ["PROXY_HOPS"]))

# ---------------------------------------------------------------- access control (fail closed)
# The live desk (queue, tickets, weekly actions, approvals, audit, written files, sources-by-ticket, live numbers) and
# EVERY state-changing request, including submitting a question, need a logged-in reviewer. Anonymous visitors get only
# PUBLIC_ENDPOINTS: the read-only sample demo (data/demo_snapshot.json, synthetic data, no operational records), the
# eval evidence already published in the repository, login and the health check. If REVIEWER_PASSWORD is not set,
# nobody is a reviewer: the live desk is closed (there is no "open demo mode" in which anyone can approve).
# Every POST (except the token-protected machine API) needs a CSRF token that the server adds to each form.
PUBLIC_ENDPOINTS = {"demo", "evals", "login", "logout", "healthz", "static", "api_weekly_run"}
_FAILS: dict[str, list[float]] = {}


def auth_enabled() -> bool:
    return bool(os.environ.get("REVIEWER_PASSWORD"))


def is_reviewer() -> bool:
    return auth_enabled() and bool(session.get("reviewer"))


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def safe_next(nxt: str | None) -> str:
    """Only same-site relative paths (no //host, no /\\host, which browsers treat as //host)."""
    nxt = nxt or "/"
    return nxt if nxt.startswith("/") and not nxt.startswith("//") and "\\" not in nxt else "/"


@app.before_request
def guard():
    ep = request.endpoint
    if ep is None:
        return None                                            # unknown URL: Flask answers 404 / 405
    if request.method == "POST" and ep not in ("api_weekly_run", "static"):
        sent = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Missing or invalid CSRF token. Reload the page and try again.")
    if ep in PUBLIC_ENDPOINTS or is_reviewer():
        return None
    if request.method == "GET":
        if ep == "overview":
            return redirect(url_for("demo"))                   # the public front page is the sample demo
        return redirect(url_for("login", next=request.full_path.rstrip("?")))
    return redirect(url_for("login"))                         # a refused POST changes nothing


@app.after_request
def add_csrf_and_headers(resp):
    nonce = secrets.token_urlsafe(16)
    if resp.mimetype == "text/html" and not resp.direct_passthrough:
        html = resp.get_data(as_text=True)
        tag = f'<input type="hidden" name="csrf_token" value="{csrf_token()}">'
        html = re.sub(r"(<form\b[^>]*method=[\"']post[\"'][^>]*>)", lambda m: m.group(1) + tag, html, flags=re.I)
        html = html.replace("<script>", f'<script nonce="{nonce}">')     # only our own inline scripts may run
        resp.set_data(html)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    # Script: only same-origin files and the nonce-tagged inline blocks (no inline handlers, no eval, no third parties).
    # Style: inline style attributes are used by the templates, so 'unsafe-inline' is kept for styles only.
    resp.headers.setdefault("Content-Security-Policy", "; ".join([
        "default-src 'self'", f"script-src 'self' 'nonce-{nonce}'", "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:", "connect-src 'self'", "form-action 'self'", "frame-ancestors 'none'",
        "base-uri 'none'", "object-src 'none'"]))
    if app.config["SESSION_COOKIE_SECURE"]:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return resp


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # The client address comes from remote_addr, never from a raw X-Forwarded-For header (any client can send one,
        # so the limit could be bypassed by changing it per request). Behind a proxy set PROXY_HOPS so ProxyFix takes
        # the address that the trusted proxy appended.
        ip = request.remote_addr or "?"
        now = time.time()
        if len(_FAILS) > 10_000:                               # bound memory: forget addresses with no recent failure
            for k in [k for k, v in _FAILS.items() if not v or now - v[-1] >= 60]:
                del _FAILS[k]
        recent = [t for t in _FAILS.get(ip, []) if now - t < 60]
        if len(recent) >= 5:
            return render_template("login.html", error="Too many attempts. Wait a minute.", enabled=auth_enabled()), 429
        pw = os.environ.get("REVIEWER_PASSWORD", "")
        if pw and hmac.compare_digest(request.form.get("password", ""), pw):
            session.clear(); session["reviewer"] = True; session.permanent = True
            return redirect(safe_next(request.args.get("next")))
        _FAILS[ip] = recent + [now]
        return render_template("login.html", error="Wrong password.", enabled=auth_enabled()), 401
    return render_template("login.html", error=None, enabled=auth_enabled())


@app.post("/logout")
def logout():
    session.clear()
    return redirect("/")
SVC = Service()
SVC.seed()
SVC.run_weekly()          # the weekly loop also runs once at startup; it writes nothing (actions stay pending)
RESTORED = SVC.restore()  # replay journalled human decisions (approvals, edits, live questions, canonical explainers)
EXAMPLES = ["Why is brokerage charged on every order?", "What is the exit load of HDFC Small Cap Fund?",
            "Should I redeem my HDFC Small Cap Fund units?", "Do HDFC funds invest in cryptocurrency?"]


@app.template_filter("reply_html")
def reply_html(text):
    t = str(escape(text))
    t = re.sub(r"\[([^\]]*)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    return Markup(t.replace("\n", "<br>"))


@app.template_filter("plain")
def plain(text):
    return re.sub(r"\s*\(\[source\]\([^)]*\)\)", "", str(text))


@app.template_filter("md")
def md(text):
    t = str(escape(text))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(https?://[^\s)|]+)", r'<a href="\1" target="_blank" rel="noopener">\1</a>', t)
    return Markup(t.replace("\n", "<br>"))


@app.context_processor
def inject():
    pend = sum(1 for a in SVC.actions.values() if a["status"] == "pending")
    return {"cfg": config, "pending_actions": pend, "llm": config.USE_LLM, "reviewer": is_reviewer(), "auth_on": auth_enabled()}


def _need(tid):
    return (SVC.desk.tickets.get(tid) or abort(404)), SVC.meta[tid]


@app.get("/healthz")
def healthz():
    return {"ok": True}                                        # public: no operational numbers


DEMO_SNAPSHOT = config.BASE / "data" / "demo_snapshot.json"


@app.get("/demo")
def demo():
    """Public, read-only sample view. Reads ONLY the committed snapshot built by make_demo.py from synthetic questions and
    the bundled public-review replay; never the live service, journal, audit log or written files."""
    snap = json.loads(DEMO_SNAPSHOT.read_text(encoding="utf-8")) if DEMO_SNAPSHOT.exists() else None
    return render_template("demo.html", snap=snap)


# ---------------------------------------------------------------- response loop
def _bars(items, key, label, top=None):
    mx = max([key(i) for i in items] or [1]) or 1
    return [{"label": label(i), "n": key(i), "pct": round(100 * key(i) / mx, 1), "hot": bool(top and top(i))} for i in items]


@app.get("/")
def overview():
    run = SVC.latest_run()
    statuses = [SVC.meta[t]["status"] for t in SVC.order]
    reused = sum(1 for t in SVC.order if SVC.desk.tickets[t]["outputs"]["facts"].get("canonical"))
    themes = _bars(run["themes"], lambda t: t["count"], lambda t: t["label"], lambda t: t["is_top3"]) if run else []
    groups = [g for g in (run["question_groups"] if run else []) if g["key"] != "advice"][:8]
    topics = _bars(groups, lambda g: g["count"], lambda g: g["label"], lambda g: g["count"] >= config.RECURRING_QUESTION_MIN)
    trend = (run or {}).get("fee_trend", [])
    pts, W, H = [], 460, 130
    if trend:
        mx = max(t["mentions"] for t in trend) or 1
        for i, t in enumerate(trend):
            x = 28 + i * (W - 56) / max(len(trend) - 1, 1)
            pts.append({"x": round(x, 1), "y": round(H - 24 - (t["mentions"] / mx) * (H - 52), 1), "yn": round(H - 24 - (t["negative"] / mx) * (H - 52), 1), **t})
    return render_template("overview.html", run=run, themes=themes, topics=topics, pts=pts, W=W, H=H,
                           n_q=len(SVC.order), pending=statuses.count("pending"), approved=statuses.count("approved"),
                           reused=reused, canon=SVC.canonical, n_actions=sum(1 for a in SVC.actions.values() if a["status"] == "pending"))


@app.get("/queue")
def queue():
    rows = []
    for tid in SVC.order:
        t, m = SVC.desk.tickets[tid], SVC.meta[tid]
        rows.append({"tid": tid, "t": t, "m": m, "intent": SVC.intent_of(t)})
    counts = {s: sum(1 for r in rows if r["m"]["status"] == s) for s in ("pending", "approved", "rejected")}
    return render_template("queue.html", rows=rows, counts=counts, examples=EXAMPLES, msg=request.args.get("msg"))


@app.post("/submit")
def submit():
    msg = (request.form.get("message") or "").strip()
    if not msg:
        return redirect(url_for("queue"))
    tid = SVC.submit_question(msg)
    return redirect(url_for("ticket", tid=tid))


@app.get("/ticket/<tid>")
def ticket(tid):
    t, m = _need(tid)
    return render_template("ticket.html", t=t, m=m, intent=SVC.intent_of(t), will=SVC.will_write(tid),
                           left=config.MAX_REFINEMENTS - t["refinements_used"], msg=request.args.get("msg"),
                           ok=request.args.get("ok"), canon=SVC.canonical)


@app.post("/ticket/<tid>/refine")
def refine(tid):
    t, m = _need(tid)
    if m["status"] != "pending":
        abort(400, "ticket already decided")
    res = SVC.refine(tid, (request.form.get("instruction") or "")[:500])
    return redirect(url_for("ticket", tid=tid, msg=None if res.get("ok") else res.get("error")))


@app.post("/ticket/<tid>/edit")
def edit(tid):
    _need(tid)
    res = SVC.edit_draft(tid, (request.form.get("body") or "")[:1200])
    return redirect(url_for("ticket", tid=tid, msg=None if res["ok"] else res["error"], ok="Edit saved for this ticket only." if res["ok"] else None))


@app.post("/ticket/<tid>/redraft")
def redraft(tid):
    _need(tid)
    res = SVC.redraft_with_canonical(tid)
    return redirect(url_for("ticket", tid=tid, msg=None if res["ok"] else res["error"],
                            ok=("Re-drafted: the approved canonical explainer was reused." if res.get("canonical") else
                                "Re-drafted from the corpus (no approved canonical explainer applies).") if res["ok"] else None))


@app.post("/ticket/<tid>/decide")
def decide(tid):
    _need(tid)
    approve = request.form.get("decision") == "approve"
    res = SVC.decide_ticket(tid, approve)
    if not res["ok"] and res.get("status") == 403:
        abort(403, res["error"])
    return redirect(url_for("ticket", tid=tid, msg=None if res["ok"] else res["error"]))


# ---------------------------------------------------------------- weekly loop
@app.get("/weekly")
def weekly_view():
    run = SVC.latest_run()
    acts = [(a, SVC.action_payload(a["id"])) for a in SVC.actions.values() if run and a["run_id"] == run["run_id"]]
    return render_template("weekly.html", run=run, acts=acts, msg=request.args.get("msg"), source=SVC.reviews_source)


@app.post("/weekly/run")
def weekly_run():
    SVC.run_weekly()
    return redirect(url_for("weekly_view"))


@app.post("/weekly/upload")
def weekly_upload():
    f = request.files.get("reviews")
    if not f or not f.filename:
        return redirect(url_for("weekly_view", msg="Choose a CSV file first."))
    res = SVC.use_reviews(f.read(), f.filename)
    if not res["ok"]:
        return redirect(url_for("weekly_view", msg=res["error"]))
    SVC.run_weekly()
    return redirect(url_for("weekly_view"))


@app.post("/action/<path:aid>/decide")
def action_decide(aid):
    if aid not in SVC.actions:
        abort(404)
    res = SVC.decide_action(aid, request.form.get("decision") == "approve")
    return redirect(url_for("weekly_view", msg=None if res["ok"] else res["error"]))


@app.post("/api/preview")
def api_preview():
    """Intent preview for the question box (typed or spoken). Nothing is stored or logged: the text is redacted, scanned and dropped."""
    import pii as _pii
    from agents import ComplianceAgent
    from corpus import INTENT_LABEL, SCHEME_SPECIFIC, SCHEMES, detect_intents, detect_schemes, get_corpus
    raw = str((request.get_json(silent=True) or {}).get("text", ""))[:600]
    text, found = _pii.redact(raw)
    comp = ComplianceAgent().run(text)
    intents = detect_intents(text)
    schemes = detect_schemes(text)
    out = {"redacted_text": text, "pii": sorted({f["type"] for f in found}), "intents": [INTENT_LABEL.get(i, i) for i in intents],
           "advice": bool(comp.get("advice_requested")), "clarify": None, "kind": "", "message": ""}
    if out["advice"]:
        out.update(kind="advice", message="This asks for advice or returns. The desk will refuse that part and share only official facts.")
    elif [i for i in intents if i in SCHEME_SPECIFIC] and not schemes:
        out.update(kind="clarify", message="Which scheme do you mean? The answer differs by scheme.",
                   clarify=[SCHEMES[k] for k in SCHEMES if k != "general"])
    else:
        res = get_corpus().search(text)
        out.update(kind="answerable" if res["status"] == "covered" else "not_covered",
                   message="The official sources can answer this." if res["status"] == "covered" else
                   "The official sources do not cover this; it will be routed to a team.")
    if out["pii"]:
        out["message"] = "Personal details (" + ", ".join(out["pii"]) + ") will be removed before anything is stored. " + out["message"]
    return jsonify(out)


@app.post("/api/weekly/run")
def api_weekly_run():
    # Machine trigger (GitHub Actions / n8n). It is exempt from CSRF and login, so it is OFF unless a token is configured;
    # previously an unset WEEKLY_TOKEN left it open to anyone. Constant-time comparison.
    tok = os.environ.get("WEEKLY_TOKEN", "")
    if not tok:
        abort(403, "The weekly trigger API is disabled: set WEEKLY_TOKEN on the server to enable it.")
    if not hmac.compare_digest(request.headers.get("X-Token", ""), tok):
        abort(401)
    run = SVC.run_weekly()
    return jsonify({"run_id": run["run_id"], "window": run["window"], "pulse_words": run["pulse_words"],
                    "checks_passed": all(c[1] for c in run["checks"]), "pending_actions": run["action_ids"]})


# ---------------------------------------------------------------- panels
@app.get("/approvals")
def approvals():
    pend_t = [(SVC.meta[tid]["q_id"], tid) for tid in SVC.order if SVC.meta[tid]["status"] == "pending"]
    acts = [(a, SVC.action_payload(a["id"])) for a in SVC.actions.values()]
    audit = []
    p = config.OUT / "audit_log.jsonl"
    if p.exists():
        audit = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()][-15:]
    return render_template("approvals.html", acts=acts, pend_t=len(pend_t), audit=audit)


@app.get("/sources")
def sources():
    cites, claims = {}, []
    for tid in SVC.order:
        t, m = SVC.desk.tickets[tid], SVC.meta[tid]
        u = t["draft"]["reply"]["citation_url"]
        if u:
            cites[u] = cites.get(u, 0) + 1
            fact = next((s["text"] for s in t["draft"]["reply"]["sentences"] if "](" in s["text"]), "")
            claims.append({"q": m["q_id"], "claim": re.sub(r"\s*\(\[source\]\([^)]*\)\)", "", fact), "url": u,
                           "checked": t["draft"]["reply"]["last_checked"], "canon": bool(t["outputs"]["facts"].get("canonical"))})
    run = SVC.latest_run()
    ex = {}
    for rec in SVC.canonical.values():
        for b in rec["bullets"]:
            ex[b["source_url"]] = ex.get(b["source_url"], 0) + 1
    srcs = [{"url": u, "checked": config.last_checked_for(u), "replies": cites.get(u, 0), "bullets": ex.get(u, 0)}
            for u in sorted(corpus.ALLOWED_URLS)]
    return render_template("sources.html", srcs=srcs, claims=claims[:80], run=run, review_end=SVC.window_end)


@app.get("/canonical")
def canonical():
    used = {}
    for tid in SVC.order:
        f = SVC.desk.tickets[tid]["outputs"]["facts"]
        if f.get("canonical"):
            used.setdefault(f["canonical"]["fee"], []).append((SVC.meta[tid]["q_id"], tid, f["canonical"]["bullet_index"]))
    return render_template("canonical.html", canon=SVC.canonical, used=used)


@app.get("/evals")
def evals():
    d = config.BASE / "outputs" / "evals"
    summary = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else None
    docs = {n: (d / n).read_text(encoding="utf-8") for n in ("feasibility.md", "edit_correctness.md", "grounding_compliance.md", "regressions.md", "golden.md", "mcp_server.md", "persistence.md", "approval_security.md", "privacy_pathways.md", "requirements.md") if (d / n).exists()}
    return render_template("evals.html", summary=summary, docs=docs)


@app.get("/saved")
def saved():
    def read(n):
        p = config.OUT / n
        return p.read_text(encoding="utf-8") if p.exists() else "(nothing written yet: approve an action first)"
    return render_template("saved.html", files=[(n, read(n)) for n in
                           ("weekly_log.md", "weekly_pulse_draft.txt", "support_log.md", "support_reply_draft.txt")])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
