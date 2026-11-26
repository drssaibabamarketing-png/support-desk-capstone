"""Demonstration for the video: MCP discovery and invocation over the real protocol (stdio).
Lists the tools, calls one with no receipt (refused), with a valid human-approval receipt (written, unsent draft), then replays it (refused)."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DESK_OUT", tempfile.mkdtemp(prefix="mcp_demo_"))
sys.path.insert(0, str(ROOT))
import mcp_layer as ml  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], env={**os.environ})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print("TOOLS:", [t.name for t in (await s.list_tools()).tools])
            args = {"subject": "Demo draft", "body": "Written through the MCP server after a human approval."}
            res = await s.call_tool("create_email_draft", {"receipt_id": "none", "arguments": args})
            print("1. no approval receipt ->", "REFUSED" if res.is_error else "WRITTEN", "|", res.content[0].text[:100])
            gate = ml.ApprovalGate("demo"); gate.decide(True)                      # stands for the human clicking Approve
            rid = ml.issue_receipt(gate, "create_email_draft", args)
            res = await s.call_tool("create_email_draft", {"receipt_id": rid, "arguments": args})
            print("2. valid receipt     ->", "REFUSED" if res.is_error else "WRITTEN", "|", res.content[0].text)
            res = await s.call_tool("create_email_draft", {"receipt_id": rid, "arguments": args})
            print("3. same receipt again->", "REFUSED" if res.is_error else "WRITTEN", "|", res.content[0].text[:100])
    audit = Path(os.environ["DESK_OUT"]) / "audit_log.jsonl"
    print("AUDIT:", json.loads(audit.read_text().splitlines()[-1]))


asyncio.run(main())
