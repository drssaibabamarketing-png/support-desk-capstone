"""Reviewer: hard-fail checks on a draft before a human ever sees it.

Hard fails: uncited factual claim, advice language, return/performance claim, surviving PII,
figure not found in the retrieved fact, wrong citation, >3 sentences, missing 'last checked'.
Failures carry a code and a PII-free detail so the orchestrator can be told exactly what to fix.
"""
from __future__ import annotations

import re

import config
import llm
from agents import ComplianceAgent
from corpus import ALLOWED_URLS
from orchestrator import BOILER_TEXTS

_LINK = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_DATE = re.compile(r"Last checked:\s*(\d{1,2} [A-Za-z]{3} \d{4})")



_SW = set("a an the is are was were be been of for to in on at by with and or as it its this that these those from if than then so but not no".split())
_ABSOLUTE = {"always", "never", "zero", "free", "nothing", "guaranteed", "all", "every", "only", "none", "waived", "waive", "unlimited"}


def _bigrams(t: list[str]) -> set:
    return set(zip(t, t[1:]))


def _stem(w: str) -> str:
    return re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w


def _content(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9%.]+", text.lower()) if w not in _SW and len(w) > 1} | \
           {w for w in re.findall(r"[a-z]+", text.lower()) if w in _ABSOLUTE}


def split_reply(full_text: str) -> tuple[list[dict], str | None]:
    """Parse a draft into sentences (each with its citation URLs) and the 'last checked' date."""
    m = _DATE.search(full_text)
    foot = re.search(r"\n\s*Last checked:", full_text)          # a footer without a date ("not confirmed") is still a footer
    body = full_text[: m.start()].strip() if m else (full_text[: foot.start()].strip() if foot else full_text.strip())
    urls: list[str] = []

    def stash(mo):
        urls.append(mo.group(1))
        return f"§{len(urls) - 1}§"

    flat = _LINK.sub(stash, body)
    parts = [p for p in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", flat) if p.strip()]
    sents = []
    for p in parts:
        ids = [int(i) for i in re.findall(r"§(\d+)§", p)]
        sents.append({"text": re.sub(r"\(§\d+§\)", "", p).replace("§", "").strip(), "urls": [urls[i] for i in ids]})
    return sents, (m.group(1) if m else None)


def review(orch: dict, facts: dict, comp_agent: ComplianceAgent | None = None) -> dict:
    comp_agent = comp_agent or ComplianceAgent()
    full = orch["reply"]["full_text"]
    note = orch["routing"]["note"]
    sents, last = split_reply(full)
    fails: list[dict] = []

    def fail(code: str, detail: str):
        fails.append({"code": code, "detail": detail})

    # 1. length and last-checked
    if len(sents) > config.MAX_SENTENCES:
        fail("SENTENCE_LIMIT", f"{len(sents)} sentences; the limit is {config.MAX_SENTENCES}")
    import verification
    unconfirmed = None
    if facts["status"] == "covered" and facts.get("citation_url"):
        v = verification.fact_status(facts["citation_url"], facts.get("fact_intents"))
        unconfirmed = v if v and v["status"] == "unconfirmed" else None
    # The only accepted footer without a date is "Last checked: not confirmed ...", and only for a fact that really is
    # unconfirmed (that reply is then blocked by UNCONFIRMED_SOURCE below). Any other missing date still fails here.
    if not last and not (unconfirmed and re.search(r"Last checked: not confirmed", full)):
        fail("MISSING_LAST_CHECKED", "reply has no 'Last checked: <date>' line")

    # 2. citations: every non-boilerplate sentence needs exactly one allowed link; and it must be Facts' link
    covered = facts["status"] == "covered"
    for i, s in enumerate(sents, 1):
        if s["text"] in BOILER_TEXTS or re.sub(r"\s+", " ", s["text"]) in BOILER_TEXTS:
            continue
        if len(s["urls"]) != 1:
            fail("UNCITED_FACT", f"sentence {i} makes a claim but carries {len(s['urls'])} citation links (needs exactly 1)")
        else:
            u = s["urls"][0]
            if u not in ALLOWED_URLS:
                fail("WRONG_CITATION", f"sentence {i} cites a URL outside the corpus source list")
            elif covered and u != facts["citation_url"]:
                fail("WRONG_CITATION", f"sentence {i} cites a different page than the retrieved fact")
        if not covered:
            fail("UNCITED_FACT", f"sentence {i} states something but the corpus did not cover this question")

    # 2a. owner's decision (26 Nov 2026): a fact whose official source has not been checked for it is blocked
    if unconfirmed:
        fail("UNCONFIRMED_SOURCE", f"{unconfirmed['reason']}; this answer cannot be approved until a person checks the page "
             "and records it in data/source_checks.json")

    # 2b. time-sensitive facts must have been re-checked recently (stale expense ratios are never served)
    if covered and set(facts.get("intents") or []) & config.TIME_SENSITIVE_INTENTS and facts.get("citation_url"):
        from datetime import datetime as _dt
        try:
            age = (config.today() - _dt.strptime(config.last_checked_for(facts["citation_url"]), "%d %b %Y").date()).days
        except ValueError:
            age = 10 ** 6
        if age > config.TIME_SENSITIVE_MAX_DAYS:
            fail("STALE_FACT", f"the source for this time-sensitive figure was last checked {age} days ago "
                 f"(limit {config.TIME_SENSITIVE_MAX_DAYS}); re-check the page and update data/source_checks.json")

    # 3. figures must come from the retrieved fact
    plain = _LINK.sub("", " ".join(s["text"] for s in sents))
    allowed_nums = set(_NUM.findall(facts.get("answer") or ""))
    extra = [n for n in _NUM.findall(plain) if n not in allowed_nums]
    if extra:
        fail("UNGROUNDED_FIGURE", f"{len(extra)} figure(s) in the reply do not appear in the retrieved fact")

    # 3b. support: each factual sentence must be backed by the retrieved fact's own words, not just its URL
    if covered:
        fact_words = _content(facts.get("answer") or "")
        for i, s in enumerate(sents, 1):
            if s["text"] in BOILER_TEXTS or re.sub(r"\s+", " ", s["text"]) in BOILER_TEXTS:
                continue
            w = _content(_LINK.sub("", s["text"]))
            if not w:
                continue
            toks = re.findall(r"[a-z0-9%.]+", _LINK.sub("", s["text"]).lower())
            fb = _bigrams(re.findall(r"[a-z0-9%.]+", (facts.get("answer") or "").lower()))
            sb = _bigrams(toks)
            if sb and len(sb & fb) / len(sb) < 0.8:                      # word order/meaning differs from the source sentence
                fail("UNSUPPORTED_CLAIM", f"sentence {i} rewords the cited fact so its meaning may change (phrase order differs from the source)")
                continue
            unsupported = w - fact_words
            absolute = {x for x in w if x in _ABSOLUTE} - fact_words
            if absolute or len(unsupported) / len(w) > 0.34:
                fail("UNSUPPORTED_CLAIM", f"sentence {i} says things the cited source text does not support: "
                     + ", ".join(sorted(absolute or unsupported)[:5]))

    # 4. advice language / return claims / PII (draft AND internal note)
    scan = comp_agent.scan_draft(full)
    if scan["advice_language"]:
        fail("ADVICE_LANGUAGE", f"{len(scan['advice_language'])} advice-style phrase(s); the reply must be facts-only")
    if scan["return_claims"]:
        fail("RETURN_CLAIM", f"{len(scan['return_claims'])} return/performance claim(s); remove them")
    leaked = sorted(set(scan["pii"]) | set(comp_agent.scan_draft(note)["pii"]))
    if leaked:
        fail("PII_SURVIVED", "PII still present in the draft or routing note: " + ", ".join(leaked))

    # 5. optional LLM second opinion (only when a key is configured)
    judged = None
    if config.USE_LLM and not fails:
        try:
            judged = llm.judge_advice(full)
            if judged:
                fail("ADVICE_LANGUAGE", "LLM judge flagged advice or return language")
        except Exception:                                  # noqa: BLE001
            judged = None

    return {"passed": not fails, "failures": fails, "sentences": len(sents), "llm_judged": judged}
