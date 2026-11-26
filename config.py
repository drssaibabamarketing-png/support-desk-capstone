"""Central settings for the Support Desk (Capstone)."""
import os
from pathlib import Path

BASE = Path(__file__).parent
REVIEWS_CSV = BASE / "data" / "reviews.csv"
OUT = Path(os.environ.get("DESK_OUT", BASE / "outputs"))
LOGS = Path(os.environ.get("DESK_LOGS", BASE / "logs"))
QUESTIONS_CSV = BASE / "data" / "questions.csv"
SOURCE_CHECKS = BASE / "data" / "source_checks.json"

PRODUCT = "Groww"
AMC = "HDFC Mutual Fund"

# Date the corpus snapshot was last verified against the live pages.
# UPDATE THIS when you re-verify corpus_registry.py (or set CORPUS_LAST_CHECKED in the env).
CORPUS_LAST_CHECKED = os.environ.get("CORPUS_LAST_CHECKED", "22 Oct 2026")

# --- Pattern agent
PATTERN_WINDOW_DAYS = 28        # total window, anchored on the newest review in the CSV
PATTERN_SPLIT_DAYS = 14         # recent half vs previous half -> trend
SIM_THRESHOLD = 0.15            # cosine similarity for "same issue" reviews (calibrated on 40 sampled 1-2 star reviews)
MIN_RECURRING = 5               # fewer similar reviews than this in the window = one-off
RISING_RATIO = 1.5              # recent >= 1.5x previous (and >= MIN_RECURRING) = rising
HOT_RECENT = 10                 # recurring with this many in the recent half also triggers HOLD

# --- Orchestrator / reviewer
MAX_SENTENCES = 3
MAX_REWORK = 1                  # reviewer -> orchestrator rounds
MAX_REFINEMENTS = 5

# --- Optional LLM (Groq). Everything works without it; with it, the orchestrator
# rewrites the draft and the reviewer adds an LLM advice-judge on top of the rules.
USE_LLM = bool(os.environ.get("GROQ_API_KEY")) and os.environ.get("USE_LLM", "1") != "0"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Capstone
WEEK_DAYS = 7                   # the weekly loop covers the newest 7 days of the reviews export
RECURRING_QUESTION_MIN = 5      # a question seen this many times in the window is surfaced in the pulse
PULSE_WORD_LIMIT = 250
EXPLAINER_BULLET_LIMIT = 6
DEMO_CLOCK = os.environ.get("REAL_CLOCK", "0") != "1"   # pin the demo clock to the end of the review export


def last_checked_for(url: str | None) -> str:
    """Per-source 'last checked' date (data/source_checks.json), falling back to the corpus-wide date."""
    import json
    try:
        d = json.loads(SOURCE_CHECKS.read_text(encoding="utf-8"))
        if url and url in d.get("sources", {}):
            return d["sources"][url]
        return d.get("default", CORPUS_LAST_CHECKED)
    except Exception:                                          # noqa: BLE001
        return CORPUS_LAST_CHECKED


# time-sensitive facts (expense ratio, exit load, minimum SIP) must have been re-checked recently, or the reply is blocked
TIME_SENSITIVE_MAX_DAYS = int(os.environ.get("TIME_SENSITIVE_MAX_DAYS", "60"))
TIME_SENSITIVE_INTENTS = {"expense_ratio", "exit_load", "min_sip"}


def today():
    from datetime import date
    o = os.environ.get("TODAY_OVERRIDE")                      # tests only
    return date.fromisoformat(o) if o else date.today()
