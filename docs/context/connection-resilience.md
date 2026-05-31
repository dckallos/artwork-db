# connection-resilience.md — Mitigating connection blips & ghost-session forks

> **Tier-1 reference doc.** Created 2026-05-31. Companion to
> `session-3-progress-log.md` (the empirical incident record) and
> `cortex-ai-agents-playbook.md` (Cortex Agents primitives).
> **Single-instance confirmed before authoring** (`scripts/check.sh` 2026-05-31:
> exactly 1 `cortex_code_snowsight` session). **Read-before-write** discipline
> applied to every shared file touched.
>
> All facts are doc-grounded. Items still **`⚠ unverified`** are flagged inline.

---

## 1. Problem statement & symptom

**Symptom.** A connection blip stuns the live Cortex Code Snowsight window
(UI stops rendering tool output / streaming text). The owner opens a fresh
window and resubmits the prompt. **Two backend agent instances** then edit the
same workspace files concurrently — the "ghost fork" pattern. Empirical
evidence is captured in `session-3-progress-log.md` (the dual-instance
incident: file mtime cluster `01:04–01:07 GMT 2026-05-31` written by a fork
the surviving chat never authored).

**Why this happens (verified):** Cortex Code in Snowsight has **no conversation
persistence** — "Each new session starts fresh. If you have project-level
context, you want Snowflake Cortex Code to always know, put it in an
`AGENTS.md` file." [Flexera 2026](https://www.flexera.com/blog/finops/snowflake-cortex-code-101-snowsight-and-cli-setup-guide-2026/).
A stunned window's backend continues until idle-timeout/abort; the new tab
spawns a new session. Both back-ends share the same user (`PORCHANALYTICS`),
so they cannot be selectively distinguished by identity, role, or network
policy.

**The kill is asymmetric.** `SYSTEM$ABORT_SESSION` is **async, not immediate**;
the client reconnects unless the *client window itself* is closed. Verified:
"the design of the abort_session function forces a logout of connected
sessions … and then cleans up the session … as an async action, so statement
termination may take time and is not guaranteed to be immediate" — and "you
will also need to stop the client to prevent further queries from being
started in the session" [Snowflake KB](https://community.snowflake.com/s/article/A-session-closed-with-the-abort-session-function-is-not-closed-immediately).

**Empirical confirmation (added 2026-05-31, post-authoring):** scenario B
recurred *inside the session that wrote this doc*. A ghost Cortex Code fork
executed during a connection blip and authored 7 files of IaC implementing
recs #2 + #3 — including code materially better than this doc's §6.F strawman
— without the live window's knowledge. The ghost did not (and would not have)
run `check.sh`. **Direct implication for the §3 ranking:** rec #1 (the
advisory lease) is no longer "build belt-and-suspenders later"; it is the
*only* recommendation that would have prevented this specific failure mode,
because #2 and #3 only address queries and detection — neither stops a ghost
agent from writing files. Detail in `session-3-progress-log.md` 2026-05-31
INCIDENT entry. Owner decision on the re-prioritization pending.

---

## 2. Prioritized recommendations

| # | Lens | Action | Addresses symptom? | Effort | IaC-able? | Source |
|---|---|---|---|---|---|---|
| 1 | E. Mutual exclusion | **Software single-flight via `RUN_CONTROL` advisory lease** — new windows must `CLAIM` a `(run_id, instance)` lease before any write; ghost forks see the lease held by the live window and self-abort. | **Direct** — turns "two windows write" into "one window writes, fork yields". | Medium (table + 30-line bash claim/heartbeat) | Yes (DDL + script) | This doc §5; pattern grounded in `BRONZE.RUN_CONTROL` (already exists). |
| 2 | A. Session params | **`ALTER ACCOUNT SET ABORT_DETACHED_QUERY = TRUE`** — Snowflake auto-aborts in-progress queries 5 min after the client connection drops. | **Partial** — kills *queries* in the ghost session but NOT the agent process or its file writes (workspace edits aren't necessarily query-shaped). Still worthwhile. | Trivial | Yes (one DDL) | [Parameters → ABORT_DETACHED_QUERY](https://docs.snowflake.com/en/sql-reference/parameters), [Snowflake KB](https://community.snowflake.com/s/article/Why-am-I-seeing-my-queries-cancelled-when-I-didn-t-cancel-them) |
| 3 | F. Detection | **Snowflake Alert: >1 `cortex_code_snowsight` session active** — scheduled query against `INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER`; sends notification when forks appear. | **Detective, not preventive** — pairs with #1 to surface incidents. | Low (one `CREATE ALERT`) | Yes | [CREATE ALERT](https://docs.snowflake.com/en/sql-reference/sql/create-alert), [Alerts overview](https://docs.snowflake.com/en/user-guide/alerts) |
| 4 | D. Client | **Tab-discipline runbook** — close the old Snowsight tab *before* opening a new one; never resubmit a prompt from a fresh tab while the original is still loading. | **Direct** but human-dependent. The 100% reliable kill (verified: `session-3-progress-log.md` §RUNBOOK). | Trivial | No (procedural) | This doc §6.D + the existing log §RUNBOOK. |
| 5 | C. Resume the work | **Continue the existing `RUN_CONTROL` checkpoint pattern** — every multi-step task writes idempotent step rows, so a stunned window's resume costs ≤1 step of rework. **Already built and in use.** | **Mitigates damage**, doesn't prevent forks. | None (already built) | Yes (already IaC) | `BRONZE.RUN_CONTROL` table; `scripts/checkpoint.sh`. |
| 6 | A. Session params | **Set a UI session policy with a shorter idle timeout** (`SESSION_UI_IDLE_TIMEOUT_MINS`, e.g. 60) so a stunned window auto-logs-out instead of running indefinitely. | **Indirect** — bounds the ghost's lifetime. Default is now 4h (BCR-2139, 2026); can lower to 5 min. | Low | Yes (`CREATE SESSION POLICY`) | [Session policies](https://docs.snowflake.com/en/user-guide/session-policies), [BCR-2139](https://docs.snowflake.com/en/release-notes/bcr-bundles/2026_01/bcr-2139) |
| 7 | C. Resumable agent | **Migrate scriptable workflows to Cortex Agents Run API + threads** — programmatic, thread-persisted alternative to the Code UI for repeat workflows (e.g. "apply infra"). Stunned client-side reconnect resumes the same `thread_id`. | **Architectural fix** — Code UI's "fresh session" defect is bypassed entirely for batch workflows. | High (build an agent + thread driver) | Yes (`CREATE AGENT FROM SPECIFICATION`) | [Cortex Agents Run](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run), [Threads API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-threads-rest-api), [SNOWFLAKE.CORTEX.AGENT_RUN](https://docs.snowflake.com/en/sql-reference/functions/agent_run-snowflake-cortex) |
| 8 | B. Cortex Code | **File feedback to Snowflake** — Cortex Code Snowsight ships fresh-each-session by design; only the vendor can add single-flight enforcement at the product layer. | **Long-term** — no immediate user-side action. | None on our side | No | [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) (no documented single-flight) — `⚠ unverified`: no public release-note mentions ghost-session prevention. |
| 9 | D. Endpoint | **Cabling/network discipline** — wired ethernet over wifi, disable VPN auto-reconnect on the workspace browser, disable browser tab-discard for the Snowsight tab (`chrome://discards/`). | **Reduces blip frequency**, doesn't help once a blip happens. | Trivial | No | General; `⚠ unverified` for Snowflake-specific tab-discard interaction. |
| 10 | A. Session params | **`CLIENT_SESSION_KEEP_ALIVE` + heartbeat** — relevant for SnowSQL/connector clients, **not** the Snowsight UI. Set on the Mac CLI (`~/.snowflake/config.toml`) so `make infra` doesn't drop mid-apply. | **Tangential** — helps Mac terminal; doesn't help the Cortex Code window. | Trivial | Partial (config file, not account DDL) | [CLIENT_SESSION_KEEP_ALIVE](https://docs.snowflake.com/en/user-guide/session-policies), [ODBC params](https://docs.snowflake.com/en/developer-guide/odbc/odbc-parameters) |

---

## 3. "Do this now" shortlist (top 3)

If we do nothing else, do these three (ordered by leverage):

1. **Build the `RUN_CONTROL` advisory lease (rec #1).** This is the only
   recommendation that *prevents* concurrent writes from a ghost fork.
   ~30 lines of bash + a small DDL change. Pairs with the existing
   `check.sh`/`checkpoint.sh` ritual: `claim.sh` is the new first command of
   any session.
2. **Enable `ABORT_DETACHED_QUERY = TRUE` at the account level (rec #2).**
   One DDL. Limits how long a ghost session can run any *query* after its
   client disconnects (5 min cap). Cheap insurance.
3. **Add the >1-cortex-session alert (rec #3).** Detective-only, but it turns
   the dual-instance pattern from invisible (today) into a notification you
   can act on within minutes.

Optional + high-value-later: **rec #7** (Cortex Agents Run + threads) for the
specific workflows that suffer most from session-loss (e.g. recurring infra
audits, Section C build). Out of scope for "do now" — but the right home for
this is a separate Section-D session.

---

## 4. Deeper "resumable-agent" track (rec #7)

The Code UI's defect is structural: **"Each new session starts fresh"**
([source](https://www.flexera.com/blog/finops/snowflake-cortex-code-101-snowsight-and-cli-setup-guide-2026/)).
For workflows that run repeatedly (audits, infra applies, Section-C build
phases), a thread-persistent alternative exists:

### Cortex Agents Run API + Threads (verified)

- `POST /api/v2/cortex/threads` creates a thread (persistent server-side
  conversation). Returns `thread_id`. [Threads API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-threads-rest-api)
- `POST /api/v2/cortex/agent:run` (the Run API) accepts `thread_id` +
  `parent_message_id` to continue from any prior message. [Cortex Agents Run](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run)
- `SNOWFLAKE.CORTEX.AGENT_RUN` is a SQL UDTF wrapper around the same REST
  endpoint, useful for in-warehouse orchestration. [AGENT_RUN reference](https://docs.snowflake.com/en/sql-reference/functions/agent_run-snowflake-cortex)
- 15-minute request timeout per call; a long workflow chains multiple
  `agent:run` calls within the same `thread_id`.
- Sep 02 2025 release note: "configure a thread to maintain the context in
  memory, so that the client does not have to send the context at every turn"
  [release note](https://docs.snowflake.com/en/release-notes/2025/other/2025-09-02-cortex-agents-rest-api-object).

### Why this beats the Code UI for repeat workflows

| Failure mode | Cortex Code Snowsight | Agents Run + threads |
|---|---|---|
| Browser tab killed mid-run | New session, no context | Reconnect to same `thread_id`; resume |
| Connection blip | UI stuns; backend reboots as fork | Client retries; server-side conversation intact |
| Two clients in parallel | Two backend agents writing | Two clients, one server thread — last writer wins, but same context |
| Audit trail | None native | Server-side messages addressable by `message_id` |

### What it *doesn't* fix

- An account toggle is required for Cortex Agents (general availability of
  the agent OBJECT type — see `cortex-ai-agents-playbook.md` §1).
- An agent must be authored. No agent exists in this account today.
- Cost: each `agent:run` bills warehouse + Cortex tokens. Run-history audit
  via `SNOWFLAKE.LOCAL.AI_OBSERVABILITY_EVENTS`
  [observability ref](https://docs.snowflake.com/en/user-guide/snowflake-cortex/ai-observability/reference).
- The Code UI's ergonomics (file viewing, diff preview, tool surface) don't
  port to a REST client without UI work.

**Recommendation:** treat this as a track-D commitment, not a quick fix.
Best fit = workflows with a stable, repeated shape (the Section-C build
phases, the future weekly audit). Authoring sketch lives in
`cortex-ai-agents-playbook.md` §3.

---

## 5. The advisory lease (rec #1) — design sketch

The mutual-exclusion piece. Sketched here, NOT applied — owner sign-off + a
build session before any DDL.

### Schema delta (`infrastructure/create_run_control.sql`)

Today `RUN_CONTROL` is `(run_id, step)` PK + status + checkpoint. Add a
separate small table for the lease (don't overload `RUN_CONTROL`):

```sql
-- STRAWMAN — do NOT apply
CREATE TABLE IF NOT EXISTS BRONZE.RUN_LEASE (
  lease_key      STRING NOT NULL PRIMARY KEY,        -- e.g. 'cortex-code:default'
  holder_id      STRING NOT NULL,                    -- session_id::STRING + UUID
  query_tag      STRING,                             -- ALTER SESSION SET QUERY_TAG=…
  acquired_at    TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  heartbeat_at   TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  ttl_seconds    NUMBER NOT NULL DEFAULT 300,        -- 5-min stale → reclaimable
  notes          STRING
);
```

### Atomic claim — single MERGE

```sql
-- claim if free OR previous holder is stale (heartbeat older than TTL)
MERGE INTO BRONZE.RUN_LEASE t
USING (SELECT 'cortex-code:default' AS lease_key,
              CURRENT_SESSION()::STRING || ':' || UUID_STRING() AS holder_id) s
ON t.lease_key = s.lease_key
WHEN MATCHED AND t.heartbeat_at < DATEADD(second, -t.ttl_seconds, CURRENT_TIMESTAMP())
  THEN UPDATE SET t.holder_id = s.holder_id, t.acquired_at = CURRENT_TIMESTAMP(),
                  t.heartbeat_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED
  THEN INSERT (lease_key, holder_id) VALUES (s.lease_key, s.holder_id);

-- verify we own it (must be the same holder_id we just minted)
SELECT holder_id = :our_holder_id AS owns_lease
FROM BRONZE.RUN_LEASE WHERE lease_key = 'cortex-code:default';
```

### `scripts/claim.sh` (new — owner-decision)

Wraps the MERGE + verification. Returns exit 0 (we own the lease) or non-zero
(another live holder; abort write). Heartbeats the lease every 60 s in the
background. New ritual:

```
bash scripts/check.sh                                   # detect forks (today)
bash scripts/claim.sh 2026-05-31-recon                  # NEW — block-or-yield
bash scripts/checkpoint.sh 2026-05-31-recon resume in_progress
... actual work ...
```

A ghost fork's `claim.sh` would see a fresh heartbeat from the live window
and exit non-zero — the fork's prompt-driven "do work" loop then has a
single point at which to STOP. (This requires the agent to consult the
exit code; it's enforced by the AGENTS.md ritual + by humans at first.)

### Failure modes (be honest)

- **The ghost fork doesn't run `claim.sh`.** Pure agent discipline — only as
  reliable as the prompt + AGENTS.md instructions. Mitigation: the
  resumption contract in `session-3-progress-log.md` already mandates a
  read-first / check-first ritual. Add `claim.sh` to it.
- **TTL drift / stale lock.** A live window that crashes leaves the lease
  held until TTL expires (5 min). Acceptable; tunable.
- **Two near-simultaneous claims.** MERGE is atomic in Snowflake (single
  statement), so one wins — the verification SELECT settles it.

---

## 6. The other lenses (lighter coverage)

### A. Snowflake session/network params (verified)

| Parameter | Default | Purpose | Recommendation |
|---|---|---|---|
| `ABORT_DETACHED_QUERY` | `FALSE` | Auto-aborts in-progress queries 5 min after a client disconnect. | **Set TRUE at account level** ([source](https://docs.snowflake.com/en/sql-reference/parameters)). |
| `CLIENT_SESSION_KEEP_ALIVE` | `FALSE` | Driver pings to keep session alive (per-client). | Set on the Mac SnowSQL config; harmless. |
| `CLIENT_SESSION_KEEP_ALIVE_HEARTBEAT_FREQUENCY` | varies by driver | Heartbeat interval seconds. | Mid-range value (900 s) when KEEP_ALIVE=TRUE. |
| `SESSION_IDLE_TIMEOUT_MINS` | 240 (non-UI) | Session policy attribute. | Lower for UI-only policy if owner wants tighter ghost lifetime. |
| `SESSION_UI_IDLE_TIMEOUT_MINS` | 240 (post-BCR-2139, 2026) | UI-specific idle timeout. | See [BCR-2139](https://docs.snowflake.com/en/release-notes/bcr-bundles/2026_01/bcr-2139). |
| `STATEMENT_TIMEOUT_IN_SECONDS` | warehouse-level | Caps statement runtime. | Already covered by `ARTWORK_WH` defaults; not a session-blip lever. |

### B. Cortex Code product behavior (mostly silent in docs)

- **Verified:** "Each new session starts fresh"
  ([Flexera 2026 setup guide](https://www.flexera.com/blog/finops/snowflake-cortex-code-101-snowsight-and-cli-setup-guide-2026/)).
  No conversation persistence in the Snowsight implementation.
- **Verified:** `AGENTS.md` is the documented persistence mechanism for
  cross-session context (same source).
- **Verified:** [Cortex Code product page](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code)
  + [Snowsight implementation](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight) +
  [Mar 9 2026 GA release note](https://docs.snowflake.com/en/release-notes/2026/other/2026-03-09-cortex-code-snowsight-ga)
  describe the product but **do not document any single-flight, fork-prevention,
  or resume-on-reconnect behavior**. → `⚠ unverified` whether ghost forks are a
  known issue with a tracked roadmap item.
- **Action:** file feedback (in-product feedback channel; no public issue
  tracker noted). Out-of-band item for the owner.

### C. Resume-the-work patterns (already partly built)

- `BRONZE.RUN_CONTROL` checkpoint table — durable per-step state, PK
  `(run_id, step)`, VARIANT checkpoint, session_id/query_tag provenance.
  **Already in IaC** (`infrastructure/create_run_control.sql`,
  Session-3 applied).
- `scripts/checkpoint.sh` — write a `RUN_CONTROL` row, sets `QUERY_TAG`.
  **Already in scripts.**
- `scripts/sql/show_run_control.sql` — reads back the trail; smell-tests for
  multi-instance writes. **Already in scripts.**
- **`QUERY_TAG` correlation.** The cortex_code_snowsight tag is already used
  for fork detection (`show_active_sessions.sql`). For richer correlation,
  set a tag including the `run_id`:
  `ALTER SESSION SET QUERY_TAG = '{"run_id":"…","app":"…"}'`. The Mac CLI
  (`apply_sql.sh`) can do this automatically.
- **Idempotent re-run discipline.** Already enforced (DDL idempotency split,
  manifest dependency order, Snowflake `MERGE` upserts). No change needed.

### D. Client / endpoint

- Browser tab discard: Chrome aggressively discards background tabs unless
  pinned. Pin the Snowsight tab; or `chrome://discards/` to inspect.
  `⚠ unverified` whether Snowsight-on-discard cleanly closes the session
  (likely it does NOT — that's the root of the symptom).
- OS sleep: closing the lid on a Mac with the Snowsight tab open breaks the
  websocket. The Cortex Code backend keeps running. Pair with rec #2
  (`ABORT_DETACHED_QUERY=TRUE`) to bound the orphan.
- VPN/proxy: forced reconnect (e.g. corporate Zscaler) drops the session.
  No fix at the Snowflake layer.
- Multiple devices/tabs: same user logged in twice = same problem class as
  the ghost fork. Discipline: one Cortex Code window at a time, full stop.
- Concurrent-session limits: Snowflake doesn't impose a per-user concurrent
  session cap by default. `⚠ unverified` whether a session policy can do
  this; the docs describe idle-timeout/lifespan but not max-concurrent.

### E. Operational guardrails (rec #1 above is the main one)

- The lease pattern (§5) is the single-flight fix.
- Tab-discipline runbook (already in `session-3-progress-log.md` §RUNBOOK).
- Stable `run_id` convention: `YYYY-MM-DD-<topic>` (already in use:
  `2026-05-31-recon`).
- Read-first / write-second on every shared file (already in AGENTS.md).

### F. Detection / observability (rec #3)

```sql
-- STRAWMAN alert (do NOT apply)
CREATE ALERT IF NOT EXISTS BRONZE.CORTEX_FORK_ALERT
  WAREHOUSE = ARTWORK_WH
  SCHEDULE  = '5 MINUTE'
  IF (EXISTS (
    SELECT 1
    FROM TABLE(ARTWORK_DB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(RESULT_LIMIT=>1000))
    WHERE START_TIME >= DATEADD(minute, -10, CURRENT_TIMESTAMP())
      AND CONTAINS(QUERY_TAG, 'cortex_code_snowsight')
    GROUP BY SESSION_ID
    HAVING COUNT(DISTINCT SESSION_ID) > 1
  ))
  THEN CALL SYSTEM$SEND_EMAIL(...);
```

Pairs with the existing `scripts/sql/show_active_sessions.sql` for
on-demand inspection. The alert mechanics are well-documented
([CREATE ALERT](https://docs.snowflake.com/en/sql-reference/sql/create-alert)).

Provenance via session_id: every checkpoint row already carries
`session_id` + `query_tag` columns; an alert that flags
"two distinct `session_id`s wrote to the same `run_id` in the last
N minutes" is a one-line addition to `show_run_control.sql`.

---

## 7. Open questions / `⚠ unverified`

1. **Cortex Code release notes silent on ghost-fork prevention.** No public
   roadmap item or "single-flight" note in
   [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code)
   or its [Mar 9 2026 GA release note](https://docs.snowflake.com/en/release-notes/2026/other/2026-03-09-cortex-code-snowsight-ga).
   → file vendor feedback.
2. **Snowflake max-concurrent-sessions per user.** Session policies cap
   timeouts and lifespans but don't appear to cap concurrent-session count
   ([Session policies](https://docs.snowflake.com/en/user-guide/session-policies)).
   `⚠ unverified` — owner could ask Snowflake support.
3. **Tab discard interaction with Snowsight session.** No documented
   behavior on whether Chrome's tab-discard cleanly closes the websocket
   or leaves it in a half-open state. Empirically (this repo's incident
   record) the latter happens. `⚠ unverified` formally.
4. **Whether Cortex Code Snowsight can be told to "yield to existing
   session" by client-side prompt.** The tools we have (this AGENTS.md +
   the resumption contract) are best-effort; there is no API hook.
5. **Cost of a Cortex Agent + thread alternative for repeat workflows.**
   Per-`agent:run` warehouse + token cost not estimated for our specific
   workloads; needs a track-D scoping pass.

---

## 8. Cross-references

- Empirical incident record: `docs/context/session-3-progress-log.md`
  (the dual-instance evidence + the abort/close-tab runbook).
- Cortex Agents primitives: `docs/context/cortex-ai-agents-playbook.md` §3.
- Existing checkpoint/lease infrastructure already in IaC:
  `infrastructure/create_run_control.sql`, `scripts/check.sh`,
  `scripts/checkpoint.sh`, `scripts/sql/show_*.sql`.
- AGENTS.md "single-instance discipline" + "read-before-write" rules — this
  doc is the technical implementation behind those rules.
