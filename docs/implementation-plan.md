# Implementation plan (as built)

| Item | Decision |
|---|---|
| Goal | One deployed system running the weekly (product) loop and response (support) loop for Groww, joined by two connections, with human approval on every write |
| Stack | Python 3.11, Flask, scikit-learn (TF-IDF, LSA, KMeans), pandas, gunicorn |
| LLM | None required. Optional Groq (`llama-3.3-70b-versatile`) can rephrase replies; the reviewer checks them like any other draft. Untested |
| Retrieval | TF-IDF + intent/scheme matching over 74 sentence-level facts from 16 public pages |
| Persistence | In memory + local files under `outputs/`; no database |
| Deploy | Render (free) or Docker; GitHub Actions for tests, evals and the weekly schedule |

## Phases
1. **Inventory and base choice.** Compare Milestones 1–3; choose M3 (agents, reviewer, PII gate, approval gate) as the base; pull the weekly pipeline from M2 and the corpus from M1.
2. **Data.** Prepare the 8,629-row Play Store export (`scripts_prepare.py`): redact, assign stable review ids `R1…R8629`. Write a 38-question demo queue.
3. **Weekly loop.** Window loading, theme review ids, quote filter, per-bullet citations, word and bullet caps, nine output checks, fee trend.
4. **Service layer.** One `Service` owning both loops, per-action gates, topic keys, canonical store, `snapshot()`.
5. **The connection.** Question counts → pulse; approved explainer → canonical → Facts agent.
6. **UI.** Overview, Queue, Ticket, Weekly, Approvals, Sources, Canonical, Evals, Written files.
7. **Evals.** Three evaluations with saved results; fix what they find.
8. **Docs and deploy.** README, `docs/`, Docker, Render, GitHub Actions, n8n.

## Decisions that changed during the build
- **A bug found by the evals:** return-figure questions ("what is the 5 year return of…") were answered "not covered" instead of refused → added request patterns to the Compliance agent.
- **A bug found by the evals:** "charged twice" was counted as brokerage but missed the canonical lookup → topic detection now uses the corpus intents, so counting and reuse agree.
- **A relevance bug found in the samples:** a brokerage question received the DP-charges bullet because "sold shares" out-voted "brokerage" → generic words are removed from bullet matching and the eval now asserts the reused bullet mentions the fee.
- **A test written wrong, not the code:** a "re-draft" step expected too few changed fields.

## Milestone lineage
See [milestone-lineage.md](milestone-lineage.md).

## Out of scope (deliberately)
Real Google Docs/Gmail connections, authentication, multi-user queues, a database, semantic clustering of questions, live scraping of the source pages.
