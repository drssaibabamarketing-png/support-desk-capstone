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


if __name__ == "__main__":
    unittest.main()
