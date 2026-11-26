"""MCP-style tool layer with the same approval gate as Milestone 2.

NO tool executes unless a human-approved ApprovalGate is passed in. After approval the desk:
  1. append_support_record -> outputs/support_log.md + .jsonl   (stand-in for the Google Doc)
  2. create_email_draft    -> outputs/support_reply_draft.eml   (X-Unsent, NEVER sent)
Swap the two bodies for Google Docs / Gmail MCP calls to go live; the gate does not change.
Defence in depth: every payload is re-scanned for PII and refused if any survives.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime
from email.message import EmailMessage

import config
import pii

OUT = config.OUT


class ApprovalRequired(PermissionError):
    pass


class ApprovalGate:
    """Created pending; only a human click flips it."""

    def __init__(self, summary: str):
        self.id = secrets.token_hex(4)
        self.summary = summary
        self.status = "pending"          # pending | approved | rejected
        self.decided_at = None

    def decide(self, approve: bool):
        self.status = "approved" if approve else "rejected"
        self.decided_at = datetime.now().isoformat(timespec="seconds")


TOOLS = {
    "append_support_record": {
        "description": "Append the approved ticket record (redacted complaint, reply, citation, routing note) to the team log.",
        "inputSchema": {"type": "object", "required": [
            "ticket_id", "date", "complaint_redacted", "reply_draft", "citation_url", "last_checked",
            "routing_note", "priority", "ticket_status", "agents_fired"]},
    },
    "create_email_draft": {
        "description": "Create an email DRAFT (.eml, X-Unsent). Never sends.",
        "inputSchema": {"type": "object", "required": ["subject", "body"]},
    },
}


TOOLS["append_weekly_record"] = {
    "description": "Append the approved weekly pulse + fee explainer entry to the team doc (outputs/weekly_log.md).",
    "inputSchema": {"type": "object", "required": ["run_id", "window", "entry_md", "pulse", "explainer"]},
}
TOOLS["create_weekly_email"] = {
    "description": "Create the weekly pulse email DRAFT (.eml, X-Unsent). Never sends.",
    "inputSchema": {"type": "object", "required": ["subject", "body"]},
}


def list_tools() -> list[dict]:
    return [{"name": n, **t} for n, t in TOOLS.items()]


def _append_support_record(a: dict) -> dict:
    OUT.mkdir(exist_ok=True)
    md = OUT / "support_log.md"
    entry = (f"\n---\n## Ticket {a['ticket_id']} - {a['date']}  [{a['priority']}]  status: {a['ticket_status']}\n"
             f"**Complaint (redacted):** {a['complaint_redacted']}\n\n"
             f"**Reply draft:**\n\n{a['reply_draft']}\n\n"
             f"**Citation:** {a['citation_url'] or 'none (not covered by corpus)'}  |  **Last checked:** {a['last_checked']}\n\n"
             f"**Routing note:** {a['routing_note']}\n\n"
             f"**Agents fired:** {', '.join(a['agents_fired'])}\n")
    with md.open("a", encoding="utf-8") as f:
        f.write(entry)
    with (OUT / "support_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(a, ensure_ascii=False) + "\n")
    return {"ok": True, "path": md.name, "chars_appended": len(entry)}


def _create_email_draft(a: dict) -> dict:
    OUT.mkdir(exist_ok=True)
    m = EmailMessage()
    m["Subject"] = a["subject"]
    m["To"] = a.get("to", "")            # left blank: customer contact details are never stored
    m["X-Unsent"] = "1"
    m.set_content(a["body"])
    p = OUT / "support_reply_draft.eml"
    p.write_bytes(bytes(m))
    (OUT / "support_reply_draft.txt").write_text(f"Subject: {a['subject']}\n\n{a['body']}", encoding="utf-8")
    return {"ok": True, "path": p.name, "sent": False}


def _append_weekly_record(a: dict) -> dict:
    OUT.mkdir(exist_ok=True)
    md = OUT / "weekly_log.md"
    with md.open("a", encoding="utf-8") as f:
        f.write(a["entry_md"])
    with (OUT / "weekly_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: a[k] for k in ("run_id", "window", "pulse", "explainer")}, ensure_ascii=False) + "\n")
    return {"ok": True, "path": md.name, "chars_appended": len(a["entry_md"])}


def _create_weekly_email(a: dict) -> dict:
    OUT.mkdir(exist_ok=True)
    m = EmailMessage()
    m["Subject"] = a["subject"]
    m["To"] = a.get("to", "")
    m["X-Unsent"] = "1"
    m.set_content(a["body"])
    (OUT / "weekly_pulse_draft.eml").write_bytes(bytes(m))
    (OUT / "weekly_pulse_draft.txt").write_text(f"Subject: {a['subject']}\n\n{a['body']}", encoding="utf-8")
    return {"ok": True, "path": "weekly_pulse_draft.eml", "sent": False}


_IMPL = {"append_support_record": _append_support_record, "create_email_draft": _create_email_draft,
         "append_weekly_record": _append_weekly_record, "create_weekly_email": _create_weekly_email}


# ----------------------------------------------------------------------------- signed approval receipts
# The gate lives in the web app (a human clicks). To make the approval verifiable on the far side of a protocol
# boundary, an approved gate yields a signed, single-use RECEIPT bound to the tool name and the exact arguments.
# The MCP server (mcp_server.py) refuses every write tool unless it is shown a valid, unused receipt.
def _key() -> bytes:
    env = os.environ.get("APPROVAL_SECRET")
    if env:
        return env.encode()
    OUT.mkdir(exist_ok=True)
    kp = OUT / ".approval_key"
    if not kp.exists():
        kp.write_text(secrets.token_hex(32))
    return kp.read_text().strip().encode()


def args_hash(name: str, arguments: dict) -> str:
    return hashlib.sha256((name + "\n" + json.dumps(arguments, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()


def issue_receipt(gate: "ApprovalGate", name: str, arguments: dict) -> str:
    if gate is None or gate.status != "approved":
        raise ApprovalRequired(f"no receipt: approval gate is {getattr(gate, 'status', 'missing')}")
    now = time.time()
    body = {"receipt_id": "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(20)), "gate": gate.id, "tool": name, "args_sha256": args_hash(name, arguments),
            "approved_at": gate.decided_at, "issued_at": now, "expires_at": now + float(os.environ.get("APPROVAL_TTL_SECONDS", "900"))}
    body["sig"] = hmac.new(_key(), json.dumps({k: body[k] for k in sorted(body)}).encode(), hashlib.sha256).hexdigest()
    d = OUT / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{body['receipt_id']}.json").write_text(json.dumps(body))
    return body["receipt_id"]


def verify_and_consume_receipt(receipt_id: str, name: str, arguments: dict, now: float | None = None, consume: bool = True) -> dict:
    """Used by the MCP server. Raises ApprovalRequired unless the receipt is genuine, for THIS tool and THESE arguments, and unused."""
    p = OUT / "receipts" / f"{''.join(c for c in str(receipt_id) if c.isalnum())}.json"
    try:
        body = json.loads(_retry_sharing(p.read_text))
    except FileNotFoundError:                                     # never issued, or consumed by a concurrent caller just now
        raise ApprovalRequired("no human approval on record for this call (receipt not found)") from None
    except (OSError, ValueError):
        raise ApprovalRequired("receipt could not be read; approve the action again") from None
    sig = body.pop("sig", "")
    good = hmac.new(_key(), json.dumps({k: body[k] for k in sorted(body)}).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good):
        raise ApprovalRequired("receipt signature invalid")
    if (now if now is not None else time.time()) > body.get("expires_at", 0):
        try:
            p.rename(p.with_suffix(".expired"))
        except OSError:
            pass                                                  # refused either way; the file state is not security-relevant
        raise ApprovalRequired("approval expired (receipts are valid for a limited time); approve the action again")
    if body["tool"] != name or body["args_sha256"] != args_hash(name, arguments):
        raise ApprovalRequired("receipt does not match this tool and these exact arguments (content changed after approval)")
    claim = p.with_suffix(".used")
    if claim.exists():
        raise ApprovalRequired("receipt already used")
    if consume:
        # Single use. The claim is an EXCLUSIVE CREATE of <id>.used (O_CREAT|O_EXCL), which the OS guarantees only one
        # caller can win, on Windows (CREATE_NEW) and POSIX alike. The previous claim was a rename of <id>.json, which is
        # atomic on POSIX but NOT on Windows: concurrent renames of one file were each reported as successful, so one
        # approval could authorise several writes (found 26 Nov 2026; tests/test_capstone.py). Losers fail closed.
        try:
            os.close(os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            raise ApprovalRequired("receipt already used") from None
        except OSError:
            raise ApprovalRequired("receipt could not be claimed; it was not used by this call") from None
    return body


def _retry_sharing(fn, attempts: int = 50, delay: float = 0.005):
    """Run fn, retrying a Windows sharing violation (PermissionError) for up to ~0.25 s. Other errors pass straight through."""
    for i in range(attempts):
        try:
            return fn()
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay)


def validate_args(name: str, arguments: dict) -> None:
    missing = [k for k in TOOLS[name]["inputSchema"]["required"] if k not in arguments]
    if missing:
        raise ValueError(f"missing arguments: {missing}")
    leaked = pii.detect(json.dumps(arguments, ensure_ascii=False))
    if leaked:
        raise ValueError("payload still contains PII (" + ", ".join(leaked) + "); refusing to store it")


def run_tool(name: str, arguments: dict) -> dict:
    """Validate and execute a tool body (no gate check: callers must have verified approval). Used by the MCP server."""
    validate_args(name, arguments)
    return _IMPL[name](arguments)


def _via_stdio(name: str, arguments: dict, gate: "ApprovalGate") -> dict:
    """Route the write through the real MCP server over stdio (MCP_TRANSPORT=stdio)."""
    import asyncio
    import sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    rid = issue_receipt(gate, name, arguments)

    async def go():
        params = StdioServerParameters(command=sys.executable, args=[str(__import__("pathlib").Path(__file__).with_name("mcp_server.py"))], env={**os.environ})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                res = await s.call_tool(name, {"receipt_id": rid, "arguments": arguments})
                if res.is_error:
                    raise ApprovalRequired("MCP server refused: " + " ".join(getattr(c, "text", "") for c in res.content))
                return json.loads(res.content[0].text)
    return asyncio.run(go())


def call_tool(name: str, arguments: dict, gate: ApprovalGate) -> dict:
    if gate is None or gate.status != "approved":
        raise ApprovalRequired(f"'{name}' blocked: approval gate is {getattr(gate, 'status', 'missing')}")
    missing = [k for k in TOOLS[name]["inputSchema"]["required"] if k not in arguments]
    if missing:
        raise ValueError(f"missing arguments: {missing}")
    leaked = pii.detect(json.dumps(arguments, ensure_ascii=False))
    if leaked:
        raise ValueError("payload still contains PII (" + ", ".join(leaked) + "); refusing to store it")
    if os.environ.get("MCP_TRANSPORT") == "stdio":
        return _via_stdio(name, arguments, gate)               # the MCP server verifies the receipt, writes and audits
    res = _IMPL[name](arguments)
    OUT.mkdir(exist_ok=True)
    with (OUT / "audit_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "tool": name,
                            "gate": gate.id, "approved_at": gate.decided_at, "result": res}) + "\n")
    return res


def build_payloads(t: dict) -> tuple[dict, dict]:
    d = t["draft"]
    hold = d["routing"]["hold"]
    flat_fired = [a for e in t["fired_log"] for a in e["agents_fired"]]
    status = "escalated_open (ticket NOT closed)" if hold else ("open (needs human answer)"
             if t["outputs"]["facts"]["status"] != "covered" else "reply approved")
    record = {
        "ticket_id": t["tid"], "date": datetime.now().date().isoformat(),
        "complaint_redacted": t["message"], "reply_draft": d["reply"]["full_text"],
        "citation_url": d["reply"]["citation_url"], "last_checked": d["reply"]["last_checked"],
        "routing_note": d["routing"]["note"], "priority": d["routing"]["priority"],
        "ticket_status": status, "agents_fired": flat_fired,
        "pii_types_removed": [f["type"] for f in t["pii_removed"]],
    }
    prefix = "[HOLD - escalate before sending] " if hold else ""
    email = {
        "to": "", "subject": f"{prefix}Support reply draft - ticket {t['tid']}",
        "body": f"{d['reply']['full_text']}\n\n--- INTERNAL (remove before sending) ---\n{d['routing']['note']}",
    }
    return record, email
