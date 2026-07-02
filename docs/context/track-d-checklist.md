# track-d-checklist.md — Cortex Agents growth checklist (flexible, not declarative)

> **A guideline, not a plan.** Created 2026-05-31. Companion to
> `docs/context/track-d-resumable-agents.md` (the "what + why" planning doc).
> This doc is the "how, roughly, while staying open to surprise."
>
> **Read posture:** challenge every box. If a step turns out to be wrong for
> our project, **strike it out and write what you did instead** — don't
> pretend the original was right. Every checked box should record *what
> actually happened*, not what we predicted would happen. The whole point of
> Track D is that we stop wasting cycles on connection issues and **start
> shipping data work** (Met extraction → Bronze → dbt). If a checkbox in
> this doc costs more than 30 min and isn't moving us toward data, stop
> and ask whether it's load-bearing.
>
> **Prime directive:** the cheapest agent that is good enough beats the most
> elegant agent that takes a week.

---

## Mental model

Three concentric goals, smallest first:

```
[ minimum: thread-persistent chat that survives a tab close ]
    └── [ useful: agent can answer real questions about our data ]
            └── [ leveraged: agent can DO work (apply DDL / run dbt / extract) ]
```

We hit goal 1 in ~30 min if the account is enabled. Goal 2 needs a Semantic
View (real but bounded work). Goal 3 needs tools + scripting + thought about
authorization. **It is fine — and probably correct — to stop after goal 2 for
weeks.** Most data-engineering pain is goal-2-shaped.

---

## Stage 0 — Sanity (minutes, before any creation)

Don't skip these. Each is a 10-second SQL or page-load.

- [ ] `bash $(TOOLKIT_DIR)/check.sh` shows exactly one `cortex_code_snowsight` session.
- [ ] `SHOW PARAMETERS LIKE 'ABORT_DETACHED_QUERY' IN ACCOUNT;` returns `true`
      (proves rec #2 is live).
- [ ] `SHOW ALERTS IN ACCOUNT;` lists `CORTEX_FORK_ALERT`, scheduled (proves
      rec #3 is live).
- [ ] `SELECT * FROM ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS` is empty (or
      noted: any rows = a fork happened; investigate before continuing).
- [ ] `SHOW AGENTS IN ACCOUNT;` succeeds (proves Cortex Agents is enabled).
      If this errors → STOP, file with Snowflake support. Track D is dead
      until enabled.

> **Challenge prompt:** if any of the above fails or surprises you, the
> assumption stack from this session may have rotted. Read the latest
> `session-3-progress-log.md` entry before deciding whether to proceed.

---

## Stage 1 — Hello, Agent (target: 30 min, ceiling: 2 hr)

Goal: prove threads persist across tab-close. Nothing more.

- [ ] Snowsight → AI & ML → Agents → **Create agent** (UI, not SQL).
- [ ] Name: `HELLO_AGENT` in whatever default schema the UI offers
      (probably `SNOWFLAKE_INTELLIGENCE.AGENTS.HELLO_AGENT`). **Don't fight the
      default location yet** — that's Stage-2 IaC work.
- [ ] Instructions: 1–3 sentences. "You are a senior Data Engineer pairing
      with the owner on the `artwork-db` learning repo." That's enough.
- [ ] Model: `claude-4-sonnet` (mid-cost). **Note the cost** — if it's
      significantly different from what `track-d-resumable-agents.md §2`
      estimates, update both docs.
- [ ] **No tools.** Bare LLM only.
- [ ] Send 3 messages in the playground.
- [ ] **Close the browser tab.** Reopen Snowsight → AI & ML → Agents →
      `HELLO_AGENT`. Confirm the thread is still there.
- [ ] Send a 4th message that references something from messages 1-3. Confirm
      the agent recalls.

**Decision gate (write the answer):**
- Did thread persistence visibly fix the "fresh session" pain? ___
- Was the playground UX better, worse, or same as Cortex Code for chat? ___
- Total token spend for this stage: ___ (read `AI_OBSERVABILITY_EVENTS`).
- Continue to Stage 2? Yes / No / Pause to think.

> **Challenge prompt:** if Stage 1 didn't actually feel better than Cortex
> Code, **STOP**. Track D is wrong for our problem. Reopen the lease (rec #1)
> conversation instead. That is a real possibility — don't sunk-cost into
> Stage 2.

---

## Stage 2 — Grounded in our data (target: 1–2 sessions, NOT a sprint)

Goal: agent can answer questions about Met data we've already loaded.

This is also where the project's data work lives. Stage 2 IS data work — it
forces us to author the first Semantic View, which is itself a Track-1
("Met data") deliverable. Don't think of this as "Track D overhead";
think of it as "Track D + Track 1 in one motion."

### 2a. Pick the smallest useful Semantic View

- [ ] Decide: which Bronze table(s)? Probably just `RAW_MET_OBJECTS` to start.
      `MET_ENRICHMENT_CONTROL` and `MET_CSV_SNAPSHOT` add complexity for
      questionable analytical value at this stage.
- [ ] Decide: how many dimensions? Aim for ≤5 (e.g. department, period,
      classification, isPublicDomain, accession year). Don't model the world.
- [ ] Decide: how many measures? `count(*)` is fine for v1.
- [ ] Author `infrastructure/create_semantic_views.sql` (+ drop pair). Pattern:
      `CREATE SEMANTIC VIEW … FROM …` — see `engineering-playbook.md`.
- [ ] Wire into `manifest.txt` (after `create_bronze_views.sql`).
- [ ] Apply via `make infra`. Confirm in Snowsight → AI & ML → Semantic Views.

> **Challenge prompt:** if this takes more than one session, the Semantic
> View is too ambitious. Cut it down ruthlessly. v1 should be embarrassingly
> small.

### 2b. Wire the agent to the view

- [ ] In the playground, edit `HELLO_AGENT` → add tool → `cortex_analyst_text_to_sql`
      → point at the new Semantic View.
- [ ] Ask: "How many Met objects do we have?" — agent should generate SQL,
      execute, return a number.
- [ ] Ask 5 more questions a real user would ask. Note which the agent
      handles well, which it fumbles, which need Semantic-View tweaks.
- [ ] Iterate the Semantic View based on what fumbled. **This iteration loop
      is the actual work** — don't rush it.

### 2c. (Optional) IaC-ify the agent

- [ ] If — and only if — you want the agent to be reproducible across
      environments, write `infrastructure/create_agents.sql` mirroring what
      the UI built. Owner sign-off + manifest wire + `make infra`.
- [ ] If you DON'T do this, that's fine. The UI-defined agent is recoverable
      from your account; just document its existence in `file-map.md`.

**Decision gate (write the answer):**
- Has the agent answered a question that was painful in plain Cortex Code? ___
- Token + warehouse cost so far: ___ (vs. Stage-1 baseline).
- Has any `CORTEX_FORK_INCIDENTS` row appeared during this stage? ___ → if
  yes, surface to the owner; rec #1 conversation reopens.
- Continue to Stage 3? Yes / No / Pause for actual data work.

> **Challenge prompt:** at this point we've burned a real amount of
> learning-time on tooling. **Is shipping more important than continuing
> Track D right now?** If Met extraction or dbt is overdue, pause Track D
> at Stage 2 (it's already useful) and come back later.

---

## Stage 3 — Tools that *do* work (open-ended; gate on owner pain)

Goal: agent can apply small DDL changes / run dbt / inspect ingestion logs
without round-tripping to a CLI.

This is where Track D starts displacing Cortex Code for real workflows.
**Only enter this stage if Stage 2 demonstrably saved time on the Met data
build.** Otherwise it's premature.

Possible tools (pick 1, ship it, then decide on the next):

- [ ] `web_search` tool — cheapest add. Per-agent enable in spec; account
      toggle already on. Useful for "what does this Met API field mean."
- [ ] A `generic` tool (or MCP server tool) calling a stored procedure that
      runs a *bounded* dbt operation (e.g. `dbt run --select +my_model`).
      **High blast radius — owner sign-off mandatory before authoring.**
- [ ] A `cortex_search` service over Met object descriptions. **Real money** —
      verify $/GB-month before building. Defer if the questions can be
      answered with `cortex_analyst` alone.
- [ ] An MCP tool that calls `$(TOOLKIT_DIR)/check.sh` or `$(TOOLKIT_DIR)/checkpoint.sh`,
      so the agent participates in the run-control trail. (This is where
      Track D starts to subsume the Track-1 visibility suite.)

> **Challenge prompt:** every tool added is permanent surface area. Add one,
> use it for a week, only then add the next. If you're adding two in one
> session, you're scope-creeping.

---

## Stage 4 — Programmatic resumable runner (deferred indefinitely)

Goal: scriptable agent calls from `make` / a Mac CLI; checkpointed.

- [ ] Build a small Python or bash driver around `agent:run` taking a
      `thread_id` + a `run_id`.
- [ ] Driver writes to `BRONZE.RUN_CONTROL` after each tool call.
- [ ] Wire into `make` for repeat workflows.

**Don't enter Stage 4 until Stage 3 has at least 2 tools you actually use.**
This is the full Track-D vision. It is also the easiest place to over-
engineer; resist.

---

## Things that will probably surprise you (record them here)

A blank section by design. As you discover things that don't fit the above,
add them as bullets with a date. The doc is more valuable as a journal of
*what actually happened* than as a list of *what was supposed to happen*.

- _empty_

---

## Hard stops (these short-circuit the whole checklist)

If any of these become true, **stop Track D, document the situation in
`session-3-progress-log.md`, and replan.**

- `SHOW AGENTS IN ACCOUNT;` errors (Cortex Agents not enabled).
- `BRONZE.CORTEX_FORK_INCIDENTS` accrues 3+ rows in a single week — scenario B
  is happening regularly; Track D might be too slow to build relative to
  the urgency. Consider rec #1 (the lease) in parallel.
- Token spend on agent + Cortex Search exceeds an owner-defined cap (set
  this BEFORE Stage 2 — see `track-d-resumable-agents.md §4`).
- A new Snowflake feature renders this whole approach obsolete (e.g. Cortex
  Code Snowsight ships true session persistence). Check release notes
  monthly; if it lands, archive Track D.

---

## What this doc is NOT

- A timeline. There are no dates.
- A commitment. Any stage can be paused, cut, or reordered.
- A spec. The agent's actual instructions/tools live in the agent OBJECT,
  not here.
- A replacement for `track-d-resumable-agents.md`. That doc explains *why*;
  this one is *how, roughly*.

---

## Cross-references

- `docs/context/track-d-resumable-agents.md` — the planning doc; explains
  Cortex Code vs Cloud Agents vs Cortex Agents OBJECT, costs, phases.
- `docs/context/connection-resilience.md` — the symptom this fixes; recs
  #2 + #3 already applied.
- `docs/context/cortex-ai-agents-playbook.md` — deeper Cortex Agents
  technical reference.
- `docs/context/engineering-playbook.md` — Semantic View patterns (needed
  for Stage 2).
- `BRONZE.CORTEX_FORK_INCIDENTS` — the alert audit table; check during
  every stage for evidence of new dual-instance events.
