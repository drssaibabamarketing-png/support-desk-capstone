"""A real MCP server (stdio) for the Support Desk write tools.

Run:   python mcp_server.py            (speaks the Model Context Protocol on stdin/stdout)
Use:   any MCP client (Claude Desktop, an agent framework, n8n's MCP client, the `mcp` Python SDK).

Every tool is a WRITE and is refused unless the caller presents a RECEIPT: a signed, single-use record, issued only
when a human approved that exact action in the web app, bound to this tool and these exact arguments.
A model that can reach this server therefore still cannot write anything on its own.
The tool bodies write local files (a stand-in for Google Docs / Gmail); swap the bodies in mcp_layer.py to go live.
"""
from __future__ import annotations

import json
from datetime import datetime

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import config
import mcp_layer as ml

server = MCPServer("support-desk", instructions="Write tools for the Groww/HDFC Support Desk. Each call needs a human-approval receipt_id.")


def _run(name: str, receipt_id: str, arguments: dict) -> str:
    try:
        ml.verify_and_consume_receipt(receipt_id, name, arguments, consume=False)   # authorise first
        ml.validate_args(name, arguments)                                           # a validation failure does not burn the receipt
        receipt = ml.verify_and_consume_receipt(receipt_id, name, arguments)        # atomic single use
        res = ml.run_tool(name, arguments)
    except (ml.ApprovalRequired, ValueError) as e:
        raise ToolError(str(e)) from e                                            # a clean, readable MCP error
    ml.OUT.mkdir(exist_ok=True)
    with (ml.OUT / "audit_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "tool": name, "via": "mcp-server",
                            "gate": receipt["gate"], "receipt": receipt["receipt_id"], "approved_at": receipt["approved_at"], "result": res}) + "\n")
    return json.dumps(res)


@server.tool(description=ml.TOOLS["append_weekly_record"]["description"] + " Needs a receipt.")
def append_weekly_record(receipt_id: str, arguments: dict) -> str:
    """arguments: run_id, window, entry_md, pulse, explainer"""
    return _run("append_weekly_record", receipt_id, arguments)


@server.tool(description=ml.TOOLS["create_weekly_email"]["description"] + " Needs a receipt.")
def create_weekly_email(receipt_id: str, arguments: dict) -> str:
    """arguments: subject, body"""
    return _run("create_weekly_email", receipt_id, arguments)


@server.tool(description=ml.TOOLS["append_support_record"]["description"] + " Needs a receipt.")
def append_support_record(receipt_id: str, arguments: dict) -> str:
    """arguments: ticket_id, date, complaint_redacted, reply_draft, citation_url, last_checked, routing_note, priority, ticket_status, agents_fired"""
    return _run("append_support_record", receipt_id, arguments)


@server.tool(description=ml.TOOLS["create_email_draft"]["description"] + " Needs a receipt.")
def create_email_draft(receipt_id: str, arguments: dict) -> str:
    """arguments: subject, body"""
    return _run("create_email_draft", receipt_id, arguments)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Support Desk MCP server")
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio",
                    help="stdio: launched by an MCP client or by the web app as a child process (same container). "
                         "streamable-http: a separately running service that remote MCP clients can reach.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=a.host, port=a.port)
