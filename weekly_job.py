"""Headless weekly loop: what the scheduler runs (GitHub Actions cron, or `python weekly_job.py`).

Seeds the queue, runs the weekly loop with no human input, and leaves the two writes PENDING at the approval gate.
Exit code 0 only if every output check passed. Writes only a small result file; nothing is sent or appended.
"""
import json
import sys
import time

import config
from service import Service


def main() -> int:
    t0 = time.time()
    svc = Service()
    svc.seed()
    if len(sys.argv) > 1:                              # python weekly_job.py path/to/newer_reviews.csv
        up = svc.use_reviews(open(sys.argv[1], 'rb').read(), sys.argv[1])
        if not up['ok']:
            print(up['error']); return 2
    run = svc.run_weekly()
    ok = all(c[1] for c in run["checks"])
    res = {"run_id": run["run_id"], "window": run["window"], "reviews": run["n_reviews"], "themes": len(run["themes"]),
           "pulse_words": run["pulse_words"], "explainer_bullets": len(run["explainer"]["bullets"]),
           "fee_issue": run["fee"]["fee"], "signals": [s["label"] + f" x{s['count']}" for s in run["signals"]],
           "checks_passed": ok, "pending_actions": run["action_ids"], "seconds": round(time.time() - t0, 1)}
    config.OUT.mkdir(exist_ok=True)
    (config.OUT / "weekly_job_result.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
