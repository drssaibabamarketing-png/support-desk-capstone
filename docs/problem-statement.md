# Problem statement and requirement traceability

NextLeap Applied Generative AI Bootcamp, Cohort 7: **AGB C7 Capstone, "The Support Desk"**. Product: **Groww** with **HDFC Mutual Fund** schemes (the product picked in Milestone 1).

## The problem
Two teams solve halves of the same problem and neither sees the other half.

- **Support** answers the same fee question dozens of times a month, writing it fresh each time and sometimes getting it wrong.
- **Product** reads a review dashboard that says "pricing confusion is up" without saying *which* fee, or what support has been telling people about it.

The missing piece is data neither team has in one place: **what the official documents say, what users are confused about, and how often**. This project puts those three sources behind one system, with a human approving every write.

## What was built
A deployed web application with two loops and a connection between them.

| Loop | Input | Output | Human gate |
|---|---|---|---|
| **Weekly loop** | Reviews CSV (newest 7 days) | ≤5 themes, top 3, the recurring fee confusion, a pulse (≤250 words) and a fee explainer (≤6 bullets, 2 official links, last-checked date) | Two separate approvals: doc append, email draft |
| **Response loop** | Queue of user questions | Per question: cited reply draft (≤3 sentences) and an internal routing note, from three agents in parallel, an orchestrator and a reviewer | Approve / edit / reject each draft |
| **Connection** | Both | (1) A question asked ≥5 times in the week appears in the pulse. (2) The approved explainer becomes the canonical answer the response loop reuses. | Reuse starts only after a human approves the explainer |

## Traceability: every requirement of the brief and where it lives

| # | Requirement (brief) | Implemented in | Evidence |
|---|---|---|---|
| 1 | Ingest reviews CSV, ≤5 themes, top 3 | `weekly.build`, `pipeline.cluster_reviews` | `feasibility.md` rows 5–6 |
| 2 | Pull the recurring fee/charge confusion | `pipeline.detect_fee_issue` | README "fee issue"; Weekly page |
| 3 | Pulse ≤250 words, supporting quotes, 3 actions | `weekly._pulse` (auto-trims, then checked) | `feasibility.md` row 7 (198 words) |
| 4 | Fee explainer ≤6 bullets, 2 official links, last checked | `weekly.build_explainer` (per-bullet [1]/[2] markers) | `feasibility.md` row 8 |
| 5 | Both through the approval gate before doc append and email draft | `Service.run_weekly` creates **pending** actions; `decide_action` | `edit_correctness.md` |
| 6 | Queue of incoming questions | `data/questions.csv`, `Service.seed`, `/queue` | Queue page |
| 7 | Three agents in parallel, orchestrator, reviewer | `desk.Desk._parallel`, `agents.py`, `orchestrator.py`, `reviewer.py` | Ticket page timing panel |
| 8 | Reply draft + citation + routing note; approve/edit/reject | `Service.edit_draft`, `decide_ticket` | `edit_correctness.md` |
| 9 | Same question ×5 in a week shows up in the pulse | `Service.question_groups` → `weekly.build(signals)` | `feasibility.md` LINK 1 |
| 10 | Weekly explainer becomes the canonical answer the response loop reuses | `Service._register_canonical`, `FactsAgent(canonical=…)` | `feasibility.md` LINK 2; `/canonical` |
| 11 | Facts-only, no advice/buy/sell/returns, enforced in code | `ComplianceAgent`, `reviewer.review`, `weekly.clean_ok` | `grounding_compliance.md` |
| 12 | No PII anywhere (dataset, UI, logs, agent state) | `pii.redact` first line of `Desk.submit` and weekly ingest; `call_tool` re-scan | `grounding_compliance.md` last two rows |
| 13 | Queue view with drafts, citations, reviewer flags | `templates/queue.html` | screenshot 02 |
| 14 | Weekly pulse view: themes, quotes, counts | `templates/weekly.html` | screenshot 03 |
| 15 | Sources panel with last-checked dates | `/sources`, `data/source_checks.json` | screenshot 08 |
| 16 | Approval screen: exactly what will be written and where | `/approvals`, per-ticket and weekly "Exact content" | screenshot 04 |
| 17 | See the canonical explainers being reused | `/canonical` | screenshot 06 |
| 18 | Every factual claim has one source link from the M1 corpus | reviewer citation checks; `corpus.ALLOWED_URLS` | `grounding_compliance.md` claims |
| 19 | Public sources only | `SOURCES.md` | — |
| 20 | Corpus can't answer → say so and name what was searched | `corpus.Corpus.search` + `validate_output` | `grounding_compliance.md` row 16 |
| 21 | Every theme traces to review ids; every count states its window | theme rows carry `review_ids` + `window` | Weekly page |
| 22 | Nothing written/sent without approval of that specific action | per-action `ApprovalGate`; `mcp_layer.call_tool` | `edit_correctness.md` |
| 23 | Drafts ≤3 sentences, pulse ≤250 words, explainer ≤6 bullets | reviewer / `weekly` checks | all three evals |
| 24 | Eval: feasibility | `evals/run_evals.py::feasibility` | 13/13 |
| 25 | Eval: correctness of edits (diff state before/after) | `::edit_correctness` using `Service.snapshot` + `diff` | 16/16 |
| 26 | Eval: grounding and compliance (15 claims, uncovered, advice/returns/PII, both loops, rephrased, repeated, logs clean) | `::grounding_compliance` | 26/26 |
| 27 | README (architecture, setup, sources, gate, loop connection, fee issue, evals, limits) + CSV sample + 5 samples + doc entry + email draft + eval results | `README.md`, `outputs/samples/`, `data/reviews_sample.csv`, `outputs/evals/` | — |
| 28 | Working prototype link | Render (`render.yaml`, `Dockerfile`) | README |

## What the graders asked
*Can you design a system where three data sources answer one question? Do you know where a language model stops being reliable, and does your system say so out loud? Can you build a gate a compliance team would trust? Can you explain why you drew the lines where you did?* — answered in README "Design decisions" and [compliance-model.md](compliance-model.md).
