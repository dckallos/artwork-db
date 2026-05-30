# cortex-ai-agents-playbook.md — optimizing Cortex AI & Cortex Agents

> **Tier-1 REFERENCE doc (companion to `engineering-playbook.md`).** Same contract:
> a reference tool you return to, not your primary learning tool. It catalogs the
> ways to extend/optimize Cortex AI and Cortex Agents on this account, and answers
> the standing question: *why is `web_search` returning nothing, and how do I turn
> it on?* Grounded with cited Snowflake doc URLs.
>
> Account context: `pa37992`, role `ACCOUNTADMIN` (you can enable account-level
> features yourself).

## Why this doc exists

While grounding the engineering playbook, the agent's `web_search` tool returned
no results. The cause is **not** an outage: Snowflake's **Web Search is an
account-level feature that an ACCOUNTADMIN must explicitly enable** before any
agent/tool can use it. That single finding opened a broader question you asked —
*"what are all the ways we can optimize Cortex AI and Cortex Agents?"* — which this
doc answers.

---

## 1. The Cortex Agent tool menu (what you can plug in)

A Cortex Agent plans, calls **tools**, reflects, and responds. The available tools:

| Tool | Purpose | Resource you point it at |
|---|---|---|
| **Cortex Analyst** | Text-to-SQL over **structured** data | a **semantic view** (managed MCP requires a semantic *view*, not a semantic *model*) + warehouse |
| **Cortex Search** | Retrieval over **unstructured** text | a Cortex Search service |
| **Web Search** | Real-time public web results (Brave Web Search API) | account-level enablement (see §4) |
| **SQL execution** | Run governed SQL | warehouse + caller/owner rights |
| **`data_to_chart`** | Turn results into charts | n/a |
| **Custom tools** | Your own logic | a **UDF** or **stored procedure** (or an external API via the proc) |

**Why it matters for this repo:** once Silver/Gold exist, a Cortex Analyst tool
over a **semantic view** of `GOLD.open_access_artworks` lets you (or an app) ask
"how many public-domain Monets are on display?" in natural language — the
data-engineering tracks are what make a *good* semantic view possible.

**Sources:** Cortex Agents
(https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents).

---

## 2. Snowflake-managed MCP server (expose your tools to any MCP client)

Model Context Protocol (MCP, GA; Snowflake supports revision 2025-11-25) lets
external AI agents/clients securely discover and invoke Snowflake tools **without
you deploying separate infrastructure**. Create an `MCP SERVER` object listing
tools; clients authenticate (OAuth recommended) and invoke them under RBAC.

```sql
CREATE OR REPLACE MCP SERVER ARTWORK_MCP
  FROM SPECIFICATION $$
tools:
  - name: "artwork-analyst"
    type: "CORTEX_ANALYST_MESSAGE"
    identifier: "ARTWORK_DB.GOLD.SV_OPEN_ACCESS"   -- a semantic VIEW
    description: "Natural-language analytics over Gold OpenAccess artworks"
    title: "Artwork Analyst"
  - name: "run-sql"
    type: "SYSTEM_EXECUTE_SQL"
    description: "Governed ad-hoc SQL"
$$;
```

**Supported tool types:** `CORTEX_SEARCH_SERVICE_QUERY`, `CORTEX_ANALYST_MESSAGE`,
`SYSTEM_EXECUTE_SQL`, `CORTEX_AGENT_RUN`, `GENERIC` (UDF/proc).

**Best-practice / safety notes (from the docs):**
- Use **OAuth**, not hardcoded tokens; if using a PAT, give it a **least-privileged
  role**.
- Access to the MCP server ≠ access to its tools — **grant each tool explicitly**.
- Avoid recursive tool loops; Snowflake caps recursion at **10 invocations**.
- Use **hyphens, not underscores** in MCP connection hostnames.
- Vet third-party MCP servers (tool-poisoning / tool-shadowing risk).

**Sources:** Snowflake-managed MCP server
(https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp).

---

## 3. Orchestration & cost controls (tune the agent itself)

- **Orchestration model:** `orchestration: auto` (let Snowflake pick) or pin one
  (e.g. `claude-4-sonnet`). `auto` is the low-maintenance default.
- **Instructions:** planning/response instructions shape behavior and output style.
- **Budget constraints:** `OrchestrationConfig.budget` caps **seconds** and
  **tokens** per request — your primary guardrail against runaway/expensive agent
  loops. Set these deliberately.
- **Monitor / evaluate:** track metrics and run evaluations after deployment
  (native Snowflake features) to iterate on accuracy and cost.
- **Access control:** `SNOWFLAKE.CORTEX_USER` (all Cortex) or
  `SNOWFLAKE.CORTEX_AGENT_USER` (Agents only); grant `USAGE` on db/schema/agent to
  let another role edit.

**Sources:** Cortex Agents
(https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents).

---

## 4. Web Search — why it's off, how to enable it, and the IaC decision

### 4a. Enable it (account-level, ACCOUNTADMIN — UI toggle)

Per the docs, the only way to enable web search is a Snowsight UI toggle:

1. Sign in to Snowsight as **ACCOUNTADMIN**.
2. Navigation menu → **AI & ML » Agents**.
3. **Settings** → flip the **Web search** toggle on.

After that, agents can use the `web_search` tool. Cortex Agents use the **Brave
Web Search API** under the hood. You add the tool to an agent via
`CREATE/ALTER AGENT` (or the REST `PUT …/agents/<name>` with a `web_search`
`tool_spec`).

```jsonc
// per-agent tool spec (REST or agent specification)
{ "tool_spec": { "type": "web_search", "name": "Web Search" } }
```

> Note: enabling web search affects the **Cortex Agents** feature. Whether *this*
> CLI agent's `web_search` tool is wired to the same account toggle is **not
> documented** and ⚠ **unverified** — enabling the toggle is the documented
> prerequisite; if the CLI tool still returns nothing afterward, that's a separate
> question to raise with the agent's owner.

### 4b. Extended considerations (you asked for this before deciding)

**Cost.**
- Web search itself is a metered Cortex capability; treat each agent web query as a
  billable call to an external (Brave) API surfaced through Snowflake. There is no
  free lunch — usage scales with how often agents search.
- Pair it with the **orchestration budget (seconds + tokens)** from §3 to cap
  per-request spend.

**Token usage.**
- Web results are injected into the model's context, inflating prompt tokens
  (and thus cost and latency) on every turn that searches. `max_results` on the
  web_search tool bounds how much gets pulled in — keep it small.

**Governance / data egress.**
- Web search sends your **query text out to a third-party API (Brave)**. For a
  public-museum learning project this is low-risk, but treat the query string as
  *leaving the Snowflake perimeter* — never let an agent search with sensitive
  inputs. Web search is **not supported in government regions**.

**Best practices.**
- Enable at the account level **once**, then grant/attach the tool per-agent only
  where it's needed (least privilege).
- Prefer **`cortex search docs`** for Snowflake-product questions (in-perimeter,
  authoritative) and reserve web search for genuinely external facts (e.g. the
  museum-API specifics the engineering playbook flagged `⚠ unverified`).

### 4c. The IaC option (your decision — NOT applied)

You asked whether web-search enablement could become an IaC item in the codebase.
Honest assessment of the two layers:

- **Account-level enablement = a Snowsight UI toggle.** The docs describe **no
  `ALTER ACCOUNT SET …` parameter** for it. So it is **not cleanly expressible as
  versioned DDL** today. We *could* record it as a documented manual bootstrap
  step (e.g. a commented entry in `git-setup/` or a README runbook), but that is a
  *runbook note*, not true IaC. ⚠ If a hidden account parameter exists, it's
  unverified — confirm before claiming it.
- **Per-agent web_search tool = genuinely IaC-able.** When/if you build a Cortex
  Agent for this project, its `web_search` tool belongs in the agent's
  `CREATE AGENT … FROM SPECIFICATION`, which *is* a versioned object you'd add to
  `infrastructure/` + `manifest.txt` like every other object.

**Recommendation:** document the account toggle as a manual runbook step now; defer
any agent-object IaC until we actually create an agent. **I have applied nothing** —
this stays a decision for you (recorded as gated in `AGENTS.md`).

**Sources:** Cortex Agents — Web search section
(https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents);
MCP server (https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp).

---

## Next concrete step (you decide)

Lowest-risk: **flip the Web search toggle yourself** (§4a) so the engineering
playbook's `⚠ unverified` museum-API facts can be web-grounded in a later window.
Bigger step: once Gold exists, build a **semantic view + Cortex Analyst agent**
over OpenAccess artworks and (optionally) expose it via the **managed MCP server**.
