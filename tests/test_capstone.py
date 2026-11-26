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
