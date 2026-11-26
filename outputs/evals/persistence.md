# Eval 7: Persistence (a restart keeps human decisions)

Result: **5/5 checks pass**

| Check | Result | Detail |
|---|---|---|
| after a restart the live question is back in the queue | PASS | {'questions': 1, 'refinements': 0, 'redrafts': 0, 'edits': 1, 'tickets': 1, 'actions': 1} |
| the approved weekly doc action and its canonical explainer survive | PASS | {'Brokerage & trade charges': 1} |
| the other weekly action is still pending (not silently approved) | PASS |  |
| an approved ticket stays approved; the replay wrote no new files | PASS |  |
| restoring twice yields exactly the same queue (no duplicate tickets) | PASS | 39 vs 39 |
