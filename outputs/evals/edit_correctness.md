# Eval 2: Correctness of edits (state diffed before and after)

Result: **16/16 checks pass**

| Check | Result | Detail |
|---|---|---|
| a human edit to one draft changes only that draft | PASS | changed: ['~ /tickets/cc675f10/edited', '~ /tickets/cc675f10/reply']; unexpected: none |
| an edit that adds advice is refused by the reviewer and changes nothing | PASS | changed: nothing; unexpected: none |
| an edit that contains a PAN is refused and changes nothing | PASS | changed: nothing; unexpected: none |
| rejecting a draft changes only that ticket's status and writes no file | PASS | changed: ['~ /tickets/e7e6ff4e/status']; unexpected: none |
| a rejected ticket cannot be approved afterwards (nothing changes) | PASS | changed: nothing; unexpected: none |
| approving one ticket writes only that ticket's two items | PASS | changed: ['+ /files/audit_log.jsonl', '+ /files/support_log.jsonl', '+ /files/support_log.md', '+ /files/support_reply_draft.eml', '+ /files/support_reply_draft.txt', '~ /tickets/cc675f10/status', '~ /tickets/cc675f10/writes']; unexpected: none |
| approving a ticket created no weekly files | PASS | ['audit_log.jsonl', 'support_log.jsonl', 'support_log.md', 'support_reply_draft.eml', 'support_reply_draft.txt'] |
| the support log holds exactly one entry (ticket A), none for B or C | PASS | 1 entry |
| approving the weekly doc action writes only the doc entry and registers the canonical explainer | PASS | changed: ['~ /actions/W-ddc8f9:append_weekly_record', '+ /canonical/Brokerage & trade charges', '~ /files/audit_log.jsonl', '+ /files/weekly_log.jsonl', '+ /files/weekly_log.md']; unexpected: none |
| email draft does not exist yet (approving the doc did not trigger it) | PASS |  |
| approving the weekly email action writes only the email draft | PASS | changed: ['~ /actions/W-ddc8f9:create_weekly_email', '~ /files/audit_log.jsonl', '+ /files/weekly_pulse_draft.eml', '+ /files/weekly_pulse_draft.txt']; unexpected: none |
| re-draft touches only the one ticket it was called on (and now reuses the canonical explainer) | PASS | changed: ['~ /tickets/d197b2cc/canonical', '~ /tickets/d197b2cc/note']; unexpected: none |
| rejecting a weekly action leaves the other pending and writes no file | PASS | changed: ['~ /actions/W-9091d8:append_weekly_record']; unexpected: none |
| the other action of that run is still pending | PASS | pending |
| a draft the reviewer flagged cannot be approved (403) and nothing is written | PASS | flagged=True, response={'ok': False, 'status': 403, 'error': 'The reviewer flagged this draft; it cannot be approved.'} |
| the MCP layer refuses any tool call while the gate is pending | PASS | ApprovalRequired raised |
