# Milestone lineage: what the capstone reuses and what is new

| Milestone | Repository | What it contributed | Used here as |
|---|---|---|---|
| 1. RAG FAQ assistant | `mutual-fund-faq-assistant` | Cited FAQ corpus over official pages, facts-only refusal, source list | `corpus.py`, `corpus_registry.py`, `ALLOWED_URLS`; same HDFC, AMFI, SEBI and Groww sources |
| 2. Product Insights Copilot | `product-insights-copilot` | Review clustering, weekly pulse, fee explainer, approval-gated MCP workflow | `pipeline.py`, `mcp_layer.py` (gate) and the fee knowledge base |
| 3. Multi-Agent Support Desk | `multi-agent-support-desk` | Three parallel agents, orchestrator, reviewer, PII gate, refinement | `desk.py`, `agents.py`, `orchestrator.py`, `reviewer.py`, `pii.py` |
| **Capstone** | this repo | Everything below | — |

## New in the capstone
- One `Service` that owns both loops and one shared state.
- The weekly loop inside the app (not a separate tool), with review ids on every theme and quote, a stated window, a quote filter and per-bullet citations.
- **The connection:** question counts into the pulse, and the approved explainer as the canonical answer.
- Per-action approval gates (two weekly, one per ticket) and a human **edit** path that is re-reviewed.
- Queue, Overview, Sources, Approvals and Canonical views; per-source last-checked dates.
- State snapshots and diffs; three evaluations over the assembled system; scheduled headless weekly run.
- Docs, Docker, CI and an optional n8n workflow.

## Changed from the milestones
- Reviews export replaced (8,629 rows, ids R1–R8629, 5 Jul to 29 Aug 2026); the weekly window is 7 days (M2 used 12 weeks).
- Pulse format now lists counts and review ids; quotes carry ids.
- Return-figure requests are refused (they were "not covered" in M3).
