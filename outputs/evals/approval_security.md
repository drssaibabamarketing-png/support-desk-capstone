# Eval 8: Approval security (expiry, replay, duplicates, concurrency, isolation)

Result: **12/12 checks pass**

| Check | Result | Detail |
|---|---|---|
| rejecting the doc action writes nothing, leaves the email action pending, adds exactly one journal row | PASS | rows 0->1 |
| a rejected gate cannot be turned into a receipt | PASS |  |
| a rejected action cannot be approved afterwards (no second decision) | PASS | {'ok': False, 'error': 'action already rejected'} |
| 12 concurrent approvals of the same action: exactly one succeeds, one write, one audit line, one journal row | PASS | wins=1 audit+=1 rows+=1 |
| the other weekly action was not approved by those requests | PASS |  |
| 6 concurrent ticket approvals: each ticket written once (2 audit lines each), no other ticket changed | PASS | audit+=12 |
| a duplicate approve request for an approved ticket is refused and changes nothing | PASS | {'ok': False, 'error': 'ticket already approved'} |
| an accepted edit changes only that ticket and adds exactly one journal row | PASS | [] |
| a refused edit changes nothing, in memory or in the database | PASS | The reviewer rejected the edit: UNCITED_FACT; UNSUPPORTED_CLAIM. Nothing was cha |
| an expired receipt is refused (valid for 15 minutes by default) | PASS |  |
| 8 concurrent uses of one receipt: exactly one succeeds (replay prevention under a race) | PASS | 1 ok / 7 refused |
| no sensitive identifier in the database or written files after the run | PASS | [] |
