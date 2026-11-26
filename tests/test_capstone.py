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
        import re
        return re.search(r'name="csrf_token" value="([^"]+)"', self.c.get("/queue").get_data(as_text=True)).group(1)

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


if __name__ == "__main__":
    unittest.main()
