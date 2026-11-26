# Eval 6: MCP server over stdio (signed approval receipts)

Result: **13/13 checks pass**

| Check | Result | Detail |
|---|---|---|
| server lists the four write tools over the MCP protocol | PASS | ['append_support_record', 'append_weekly_record', 'create_email_draft', 'create_weekly_email'] |
| a call with no approval receipt is refused | PASS | Error executing tool create_email_draft: no human approval on record for this call (receip |
| a call whose arguments changed after approval is refused | PASS | Error executing tool create_email_draft: receipt does not match this tool and these exact  |
| a receipt for one tool cannot be used on another | PASS | Error executing tool create_weekly_email: receipt does not match this tool and these exact |
| a valid receipt lets the write through and it is an unsent draft | PASS | {"ok": true, "path": "support_reply_draft.eml", "sent": false} |
| a receipt cannot be replayed | PASS | Error executing tool create_email_draft: receipt already used |
| PII is refused even with a valid receipt | PASS | Error executing tool create_email_draft: payload still contains PII (PAN); refusing to sto |
| exactly one audit line was written by the server for the one allowed write | PASS | [{'ts': '2026-11-26T23:07:30', 'tool': 'create_email_draft', 'via': 'mcp-server', 'gate': 'da449460', 'receipt': 'mjdwrr |
| streamable-HTTP transport: tools are discoverable | PASS | ['append_support_record', 'append_weekly_record', 'create_email_draft', 'create_weekly_email'] |
| streamable-HTTP transport: no receipt refused, valid receipt writes an unsent draft | PASS |  |
| a validation failure (missing required argument) is reported as an error | PASS | Error executing tool create_email_draft: missing arguments: ['body'] |
| approving the weekly doc action in the app wrote through the MCP server (audit says via mcp-server) | PASS | [{'ts': '2026-11-26T23:07:37', 'tool': 'append_weekly_record', 'via': 'mcp-server', 'gate': '889f007c', 'receipt': 'xydpefwmvnbeecqmnktt', ' |
| the other weekly action stayed pending | PASS |  |
