"""Pre-submission scan: personal-data patterns, secrets and unwanted generated files in the tree. Exit 1 on any finding."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pii  # noqa: E402

SKIP_DIRS = {".git", "__pycache__", "node_modules"}
TEXT = {".py", ".md", ".txt", ".csv", ".json", ".jsonl", ".html", ".css", ".yml", ".yaml", ".toml", ".cfg", ".eml", ".mmd", ".env", ".example", ""}
SECRET = re.compile(r"(?i)(?:gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
# Known, reviewed, intentionally fake data: a placeholder address and the dummy PII the redaction evals feed in.
ALLOW = {"n8n-workflow.json", "evals/run_evals.py"}
BAD_NAMES = ("poison", ".approval_key", ".env")
BAD_SUFFIX = (".db", ".sqlite", ".used", ".expired")


def publishable() -> tuple[list[Path], int]:
    """Files that would be published: in a git checkout, tracked + untracked-but-not-ignored (exactly what `git add -A`
    would ship). Ignored runtime artefacts (outputs/evals/runtime, logs/, receipts) cannot be published, so they are
    counted, not scanned; a database or receipt there is expected after an eval run. Without git, every file is scanned."""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, check=True).stdout.decode("utf-8")
        files = sorted({ROOT / f for f in out.split("\0") if f and (ROOT / f).is_file()})
        everything = [p for p in ROOT.rglob("*") if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)]
        return files, len(everything) - len(files)
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file()], 0


def main() -> int:
    findings = []
    files, ignored = publishable()
    if ignored:
        print(f"{ignored} git-ignored file(s) not scanned (runtime artefacts that cannot be published)")
    for p in files:
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(ROOT)
        if p.name in (".env",) or any(b in p.name.lower() for b in ("poison",)) or p.name == ".approval_key" or p.suffix in BAD_SUFFIX:
            findings.append(f"unwanted generated/sensitive file: {rel}")
            continue
        if p.suffix.lower() in TEXT and p.stat().st_size < 6_000_000:
            txt = p.read_text("utf-8", "ignore")
            if SECRET.search(txt):
                findings.append(f"possible secret in {rel}")
            if (rel.parts[0] != "data" or p.name != "reviews.csv") and rel.as_posix() not in ALLOW:
                hits = pii.detect(txt)
                if hits:
                    findings.append(f"PII-like pattern {hits} in {rel}")
    for f in findings:
        print("FINDING:", f)
    print("files clean" if not findings else f"{len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
