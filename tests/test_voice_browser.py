"""Real browser-engine tests of the voice UI with a MOCKED speech recogniser.

What this proves: the page's states, consent gate, error handling, transcript confirmation and redaction path behave.
What it does NOT prove: that a real microphone, the browser's speech service, or a real transcript works. That needs a
person in Chrome or Edge over HTTPS (see docs/ui-guide.md, 'Manual microphone check'). Skipped if Playwright is missing.
"""
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["DESK_OUT"], os.environ["DESK_LOGS"] = _TMP + "/out", _TMP + "/logs"
os.environ.pop("REVIEWER_PASSWORD", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                       # pragma: no cover
    sync_playwright = None

PAN = "ABCDE" + "1234F"


def mock(script_events: str) -> str:
    return """window.SpeechRecognition = window.webkitSpeechRecognition = function(){
      this.start = () => { setTimeout(() => { %s }, 40) }; this.stop = () => {}; };""" % script_events


@unittest.skipIf(sync_playwright is None, "playwright not installed")
class VoiceUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as A
        from werkzeug.serving import make_server
        cls.A = A
        cls.srv = make_server("127.0.0.1", 5071, A.app, threaded=True)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        cls.br = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.br.close(); cls.pw.stop(); cls.srv.shutdown()

    def page(self, init=None):
        p = self.br.new_page()
        if init:
            p.add_init_script(init)
        p.goto("http://127.0.0.1:5071/queue")
        return p

    def test_unsupported_browser_falls_back_to_typing(self):
        p = self.page("delete window.SpeechRecognition; delete window.webkitSpeechRecognition;")
        self.assertEqual(p.get_attribute("#voice-state", "data-state"), "unsupported")
        self.assertFalse(p.is_visible("#mic"))
        p.fill("#message", "What is the exit load of HDFC Small Cap Fund?")
        self.assertTrue(p.is_enabled("button[type=submit]"))

    def test_consent_is_required_and_declining_falls_back(self):
        p = self.page(mock("this.onstart&&this.onstart();"))
        p.click("#mic")
        self.assertTrue(p.is_visible("#consent"))
        self.assertIn("Google", p.inner_text("#consent"))              # discloses that the browser may send audio to a cloud service
        p.click("#consent-no")
        self.assertEqual(p.get_attribute("#voice-state", "data-state"), "typed")

    def test_permission_denied_shows_a_clear_error_and_asks_again(self):
        p = self.page(mock("this.onerror&&this.onerror({error:'not-allowed'}); this.onend&&this.onend();"))
        p.click("#mic"); p.click("#consent-yes"); p.wait_for_timeout(300)
        self.assertEqual(p.get_attribute("#voice-state", "data-state"), "error")
        self.assertIn("permission", p.inner_text("#voice-state").lower())
        p.click("#mic")
        self.assertTrue(p.is_visible("#consent"))                       # consent is asked again after a denial

    def test_network_and_no_speech_errors(self):
        for err, word in (("network", "network"), ("no-speech", "hear")):
            p = self.page(mock("this.onerror&&this.onerror({error:'%s'}); this.onend&&this.onend();" % err))
            p.click("#mic"); p.click("#consent-yes"); p.wait_for_timeout(300)
            self.assertEqual(p.get_attribute("#voice-state", "data-state"), "error")
            self.assertIn(word, p.inner_text("#voice-state").lower())

    def test_states_then_transcript_review_and_redaction(self):
        ev = ("this.onstart&&this.onstart(); setTimeout(()=>{this.onaudioend&&this.onaudioend();},60);"
              "setTimeout(()=>{this.onresult({results:[Object.assign([{transcript:'my pan is %s what is the exit load of HDFC Small Cap Fund',confidence:0.9}],{isFinal:true})]});this.onend&&this.onend();},160);" % PAN)
        p = self.page(mock(ev))
        seen = []
        p.click("#mic"); p.click("#consent-yes")
        for _ in range(12):
            seen.append(p.get_attribute("#voice-state", "data-state")); p.wait_for_timeout(40)
        self.assertIn("listening", seen); self.assertIn("processing", seen)
        p.wait_for_timeout(300)
        self.assertEqual(p.get_attribute("#voice-state", "data-state"), "success")
        self.assertEqual(p.input_value("#message"), "")                 # nothing is placed in the box until the person confirms
        p.click("#use"); p.wait_for_timeout(700)
        self.assertIn("personal details", p.inner_text("#preview").lower())      # preview warns that PAN will be removed
        p.fill("#message", p.input_value("#message") + " please")      # the person can correct the transcript
        n0 = len(self.A.SVC.order)
        p.click("button[type=submit]"); p.wait_for_load_state()
        self.assertEqual(len(self.A.SVC.order), n0 + 1)
        t = self.A.SVC.desk.tickets[self.A.SVC.order[-1]]
        self.assertNotIn(PAN, json.dumps(t, default=str))
        for f in Path(os.environ["DESK_LOGS"]).rglob("*"):
            if f.is_file():
                self.assertNotIn(PAN, f.read_bytes().decode("utf-8", "ignore"))

    def test_language_selector_offers_english_hindi_kannada(self):
        p = self.page(mock("this.onstart&&this.onstart();"))
        vals = p.eval_on_selector_all("#lang option", "els=>els.map(e=>e.value)")
        for v in ("en-IN", "hi-IN", "kn-IN"):
            self.assertIn(v, vals)

    def test_read_aloud_button_present_when_speech_synthesis_exists(self):
        p = self.br.new_page()
        p.goto("http://127.0.0.1:5071/ticket/" + self.A.SVC.order[0])
        self.assertTrue(p.is_visible("#speak"))


if __name__ == "__main__":
    unittest.main()
