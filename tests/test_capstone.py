import os
import sys
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["DESK_OUT"] = _TMP + "/out"
os.environ["DESK_LOGS"] = _TMP + "/logs"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config            # noqa: E402
import mcp_layer as mcp  # noqa: E402
import pii               # noqa: E402
import weekly            # noqa: E402
from service import Service  # noqa: E402

SVC = Service()
SVC.seed()


class Capstone(unittest.TestCase):
    def test_pii_redaction(self):
        pan, ph = "ABCDE" + "1234F", "98765" + "43210"
        out, found = pii.redact(f"pan {pan} phone {ph}")
        self.assertFalse(pii.detect(out))
        self.assertEqual({f["type"] for f in found}, {"PAN", "PHONE"})

    def test_weekly_caps_and_ids(self):
        run = weekly.build(config.REVIEWS_CSV, [])
        self.assertLessEqual(run["pulse_words"], 250)
        self.assertLessEqual(len(run["explainer"]["bullets"]), 6)
        self.assertLessEqual(len(run["themes"]), 5)
        self.assertTrue(all(t["review_ids"] for t in run["themes"]))
        self.assertTrue(all(c[1] for c in run["checks"]))

    def test_gate_blocks_writes(self):
        tid = SVC.order[0]
        with self.assertRaises(mcp.ApprovalRequired):
            mcp.call_tool("append_support_record", {}, SVC.meta[tid]["gate"])

    def test_link_between_loops(self):
        run = SVC.run_weekly()
        self.assertTrue(any(s["count"] >= 5 for s in run["signals"]))
        tid = SVC.submit_question("Why is brokerage charged on my order?")
        self.assertFalse(SVC.desk.tickets[tid]["outputs"]["facts"].get("canonical"))
        SVC.decide_action(run["action_ids"][0], True)
        tid = SVC.submit_question("Why is brokerage charged on my order?")
        self.assertTrue(SVC.desk.tickets[tid]["outputs"]["facts"].get("canonical"))

    def test_advice_refused(self):
        t = SVC.desk.tickets[SVC.submit_question("Should I redeem my HDFC Small Cap Fund units?")]
        self.assertTrue(t["outputs"]["compliance"]["advice_requested"])
        self.assertIn("can't advise", t["draft"]["reply"]["body"])


class AccessControl(unittest.TestCase):
    def setUp(self):
        os.environ["REVIEWER_PASSWORD"] = "pw-test"
        import app as A
        self.A, self.c = A, A.app.test_client()

    def tearDown(self):
        os.environ.pop("REVIEWER_PASSWORD", None)

    def _tok(self):
        # the token comes from /login: since the access change (26 Nov 2026) an anonymous visitor cannot open /queue
        import re
        return re.search(r'name="csrf_token" value="([^"]+)"', self.c.get("/login").get_data(as_text=True)).group(1)

    PROTECTED = ["/queue", "/weekly", "/approvals", "/canonical", "/sources", "/saved"]

    def test_anonymous_visitor_sees_only_the_public_demo(self):
        tid = self.A.SVC.order[0]
        for path in self.PROTECTED + [f"/ticket/{tid}"]:
            r = self.c.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/login", r.headers["Location"], path)
        r = self.c.get("/")
        self.assertEqual((r.status_code, r.headers["Location"].endswith("/demo")), (302, True))
        demo = self.c.get("/demo").get_data(as_text=True)
        self.assertIn("Sample data", demo)
        for live in [self.A.SVC.order[0], "Audit log (what was actually written)", "audit_log", "receipt_id",
                     'action="/ticket', 'action="/action', 'action="/submit', "Approve"]:
            self.assertNotIn(live, demo)                       # no live ticket id, audit content or approval control
        for path in ("/demo", "/evals", "/login", "/healthz"):
            self.assertEqual(self.c.get(path).status_code, 200, path)
        self.assertEqual(self.c.get("/healthz").get_json(), {"ok": True})   # no operational numbers

    def test_anonymous_cannot_submit_or_preview(self):
        n = len(self.A.SVC.order)
        tok = self._tok()
        r = self.c.post("/submit", data={"message": "What is the exit load of HDFC Small Cap Fund?", "csrf_token": tok})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(self.A.SVC.order), n)             # the live queue did not change
        r = self.c.post("/api/preview", json={"text": "exit load small cap"}, headers={"X-CSRF-Token": tok})
        self.assertEqual(r.status_code, 302)

    def test_without_a_password_nobody_is_a_reviewer(self):
        tok = self._tok()                                      # taken while a login form still exists
        os.environ.pop("REVIEWER_PASSWORD")                    # fail closed: there is no open demo mode any more
        self.assertEqual(self.c.get("/queue").status_code, 302)
        r = self.c.post("/login", data={"password": "", "csrf_token": tok})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.c.get("/queue").status_code, 302)
        self.assertIn("not configured", self.c.get("/login").get_data(as_text=True))

    def test_login_limit_cannot_be_bypassed_with_x_forwarded_for(self):
        self.A._FAILS.clear()
        tok = self._tok()
        codes = [self.c.post("/login", data={"password": "bad", "csrf_token": tok},
                             headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(7)]
        self.A._FAILS.clear()
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5:], [429, 429])               # a new spoofed address per request does not reset the limit

    def test_csp_allows_only_our_nonce_tagged_scripts(self):
        import re
        tok = self._tok()
        self.c.post("/login", data={"password": "pw-test", "csrf_token": tok})
        for path in ("/queue", f"/ticket/{self.A.SVC.order[0]}", "/demo"):
            r = self.c.get(path)
            csp = r.headers["Content-Security-Policy"]
            self.assertIn("frame-ancestors 'none'", csp)
            self.assertNotIn("'unsafe-inline'", csp.split("script-src")[1].split(";")[0])
            nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
            html = r.get_data(as_text=True)
            self.assertEqual(html.count("<script"), html.count(f'<script nonce="{nonce}">'), path)

    def test_docker_build_context_excludes_secrets_and_runtime_state(self):
        ign = (Path(__file__).resolve().parent.parent / ".dockerignore").read_text(encoding="utf-8").split()
        for must in ("outputs/.approval_key", "outputs/receipts", "outputs/audit_log.jsonl", "data_state", "*.db", ".env", "logs"):
            self.assertIn(must, ign)

    def test_login_redirect_stays_on_this_site(self):
        for bad in ("//evil.example", "/\\evil.example", "https://evil.example", "javascript:alert(1)"):
            self.assertEqual(self.A.safe_next(bad), "/")
        self.assertEqual(self.A.safe_next("/ticket/ab12"), "/ticket/ab12")

    def test_post_needs_csrf_and_login(self):
        tid = next(t for t in self.A.SVC.order if self.A.SVC.meta[t]["status"] == "pending")
        self.assertEqual(self.c.post(f"/ticket/{tid}/decide", data={"decision": "approve"}).status_code, 400)
        r = self.c.post(f"/ticket/{tid}/decide", data={"decision": "approve", "csrf_token": self._tok()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.A.SVC.meta[tid]["status"], "pending")            # not logged in: nothing happened
        self.assertEqual(self.c.post("/login", data={"password": "bad", "csrf_token": self._tok()}).status_code, 401)
        self.c.post("/login", data={"password": "pw-test", "csrf_token": self._tok()})
        self.c.post(f"/ticket/{tid}/decide", data={"decision": "approve", "csrf_token": self._tok()})
        self.assertEqual(self.A.SVC.meta[tid]["status"], "approved")


class Regressions(unittest.TestCase):
    """Defects found in the Claude Code audit (26 Nov 2026). Each test failed before its fix."""

    def test_journal_closes_its_sqlite_connections(self):
        # D1: `with sqlite3.connect()` only commits; the handle stayed open, so on Windows state.db could not be
        # moved (the eval harness crashed) and every call leaked a connection (ResourceWarning: unclosed database).
        import gc
        import warnings
        from service import Journal
        db = Path(tempfile.mkdtemp()) / "j.db"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            j = Journal(str(db))
            j.add("submit", q_id="Q-T", text="hello")
            self.assertEqual(j.events(), [("submit", {"q_id": "Q-T", "text": "hello"})])
            del j
            gc.collect()
        self.assertFalse([x for x in w if issubclass(x.category, ResourceWarning) and "sqlite" in str(x.message).lower()
                          or "unclosed database" in str(x.message)])
        moved = db.with_suffix(".moved")
        db.rename(moved)                                   # raises PermissionError on Windows if a handle is still open
        self.assertTrue(moved.exists())

    def test_concurrent_receipt_use_has_one_winner_and_clean_refusals(self):
        # Receipt race: losers used to crash with a raw PermissionError (Windows: rename while another thread reads)
        # or FileNotFoundError (any OS: exists() then read_text() after a concurrent consume). Single use must hold AND
        # every loser must get ApprovalRequired, never an unhandled OS error.
        import threading
        args = {"subject": "s", "body": "b"}
        for _ in range(30):
            g = mcp.ApprovalGate("t"); g.decide(True)
            rid = mcp.issue_receipt(g, "create_email_draft", args)
            ok, refused, other = [], [], []
            start = threading.Barrier(8)

            def use():
                start.wait()
                try:
                    ok.append(mcp.verify_and_consume_receipt(rid, "create_email_draft", args))
                except mcp.ApprovalRequired:
                    refused.append(1)
                except Exception as e:                     # noqa: BLE001
                    other.append(repr(e))
            ts = [threading.Thread(target=use) for _ in range(8)]
            [t.start() for t in ts]; [t.join() for t in ts]
            self.assertEqual(other, [])
            self.assertEqual((len(ok), len(refused)), (1, 7))


class ApprovalIntegrity(unittest.TestCase):
    """D2 (a re-run reopened approved actions), D4 (decisions were not atomic with their writes), open weekly API."""

    @classmethod
    def setUpClass(cls):
        cls.s = Service(); cls.s.seed()

    def _entries(self, run_id):
        p = config.OUT / "weekly_log.md"
        return p.read_text(encoding="utf-8").count(f"(run {run_id},") if p.exists() else 0

    def test_rerun_never_reopens_an_approved_action(self):
        s = self.s
        run = s.run_weekly(); doc, email = run["action_ids"]
        self.assertTrue(s.decide_action(doc, True)["ok"])
        fee = run["explainer"]["fee"]; v = s.canonical[fee]["version"]
        gate = s.actions[email]["gate"]
        n = self._entries(run["run_id"])                       # other tests share the output folder: measure the change
        self.assertGreaterEqual(n, 1)
        run2 = s.run_weekly()                                   # identical content
        self.assertEqual(run2["run_id"], run["run_id"])
        self.assertEqual(run2["action_ids"], [doc, email])      # same actions, not fresh ones
        self.assertEqual(s.actions[doc]["status"], "approved")
        self.assertIs(s.actions[email]["gate"], gate)           # the pending one keeps its gate
        self.assertFalse(s.decide_action(doc, True)["ok"])
        self.assertEqual(self._entries(run["run_id"]), n)       # no duplicate doc entry from the re-run
        self.assertEqual(s.canonical[fee]["version"], v)        # no spurious version bump

    def test_rejected_action_is_reoffered_under_a_new_id_and_history_is_kept(self):
        s = self.s
        run = s.run_weekly(); email = run["action_ids"][1]
        self.assertTrue(s.decide_action(email, False)["ok"])
        run2 = s.run_weekly()
        e2 = run2["action_ids"][1]
        self.assertNotEqual(e2, email)
        self.assertEqual(s.actions[email]["status"], "rejected")   # the decision is not overwritten
        self.assertEqual(s.actions[e2]["status"], "pending")

    def test_failed_ticket_write_stays_pending_and_retry_does_not_duplicate(self):
        s = self.s
        tid = next(t for t in s.order if s.meta[t]["status"] == "pending" and not s.desk.tickets[t]["send_blocked"])
        real, calls = mcp._IMPL["create_email_draft"], []

        def flaky(a):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("disk full")
            return real(a)
        mcp._IMPL["create_email_draft"] = flaky
        try:
            rows0 = len(s.journal.events())
            res = s.decide_ticket(tid, True)
            self.assertFalse(res["ok"])
            self.assertEqual(s.meta[tid]["status"], "pending")
            self.assertEqual(s.meta[tid]["gate"].status, "pending")
            self.assertEqual(len(s.journal.events()), rows0)          # nothing journalled for a failed decision
            self.assertTrue(s.decide_ticket(tid, True)["ok"])         # retry
        finally:
            mcp._IMPL["create_email_draft"] = real
        self.assertEqual(s.meta[tid]["status"], "approved")
        log = (config.OUT / "support_log.md").read_text(encoding="utf-8")
        self.assertEqual(log.count(f"## Ticket {s.meta[tid]['q_id']}/{tid} "), 1)   # record written once, not twice

    def test_failed_weekly_write_stays_pending_without_canonical(self):
        s = Service(); s.seed()
        run = s.run_weekly(); doc = run["action_ids"][0]
        real = mcp._IMPL["append_weekly_record"]
        mcp._IMPL["append_weekly_record"] = lambda a: (_ for _ in ()).throw(OSError("disk full"))
        try:
            self.assertFalse(s.decide_action(doc, True)["ok"])
        finally:
            mcp._IMPL["append_weekly_record"] = real
        self.assertEqual(s.actions[doc]["status"], "pending")
        self.assertEqual(s.canonical, {})
        self.assertTrue(s.decide_action(doc, True)["ok"])
        self.assertEqual(s.canonical[run["explainer"]["fee"]]["version"], 1)


class Persistence(unittest.TestCase):
    """D5: refinements and re-drafts were not journalled; replayed edits were silently dropped after the stale date."""

    def setUp(self):
        os.environ["DESK_DB"] = str(Path(tempfile.mkdtemp()) / "p.db")

    def tearDown(self):
        os.environ.pop("DESK_DB", None)
        os.environ.pop("TODAY_OVERRIDE", None)

    @staticmethod
    def _restarted():
        b = Service(); b.seed(); b.run_weekly(); b.restore()
        return b

    @staticmethod
    def _by_q(s, q):
        return next(t for t in s.order if s.meta[t]["q_id"] == q)

    def test_refinement_survives_a_restart(self):
        a = Service(); a.seed()
        tid = self._by_q(a, "Q-004")
        self.assertTrue(a.refine(tid, "make it shorter")["ok"])
        b = self._restarted()
        tb = b.desk.tickets[self._by_q(b, "Q-004")]
        self.assertEqual(tb["refinements_used"], 1)
        self.assertEqual(tb["draft"]["reply"]["full_text"], a.desk.tickets[tid]["draft"]["reply"]["full_text"])

    def test_redraft_then_edit_survive_a_restart(self):
        a = Service(); a.seed(); run = a.run_weekly()
        a.decide_action(run["action_ids"][0], True)                  # canonical explainer approved
        tid = self._by_q(a, "Q-020")
        self.assertTrue(a.redraft_with_canonical(tid)["canonical"])
        body = a.desk.tickets[tid]["draft"]["reply"]["body"].replace(
            "If this doesn't resolve your concern, reply here and our team will take a look.", "").strip()
        self.assertTrue(a.edit_draft(tid, body)["ok"])
        b = self._restarted()
        tb = b.desk.tickets[self._by_q(b, "Q-020")]
        self.assertTrue(tb["outputs"]["facts"].get("canonical"))     # the re-draft was replayed first ...
        self.assertEqual(tb["draft"]["reply"]["body"], body)         # ... so the edit (canonical citation) restores

    def test_edit_restored_after_stale_date_keeps_wording_and_stays_blocked(self):
        a = Service(); a.seed()
        tid = self._by_q(a, "Q-005")                                  # minimum SIP: a time-sensitive fact
        body = a.desk.tickets[tid]["draft"]["reply"]["body"].replace(
            "If this doesn't resolve your concern, reply here and our team will take a look.", "").strip()
        self.assertTrue(a.edit_draft(tid, body)["ok"])
        os.environ["TODAY_OVERRIDE"] = "2027-03-01"                   # > 60 days after the 26 Nov 2026 check
        b = self._restarted()
        tb, mb = b.desk.tickets[self._by_q(b, "Q-005")], b.meta[self._by_q(b, "Q-005")]
        self.assertEqual(tb["draft"]["reply"]["body"], body)          # the human's wording is not lost
        self.assertTrue(mb["edited"])
        self.assertTrue(tb["send_blocked"])                           # but it cannot be approved while stale
        self.assertIn("STALE_FACT", [f["code"] for f in tb["review"]["failures"]])
        self.assertEqual(b.decide_ticket(self._by_q(b, "Q-005"), True).get("status"), 403)

    def test_live_edit_of_a_stale_fact_is_still_refused(self):
        os.environ["TODAY_OVERRIDE"] = "2027-03-01"
        a = Service(); a.seed()
        tid = self._by_q(a, "Q-005")
        res = a.edit_draft(tid, a.desk.tickets[tid]["draft"]["reply"]["body"])
        self.assertFalse(res["ok"])                                   # the replay exception never applies to live edits


class SourceVerification(unittest.TestCase):
    """D3/D9: warnings wherever verification is overdue or unconfirmed; dates are never invented or changed."""
    SC = Path(__file__).resolve().parent.parent / "data" / "source_checks.json"
    HDFC_SMALL = "https://www.hdfcfund.com/product-solutions/overview/hdfc-small-cap-fund/direct"
    KYC = "https://www.hdfcfund.com/investor-services/kyc"

    def tearDown(self):
        os.environ.pop("TODAY_OVERRIDE", None)

    def test_statuses_follow_recorded_dates_scope_and_the_unchanged_60_day_interval(self):
        import datetime as dt
        import verification as v
        self.assertEqual(config.TIME_SENSITIVE_MAX_DAYS, 60)
        d = dt.date
        self.assertEqual(v.source_status(self.KYC, d(2026, 11, 26))["status"], "ok")          # checked 22 Oct, 35 days
        self.assertEqual(v.source_status(self.KYC, d(2026, 12, 10))["status"], "due_soon")    # 49 days
        self.assertEqual(v.source_status(self.KYC, d(2026, 12, 22))["status"], "overdue")     # 61 days
        self.assertEqual(v.source_status("https://example.org/never-checked")["status"], "unconfirmed")
        today = d(2026, 11, 26)
        self.assertEqual(v.fact_status(self.HDFC_SMALL, ["min_sip"], today)["status"], "ok")      # a checked field
        self.assertEqual(v.fact_status(self.HDFC_SMALL, ["benchmark"], today)["status"], "unconfirmed")
        self.assertEqual(v.fact_status(self.HDFC_SMALL, ["min_sip"], d(2027, 2, 1))["status"], "overdue")

    def test_warnings_appear_where_facts_are_shown_and_no_date_is_changed(self):
        import hashlib
        import re
        h0 = hashlib.sha256(self.SC.read_bytes()).hexdigest()
        os.environ["REVIEWER_PASSWORD"] = "pw-test"
        import app as A
        c = A.app.test_client()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', c.get("/login").get_data(as_text=True)).group(1)
        c.post("/login", data={"password": "pw-test", "csrf_token": tok})
        by_q = {A.SVC.meta[t]["q_id"]: t for t in A.SVC.order}
        bench = c.get(f"/ticket/{by_q['Q-014']}").get_data(as_text=True)            # benchmark: outside the checked fields
        self.assertIn("Source verification unconfirmed", bench)
        self.assertNotIn("Source verification", c.get(f"/ticket/{by_q['Q-005']}").get_data(as_text=True).split("Reply draft")[1].split("Internal routing")[0])
        self.assertIn("need manual verification (5)", c.get("/sources").get_data(as_text=True))
        self.assertIn("Source verification:</b>", c.get("/queue").get_data(as_text=True))   # global reviewer banner
        os.environ["TODAY_OVERRIDE"] = "2027-02-01"                                    # every recorded check > 60 days old
        self.assertIn("need manual verification (20)", c.get("/sources").get_data(as_text=True))
        demo = A.app.test_client().get("/demo").get_data(as_text=True)                 # public page warns too
        self.assertIn("verification overdue", demo)
        self.assertIn("need manual verification (20)", demo)
        os.environ.pop("REVIEWER_PASSWORD")
        self.assertEqual(hashlib.sha256(self.SC.read_bytes()).hexdigest(), h0)          # reporting never edits dates

    def test_dp_explainer_cites_the_page_checked_for_the_per_order_claim(self):
        exp = weekly.build_explainer({"fee": "DP / depository charges on selling"})
        b2 = exp["bullets"][1]
        self.assertIn("per sell order", b2["text"])
        self.assertEqual(b2["source_url"], "https://groww.in/help/stocks/searchable/are-dp-charges-per-stock-or-per-order")
        self.assertEqual(exp["last_checked"], "26 Nov 2026")                           # no longer the 22 Oct home page


class DeploymentConfig(unittest.TestCase):
    """D6: weekly.yml did not parse (an unquoted ': ' in a run line) and used `secrets` in a step `if:`."""
    ROOT = Path(__file__).resolve().parent.parent

    def test_workflows_and_deploy_files_parse_and_never_test_secrets_in_if(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("pyyaml not installed (pip install -r requirements-dev.txt)")
        files = sorted((self.ROOT / ".github" / "workflows").glob("*.yml")) + [self.ROOT / "render.yaml", self.ROOT / "docker-compose.yml"]
        for f in files:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
            self.assertIsInstance(doc, dict, f.name)
            for job in (doc.get("jobs") or {}).values():
                for step in job.get("steps", []):
                    self.assertNotIn("secrets.", str(step.get("if", "")), f"{f.name}: secrets context is not allowed in a step if:")

    def test_render_free_plan_states_that_state_is_lost(self):
        txt = (self.ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("plan: free", txt)
        self.assertIn("lost on every redeploy", txt)


class WeeklyApi(unittest.TestCase):
    def setUp(self):
        import app as A
        self.A, self.c = A, A.app.test_client()

    def tearDown(self):
        os.environ.pop("WEEKLY_TOKEN", None)

    def test_disabled_without_a_configured_token(self):
        os.environ.pop("WEEKLY_TOKEN", None)
        self.assertEqual(self.c.post("/api/weekly/run").status_code, 403)

    def test_requires_the_right_token(self):
        os.environ["WEEKLY_TOKEN"] = "tok-123"
        self.assertEqual(self.c.post("/api/weekly/run").status_code, 401)
        self.assertEqual(self.c.post("/api/weekly/run", headers={"X-Token": "wrong"}).status_code, 401)
        self.assertEqual(self.c.post("/api/weekly/run", headers={"X-Token": "tok-123"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
