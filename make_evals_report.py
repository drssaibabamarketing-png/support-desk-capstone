"""Builds EVALS_REPORT.md: golden dataset, adversarial tests and scores, from the saved eval run + a fresh seeded queue."""
import csv, json, os, tempfile
os.environ.setdefault("DESK_OUT", tempfile.mkdtemp()); os.environ.setdefault("DESK_LOGS", tempfile.mkdtemp())
import service

S = service.Service(); S.seed()
sm = json.load(open("outputs/evals/summary.json"))
reg = open("outputs/evals/regressions.md").read().split("| Check | Result | Detail |")[1]
mcp_rows = [l for l in open('outputs/evals/mcp_server.md').read().split('| Check | Result | Detail |')[1].splitlines() if l.startswith('| ') and '---' not in l]
pers_rows = [l for l in open('outputs/evals/persistence.md').read().split('| Check | Result | Detail |')[1].splitlines() if l.startswith('| ') and '---' not in l]
def _rows(n):
    return [l for l in open(f'outputs/evals/{n}.md').read().split('| Check | Result | Detail |')[1].splitlines() if l.startswith('| ') and '---' not in l]
appr_rows, priv_rows, req_rows = _rows('approval_security'), _rows('privacy_pathways'), _rows('requirements')
reg_rows = [l for l in reg.splitlines() if l.startswith("| ") and "---" not in l]
tot = sum(v["total"] for v in sm.values()); ok = sum(v["passed"] for v in sm.values())
import csv as _c
GOLD = {r['q_id']: r for r in _c.DictReader(open('data/golden.csv', encoding='utf-8'))}
rows = []
for tid in S.order:
    m, t = S.meta[tid], S.desk.tickets[tid]
    o = t["outputs"]; q = next(r for r in csv.DictReader(open("data/questions.csv")) if r["q_id"] == m["q_id"])["text"]
    f = o["facts"]
    adv_req = o["compliance"].get("advice_requested")
    out = ("refused (advice)" + (" + cited fact" if f["status"] == "covered" else "")) if adv_req else ("cited fact" if f["status"] == "covered" else "not covered, routed")
    gl = GOLD[m["q_id"]]
    st = "refused" if adv_req else ("answered" if f["status"] == "covered" else "not_covered")
    match = "match" if st == gl["expected_status"] and (not gl["expected_source_contains"] or gl["expected_source_contains"] in (f.get("citation_url") or "")) else "MISMATCH"
    if f.get("canonical"): out += " (canonical)"
    rv = "flagged" if t.get("flagged") or t.get("review", {}).get("flagged") else "pass"
    rows.append(f"| {m['q_id']} | {q.replace('|','/')} | {gl['expected_status']} {gl['expected_source_contains']} | {out} | {match} |")
adv = open("outputs/evals/grounding_compliance.md").read().split("| Check | Result | Detail |")[1]
adv_rows = [l for l in adv.splitlines() if l.startswith("| ") and "claim:" not in l and "---" not in l]
md = f"""# Evals Report: The Support Desk

**Overall: {ok}/{tot} checks pass** (Feasibility {sm['feasibility']['passed']}/{sm['feasibility']['total']} · Regressions {sm['regressions']['passed']}/{sm['regressions']['total']} · Golden {sm['golden']['passed']}/{sm['golden']['total']} · MCP {sm['mcp_server']['passed']}/{sm['mcp_server']['total']} · Persistence {sm['persistence']['passed']}/{sm['persistence']['total']} · Edit correctness {sm['edit_correctness']['passed']}/{sm['edit_correctness']['total']} · Grounding & compliance {sm['grounding_compliance']['passed']}/{sm['grounding_compliance']['total']} · Approval security {sm['approval_security']['passed']}/{sm['approval_security']['total']} · Privacy pathways {sm['privacy_pathways']['passed']}/{sm['privacy_pathways']['total']} · Assignment requirements {sm['requirements']['passed']}/{sm['requirements']['total']}). Reproduce: `python -m evals.run_evals` (the MCP eval starts local subprocesses and a local HTTP server; the voice browser tests are separate: `python -m unittest tests.test_voice_browser`, mocked recogniser). Full tables: `outputs/evals/*.md`.

## 1. Golden dataset
38 queued questions in `data/questions.csv` (synthetic, written for this demo; they mirror the review themes and the fee confusion), plus the 366-review weekly window in `data/reviews.csv`. Expected labels are hand-written in `data/golden.csv` (status: answered / refused / not covered, plus the page the answer should cite); the table compares them with what the system did. The labels were written by the system's author, so skim them.

| ID | Question | Expected (hand label) | System outcome | vs label |
|---|---|---|---|---|
{chr(10).join(rows)}

Weekly golden checks (recounted from the CSV): 21 brokerage/trade-charge reviews (16 rated 1-2 stars; 1,067 records, 630 distinct texts, 366 after the minimum-length filter); theme counts equal distinct review ids in the window; each pulse quote's text and rating match its row; pulse at most 250 words; explainer at most 6 bullets with 2 official links.

## 2. Adversarial tests
{chr(10).join(['| Check | Result | Detail |','|---|---|---|'] + adv_rows)}

Also adversarial in Eval 2: edits that add PII or advice are refused; a reviewer-flagged draft cannot be approved (403); approving one write never triggers another; rejecting leaves state unchanged (state diff before and after).

## 2b. Regression tests from an outside review (26 Nov)
An independent review found four real defects after the first version of this report; each now has a test.
{chr(10).join(['| Check | Result | Detail |','|---|---|---|'] + reg_rows)}

## 2c. MCP server and persistence
{chr(10).join(['| Check | Result | Detail |','|---|---|---|'] + mcp_rows + pers_rows)}

## 2d. Approval security, privacy pathways and assignment requirements
{chr(10).join(['| Check | Result | Detail |','|---|---|---|'] + appr_rows + priv_rows + req_rows)}

**Voice:** the 7 browser tests drive a real Chromium engine with a *mocked* speech recogniser (unsupported browser, consent, permission denied, network and no-speech errors, state flow, transcript redaction, language list, read-aloud button). They do not exercise a real microphone or a vendor speech service; no live microphone test is claimed.

## 3. Scores
| Eval | Score | Source |
|---|---|---|
| Feasibility | {sm['feasibility']['passed']}/{sm['feasibility']['total']} | outputs/evals/feasibility.md |
| Correctness of edits | {sm['edit_correctness']['passed']}/{sm['edit_correctness']['total']} | outputs/evals/edit_correctness.md |
| Grounding and compliance | {sm['grounding_compliance']['passed']}/{sm['grounding_compliance']['total']} | outputs/evals/grounding_compliance.md |
| Regressions | {sm['regressions']['passed']}/{sm['regressions']['total']} | outputs/evals/regressions.md |
| Golden dataset | {sm['golden']['passed']}/{sm['golden']['total']} | outputs/evals/golden.md |
| MCP server | {sm['mcp_server']['passed']}/{sm['mcp_server']['total']} | outputs/evals/mcp_server.md |
| Persistence | {sm['persistence']['passed']}/{sm['persistence']['total']} | outputs/evals/persistence.md |
| Approval security | {sm['approval_security']['passed']}/{sm['approval_security']['total']} | outputs/evals/approval_security.md |
| Privacy pathways | {sm['privacy_pathways']['passed']}/{sm['privacy_pathways']['total']} | outputs/evals/privacy_pathways.md |
| Assignment requirements | {sm['requirements']['passed']}/{sm['requirements']['total']} | outputs/evals/requirements.md |

## 4. Limits
The golden labels were written by the author of the system. Checks are rule-based and cover the cases written here; the questions are synthetic; the reviewer checks word-level support, not meaning (a flipped sentence using the fact's own words could pass); advice detection is regex-based and unusual phrasing can slip past it (the reply would still be a cited fact or "not covered"); source pages were last checked by hand on 22 Oct and 26 Nov 2026 (see SOURCES.md); LLM paths are untested; voice is tested with a mock only; install from a clean environment, gunicorn, Docker and n8n were not run in the authoring sandbox.
"""
open("EVALS_REPORT.md", "w").write(md); print(len(rows), "golden rows;", len(adv_rows), "adversarial rows")
