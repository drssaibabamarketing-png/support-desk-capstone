# Edge cases

Status: **tested** = covered by an eval or unit test; **checked** = exercised by hand or visible in samples; **limit** = known weakness.

## Input and PII
| Case | Behaviour | Status |
|---|---|---|
| PAN, phone, account, Aadhaar, OTP, email in a question | Redacted before anything is stored; reply tells the customer not to share them; ticket shows "PII removed" chips | tested |
| PII mixed with an advice request | Both handled: redacted and refused | tested |
| PII repeated or rephrased (Hinglish) | Redacted | tested |
| PII inside a review | Redacted at preparation and at ingest | tested (poisoned CSV) |
| Message over 2000 characters | Truncated before processing | checked |
| Edit contains PII | Refused, nothing changes | tested |
| Digits that look like PII but are not (e.g. a long order number) | May be redacted as ACCOUNT (conservative) | limit |

## Scope and compliance
| Case | Behaviour | Status |
|---|---|---|
| "Should I redeem…", "is it a good fund" | Refusal template; may add one cited fact (e.g. exit load) but no recommendation | tested |
| Rephrased, repeated, pushed back inside the ticket | Advice flag is sticky per ticket | tested |
| "What is the 5 year return / CAGR…" | Refused as a return-figure request | tested |
| Advice phrased in a way no pattern matches | Reply is still facts-only; may be answered as a plain fact or "not covered" | limit |
| Reviews containing advice or return claims | Never used as quotes; pulse scanned | tested |

## Grounding
| Case | Behaviour | Status |
|---|---|---|
| Corpus has no answer | "I couldn't find this in our official sources…", lists what was searched | tested |
| Scheme-specific question without naming a scheme | Routing note says "Scheme not specified"; no guess | checked |
| Sentence without exactly one allowed link | Reviewer hard-fail `UNCITED_FACT` / `WRONG_CITATION` | tested |
| Figure in the reply not in the fact | `UNGROUNDED_FIGURE` | tested (M3 evidence) |
| Source page has changed since the last check | Reply carries its last-checked date; dates are edited by hand | limit |

## Approval and state
| Case | Behaviour | Status |
|---|---|---|
| Approving a reviewer-flagged draft | 403, nothing written | tested |
| Approving a rejected or already approved item | Refused, no state change | tested (ticket); checked (action) |
| Approving the doc action does not create the email | Separate gate | tested |
| Re-running the weekly loop with pending actions | A different run's pending actions become `superseded`; identical content keeps its pending action and gate | tested |
| Re-running the weekly loop after an approval (identical content) | The approved action stays approved and is not offered again (no duplicate doc entry, no canonical version bump); a rejected one is re-offered under a new id, the rejection kept | tested |
| Restart after refining or re-drafting a ticket | Refinements (redacted note) and re-drafts are journalled and replayed in order, so a later edit restores against the right citation | tested |
| Restart after the stale-fact date, with an accepted edit on a time-sensitive fact | The edit's wording is restored, but the ticket stays flagged (`STALE_FACT`) and cannot be approved until the source is re-checked; a live edit of a stale fact is still refused; any other replay failure is logged as `edit_not_restored` | tested |
| A write fails during approval | The ticket/action stays pending, nothing is journalled; approving again performs only the missing write | tested |
| Edit that breaks the one-link rule | Refused with the reviewer's failure codes | checked |
| Two browsers act at once | `RLock` serialises mutations | checked |
| App restarts | Queue and canonical store reset | limit |

## Weekly loop data
| Case | Behaviour | Status |
|---|---|---|
| Very short or duplicate reviews | Dropped (under 4 words; exact duplicates) | tested |
| Fewer reviews than 5 per theme | `k` shrinks (`len(df)//5`) | checked |
| CSV without a date column | **Not supported by the weekly loop** (needs the window) | limit |
| CSV missing text or rating | `ValueError` naming accepted column names | checked |
| Pulse over 250 words | Quote length is trimmed stepwise, then the cap check runs | tested |
| Fee never mentioned | The most-mentioned fee type is still chosen; counts will be small and visible | limit |

## Deployment
| Case | Behaviour | Status |
|---|---|---|
| Render free instance asleep | First request wakes it (~30 s); state is fresh | limit |
| Source site unreachable at check time | Dates stay as last verified | limit |
