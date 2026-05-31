# track-d-resumable-agents.md — Cortex Agents Run + Threads as a Code-UI alternative

> **Tier-1 planning doc.** Created 2026-05-31. Successor-window briefing for
> **Track D**: bypass the Cortex Code UI's "fresh session" defect by moving
> repeat workflows onto a **server-side, thread-persistent Cortex Agent**.
>
> **What this doc is for.** The owner asked "what's the quickest way to get
> up and running, where would I type, is there more effort as we add skills /
> web_search / cloud agents?" This doc is the answer + a phased plan.
>
> **What this doc is NOT.** Not yet APPLIED. No agent exists in this account.
> No `CREATE AGENT` has run. Owner sign-off + a build session required before
> any DDL.
>
> **Read order for the next window:** AGENTS.md → this doc → `cortex-ai-agents-playbook.md`
> (deep reference) → `connection-resilience.md` §4 (the "why" — symptom
> Track D fixes). Do NOT re-read the design history; trust the summaries.

---

## 0. Critical naming clarification (read first)

The Snowflake "agent" word is overloaded. **Three different things**, easy to
confuse:

| Name | What it is | Relevance to Track D |
|---|---|---|
| **Cortex Code (Snowsight)** | The chat-coding agent in this Snowsight panel right now. **No conversation persistence** — each window is fresh. THIS is what's stunning on connection blips. | The **defect we are fixing**. |
| **Cortex Code "Cloud Agents"** (private preview, April 2026) | A managed sandbox that runs the Cortex Code agent loop *in the cloud* instead of in a local CLI. Still the same Code UI; still ephemeral. ([source](https://www.snowflake.com/en/blog/cortex-code-governed-agent-data-stack/)) | **Not what Track D is.** Cloud Agents = same Code experience, different host. They do NOT solve the fresh-session problem. Owner conflation risk — flag if discussion drifts. |
| **Cortex Agents** (the OBJECT type — `CREATE AGENT`) | User-authored, IaC-able agents you build with `CREATE AGENT … FROM SPECIFICATION`. Have **threads** (server-side persistent conversation). REST API + SQL + Snowsight playground. ([source](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)) | **THIS is Track D.** Threads = the resumability we want. |

When in doubt: **if it has a `thread_id`, it's a Cortex Agent (the OBJECT).**
If it's the Snowsight panel you typed your prompt into, it's Cortex Code.

---

## 1. Quickest path to "first working agent" — 30-minute target

The fastest path is **NOT** SQL or REST. It's the Snowsight UI's built-in
playground.

### Step-by-step (verified against [Configure and interact with Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage))

1. **Snowsight → AI & ML → Agents → Create agent.** ([Flexera](https://www.flexera.com/blog/finops/snowflake-intelligence/) confirms the UI path.)
2. Give it a name (e.g. `ARTWORK_DB.AGENTS.HELLO_AGENT`), instructions
   ("You are a senior Data Engineer mentor for the artwork-db learning repo"),
   and pick an orchestration model (start with `claude-4-sonnet` — middle of
   the cost curve).
3. **No tools yet.** The agent is "bare" — just instructions + a model.
4. Save. Snowsight opens the **agent playground** — a chat box. **This is
   "the comment box" the owner asked about.** Type a prompt; the agent
   responds. Conversation persists in a server-side thread.
5. Close the tab. Reopen. The thread is still there; pick up where you left
   off. **The defect is fixed.**

What you've now learned in 30 min:
- Where the chat UI lives (AI & ML » Agents » `<agent>` » Playground).
- That threads survive tab close — concretely demonstrating the resumability.
- The shape of the agent spec (you'll see the SQL the UI generates).

What you HAVEN'T done yet (and that's fine for "hello world"):
- No tools (Cortex Analyst, Cortex Search, web_search). Bare LLM only.
- No IaC (the UI-created agent isn't in version control).
- No REST/SQL programmatic access path.

### Prerequisites — verify before starting

- ✅ Account-level Web Search toggle is ON (already done 2026-05-30; AGENTS.md item #6).
- ⚠ Account must be Cortex-Agents-enabled. **Verify.** `SHOW AGENTS IN ACCOUNT;`
  succeeds → enabled. If error → a feature flag is needed; raise with Snowflake.
- ⚠ Role for create. The default agent location is
  `SNOWFLAKE_INTELLIGENCE.AGENTS.<name>` ([reference quickstart](https://github.com/Snowflake-Labs/sfguide-getting-started-with-cortex-agents)),
  which requires the `SNOWFLAKE_INTELLIGENCE_ADMIN` database role or
  ACCOUNTADMIN to write into. We are ACCOUNTADMIN — fine for a smoke test.
- ⚠ Compute warehouse. Agent orchestration uses a warehouse for tool
  execution + observability writes. `COMPUTE_WH` is fine for hello-world.

---

## 2. The owner's three specific questions — answered

### Q: "Where would I type into a comment box?"

**Answer: Snowsight → AI & ML → Agents → click the agent → playground.** Same
UX as Cortex Code's panel: chat input at the bottom, message history above.
The crucial difference: messages are stored in a server-side `thread`
(addressable by `thread_id`), so closing the tab doesn't lose context.

Programmatic alternatives (later, when scripts are needed):
- `POST /api/v2/cortex/agent:run` — REST. Pass `thread_id` to continue.
- `SNOWFLAKE.CORTEX.AGENT_RUN(...)` — SQL UDTF wrapper. Returns streaming
  response rows. Useful for in-warehouse orchestration.

### Q: "Is there more effort as we add skills, web_search, and cloud agents?"

**Yes for tools (each adds real work). Web_search is the cheapest add. "Skills"
in the Cortex Code sense don't transfer directly. "Cloud Agents" is a
different product — see §0.**

| Add this… | Effort | Cost dimension | Sources |
|---|---|---|---|
| **Bare LLM agent** (no tools) | Trivial — UI form + 30 s | Tokens only (orchestration model). claude-4-sonnet ≈ 1.95 AI Credits/1M tokens; claude-4-opus ≈ 12. | [pricing breakdown](https://medium.com/towards-data-engineering/breaking-down-snowflakes-ai-pricing-overhaul-credits-caching-and-cost-strategy-bde56f48f53f) |
| **Add `web_search` tool** | Trivial — one tool_spec block in the agent YAML; account toggle already ON. | Tokens for the search round-trip; no separate web-search billing line beyond tokens. | `cortex-ai-agents-playbook.md` §4 |
| **Add `cortex_analyst_text_to_sql` tool** | Medium — requires a **Semantic View** to point at. We don't have one yet. ~half-day to author a small one over Bronze. | Tokens for SQL gen + warehouse credits to execute the SQL. | [Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst); [Cortex Agents tools](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents) |
| **Add `cortex_search` tool** | Medium-high — requires creating a **Cortex Search Service** over an indexed column first. Index build = warehouse credits; serving = standalone $/GB-month. | Build credits + serving fee + per-query tokens. **Most-expensive tool** to wire up. | [Cortex Search costs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-costs) |
| **Add `generic` tool / external function** | High — implement a UDF or external function the agent calls. Open-ended scope. | Whatever the function costs + tokens. | [CREATE AGENT spec](https://docs.snowflake.com/en/sql-reference/sql/create-agent) |
| **"Skills" in the Cortex Code sense** | **Don't transfer directly.** Cortex Code skills are a different abstraction (Snowsight-bundled UX flows like `pdf`, `xlsx`, `dcm`). For Cortex Agents, the equivalent is **tools** + an **MCP server** ([Snowflake-managed MCP](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp)). | Effort = author each MCP tool (similar work to `generic` tool). | [Cortex Agents MCP](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp) |
| **"Cloud Agents"** | **Not relevant to Track D — see §0.** This is Cortex *Code*'s cloud sandbox, not the Agent OBJECT. It does NOT add thread persistence. If the owner means "I want the Code UI experience but server-hosted," that's Cloud Agents (private preview); request access via Snowflake. | n/a | [Snowflake blog](https://www.snowflake.com/en/blog/cortex-code-governed-agent-data-stack/) |

**Headline cost note:** every tool you add multiplies the per-turn token
budget. Cortex Search adds *standing* serving cost (per-GB-indexed-per-month)
even when the agent isn't running. Web Search is the cheapest tool to add.

### Q: "What's the quickest path to up-and-running?"

**See §1.** UI-create a bare agent, chat in the playground, prove
thread-persistence by closing/reopening the tab. 30 min. Then decide whether
to invest in tools.

---

## 3. Phased plan — three options, owner picks

The phases are **ordered by commitment**, not time. Each phase is a complete
stopping point.

### Phase A — Smoke test (1 session, ~1 hour)

Goal: prove the playground UX + thread persistence solve our problem for at
least one workflow.

1. UI-create `ARTWORK_DB.AGENTS.HELLO_AGENT` (bare; instructions only).
2. Chat with it. Close tab. Reopen. Verify thread persists.
3. Try one repeat workflow we currently do in Cortex Code — e.g. "audit infra
   files for V/R/B references" (gated item #1 in AGENTS.md).
4. Honest assessment: is the UX *good enough* without our skills? If no,
   stop and invest the build effort in connection-resilience #1 (the lease)
   instead.

**Decision gate:** continue to Phase B only if Phase A's UX clears the bar.
**Cost ceiling:** <1 USD in tokens; no Cortex Search, no Analyst.

### Phase B — IaC-ify + add web_search (1-2 sessions)

Goal: lift the agent into version control; add the cheapest tool.

1. **`infrastructure/create_agents.sql`** + **`drop_agents.sql`** pair —
   the agent spec as `CREATE OR REPLACE AGENT … FROM SPECIFICATION $$ … $$;`
   ([syntax reference](https://docs.snowflake.com/en/sql-reference/sql/create-agent)).
2. Wire into `scripts/manifest.txt`. Drop pair too (orchestrator pairs them).
3. Grants: agent execution privileges to the right role
   (`CORTEX_USER` database role at minimum; `USAGE` on the agent). Document
   the contract in `bootstrap.py`'s privilege preflight.
4. Add the `web_search` tool to the spec. Account toggle is already ON;
   per-agent enablement is just a `tool_spec` block.
5. Test: agent answers "what's the latest Met museum API version?" via
   live web search.

**Decision gate:** continue to Phase C only if web_search visibly improves
agent answers AND total token spend stays acceptable (<5 USD/week as a
soft ceiling).

### Phase C — Tooled agent (multiple sessions)

Goal: real value — agent can answer questions about *our* data.

1. Author the first **Semantic View** over `ARTWORK_DB.BRONZE` (probably
   over `RAW_MET_OBJECTS` + the new control tables). This is itself a
   real learning task — see `engineering-playbook.md` for semantic-view
   best practices.
2. Add `cortex_analyst_text_to_sql` tool to the agent spec.
3. Test: "How many Met objects are awaiting enrichment?" → agent generates
   SQL via Cortex Analyst → executes → returns answer with citations.
4. **Optional:** add Cortex Search over a text-rich Bronze column (e.g.
   artwork descriptions). This is the most expensive add — defer until
   there's a concrete question Cortex Search uniquely answers.

**Decision gate:** evaluate whether the agent has displaced Cortex Code
for any meaningful workflow. If yes → expand to Section-C build phases.
If no → keep Cortex Code as primary, agent as a specialty tool.

### Phase D (later) — Programmatic resumable runner

Goal: scriptable agent calls from `make` / a Mac CLI.

1. Build a small Python or bash driver around `agent:run` that takes a
   `thread_id` + a prompt + a `run_id` (matching `BRONZE.RUN_CONTROL`'s
   convention).
2. The driver writes checkpoints to `RUN_CONTROL` after each tool call,
   so an interrupted run resumes from the last good message.
3. Wire into `make` for `apply-with-agent`, `audit-with-agent`, etc.

This is the full Track-D vision: **the work survives the session, every
time.** Far beyond hello-world; consider only after Phase B has paid off.

---

## 4. Cost guardrails (non-optional)

Token billing is opaque without observability. Set these up FROM PHASE A:

1. **Resource monitor on the orchestration warehouse** (warning at 5
   credits/day). Doesn't bound token cost but bounds compute around it.
2. **Read `SNOWFLAKE.LOCAL.AI_OBSERVABILITY_EVENTS`** after every agent
   chat in Phase A; learn what 1 turn costs in tokens.
3. **Cortex Search standing cost**: only add Cortex Search after computing
   $/GB-month × index size. Document the estimate in `met-deepdive.md`
   under a new `COST-AGENT-XX` ID before building.
4. **Pick claude-4-sonnet (or smaller) over claude-4-opus** unless there's
   a specific reason. ~6× cost difference.

---

## 5. Risks / `⚠ unverified` (next window check)

1. **`SHOW AGENTS IN ACCOUNT;` not yet run** — feature availability in
   account `pa37992` unverified. Run as the first command of the build session.
2. **Default agent location is `SNOWFLAKE_INTELLIGENCE.AGENTS.<name>`**
   ([quickstart source](https://github.com/Snowflake-Labs/sfguide-getting-started-with-cortex-agents)),
   not in `ARTWORK_DB`. Decide: own the schema in `ARTWORK_DB.AGENTS`
   for IaC clarity, or accept the default for ecosystem alignment? Both
   work; IaC-clarity argues for `ARTWORK_DB.AGENTS`.
3. **Threads are not free**. Each turn writes to observability. Quantify
   in Phase A.
4. **Tool security**. The agent runs with the role it was created under,
   AND can be invoked by other roles with `USAGE`. Define grants
   *minimally* — don't grant `USAGE` to `PUBLIC`. Add a row to AGENTS.md
   gated items if creating a new role for agent invocation.
5. **MCP / "skills" parity**. The Cortex Code skills (e.g. `dbt-projects-on-snowflake`,
   `data-governance`) do NOT auto-port to a Cortex Agent. If the owner's
   real ask is "I want my Cortex Code skills available in this thread-
   persistent agent," that requires authoring each skill as an MCP tool —
   substantial work. Surface this trade-off explicitly to the owner before
   Phase C.

---

## 6. Concrete first-action checklist for the next window

```
# 1. Single-instance + state checks (per AGENTS.md discipline)
bash scripts/check.sh
bash scripts/checkpoint.sh 2026-06-XX-trackD start in_progress "Phase A smoke test"

# 2. Verify Cortex Agents is enabled in this account
#    (run from a SQL worksheet — DO NOT inline-DDL anything beyond this read)
SHOW AGENTS IN ACCOUNT;

# 3. If enabled — UI-create HELLO_AGENT in Snowsight (AI & ML » Agents » Create)
#    DO NOT write CREATE AGENT SQL yet; learn the UX shape first.

# 4. Chat in the playground. Close tab. Reopen. Confirm thread persists.

# 5. Decision: Phase B or stop. Checkpoint:
bash scripts/checkpoint.sh 2026-06-XX-trackD phase-A-eval done "<verdict>"
```

**Owner sign-off required before:** any `CREATE AGENT` SQL, any new
`infrastructure/*.sql` file, any grant to a non-admin role. (AGENTS.md rules.)

---

## 7. Cross-references

- **Why this track exists:** `docs/context/connection-resilience.md` §4
  (the resumable-agent track). The "Cortex Code starts fresh each session"
  defect is documented there with sources.
- **Deeper Cortex AI/Agents technical reference:**
  `docs/context/cortex-ai-agents-playbook.md` (the long-form playbook;
  predates this doc but covers tool semantics + observability).
- **Web Search account-toggle history:** AGENTS.md gated item #6.
- **Existing checkpoint substrate:** `BRONZE.RUN_CONTROL`,
  `scripts/checkpoint.sh` (Phase D builds on this).
- **Cortex Code (the thing we're augmenting, not replacing):**
  [Cortex Code in Snowsight docs](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight),
  [Cloud Agents announcement](https://www.snowflake.com/en/blog/cortex-code-governed-agent-data-stack/).
