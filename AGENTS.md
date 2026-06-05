# AGENTS.md — Context anchor for the artwork-db learning repo

> **Read this file first, every window.** It is the cheapest read in the repo and
> tells you exactly how much more to read. The goal: maximize understanding while
> spending the fewest tokens.

## Operating environment (read before acting)

You run as **Cortex Code in Snowsight** on a trial account. There is **no session
persistence and no local hooks**: this file plus `docs/context/session-3-progress-log.md`
(the append-only restart trail) are your only memory, and your own discipline is the
only enforcement. The trial has **no Cortex inference** (Cortex Agents / Cortex-Code-
over-API are blocked — see the Track-D notes), so ship data, not agent tooling.

**Current account (authoritative): `OBANOYY-MK07348`** (legacy locator `EP21559`,
region `AWS_US_EAST_2`), admin **`PORCHFLAKE` / `ACCOUNTADMIN`**, snow CLI admin
connection `[connections.mk07348]`. Earlier trials `pa37992` and `HXCNOII-RS05429`
(admin `PORCHANALYTICS`) are **RETIRED** — ignore them in older dated entries below.
The loader credential is namespaced per account: `make loader CONN=mk07348` mints
`~/.snowflake/keys/mk07348_loader_rsa_key.p8` + `[connections.mk07348_loader]`.
dbt runs as the `ARTWORK_TRANSFORMER_SVC` service user (key-pair only):
`make transformer CONN=mk07348` mints `mk07348_transformer_rsa_key.p8` +
`[connections.mk07348_transformer]`. Both service users are defined in
`infrastructure/create_service_user.sql`; their keys are registered out-of-band
(not in the manifest) by `setup.sh --phase loader|transformer`.

## Session-open ritual (do this first, every window)

1. **Confirm you are the only live Cortex session before any write.** Count
   `cortex_code_snowsight` sessions (filter `QUERY_TAG ILIKE '%cortex_code_snowsight%'`)
   in the last ~10 min and check `ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS`. Exactly 1 =
   solo; >1 = stop and ask. Do not abort husks. Husk-vs-live-ghost test + the full
   mechanism: `docs/context/connection-resilience.md`.
2. **Resume from `docs/context/session-3-progress-log.md`** — read the last dated entry
   for where we left off and honor its resumption contract.
3. **Read a shared file's current contents immediately before editing it** — a prior
   (or dropped) turn may have already written it. Cross-check a negative grep with a
   raw `grep -rn` (the search tool has given false negatives here).
4. **State the plan and wait for the owner's explicit go (+ date) before any write or
   execution.** Nothing touches the account without sign-off; all DDL flows through
   `make iac` (manifest-driven), never inline. Then verify end state (DESCRIBE/SHOW) —
   a successful run is not proof a change applied.

## Session-close ritual (do this last, every window)

The owner asks for a hand-off prompt at the end of nearly every session, so this is
codified. **Before signing off, every window MUST produce two artifacts:**

1. **A final dated entry appended to `docs/context/session-3-progress-log.md`** that
   supersedes any prior `End of this window` markers in the same date. The entry MUST
   include, in this order:
   - **What changed this turn** (workspace stage; `applied-to-account: yes/no`;
     `pushed-to-Mac: yes/no`).
   - **Cumulative workspace state** vs. the Mac (the delta the next sync will carry).
   - **Solo-session check result.**
   - **First-action options (a)/(b)/(c)** for the next window — concrete, paste-ready.
   - **Read-only verification queries** for any new schema / data state.
   - **Decision tree** keyed off the next run's expected output shapes.
   - **Deferred patches** in priority order.
   - **What MUST NOT happen in the next window** (foot-guns).
   - **The hand-off prompt block** (item 2 below).
   - **An explicit `End of this window` marker** as the final line.
2. **A paste-ready hand-off prompt** as the last code block in that entry, fenced so
   the owner can copy it verbatim into a new Cortex window. The prompt MUST contain:
   reading order (AGENTS.md → latest log entry only); solo-session SQL; dual-FS
   reminder; the gating rule ("state the plan, wait for proceed + date"); a one-line
   project-context recap (branch, account, current Phase, key Snowflake objects); and
   a closing instruction telling the new window to quote the latest `End of this
   window` header back to the owner before proposing its first action. Keep it under
   ~50 lines so it pastes cleanly.

The hand-off prompt is not boilerplate; it is tailored to where the project is at
session-close (e.g. Phase 2 done, Phase 3 in progress, awaiting curl evidence). When
in doubt, copy the prior session's prompt and edit only the parts that have changed.

## What this repo is

A **learning project** (see "Project mission" below) whose mechanics are
infrastructure-as-code: **every Snowflake object is created through the Snowflake
CLI (`snow`)** and is reproducible end-to-end from automated scripts. Default
branch: `main`. Active design branch: `donkey-kong-sandbox`.

In-Snowflake mirror of this repo: `ARTWORK_OPS.GIT.ARTWORK_DB`
(origin `https://github.com/dckallos/artwork-db.git`).

## Project mission & learning goals (READ THIS — it defines your role)

**The IaC is the substrate, not the point.** This repo exists to maximize the
owner's hands-on learning of **Snowflake and dbt depth** by building a
**Medallion architecture** (Bronze → Silver → Gold) over **OpenAccess museum
artwork** (licenses permit commercial reproduction). It grows **iteratively**:
expect the scope to expand window over window.

**Your role is mentor, not just scribe.** Act as a senior Data Engineer pairing
with a motivated learner. That means: explain the *why* and the best-practice
alternatives/tradeoffs (not just the *what*); name the learning fork when a choice
is pedagogically interesting (e.g. dbt tests vs. cross-schema reconciliation for
completeness); proactively propose the next best learning step — **but the owner
decides, and once decided you honor it.**

**Data sources.** Met Museum today (an untested Python API client lives in
`extraction/met/`). Planned next: **Cleveland Museum of Art** (CC0 + open API —
note: not "Cleveland Institute of Art"), **Art Institute of Chicago**, and the
**Smithsonian** (requires an API key).

**Data-quality cornerstones the owner cares about** (recurring design lenses):
- **Timeliness / deaccession** — if an artwork leaves a museum, there must be a
  fast path to drop it from GOLD OpenAccess listings.
- **Delete propagation** — removals in BRONZE must flow through SILVER to GOLD.
- **Cost / DDL optimization** — clustering keys chosen so affected rows prune and
  delete cheaply; spend-aware DDL.
- **Entity normalization** — the same artist referenced differently across sources
  must resolve to a canonical entity.
- **Volume / completeness** — open question (discuss both): dbt tests vs.
  cross-schema reconciliation after the pipeline runs.

**Five optimization tracks driving growth:** (1) Met data, (2) Met ingestion /
updates, (3) Met Bronze/Silver/Gold tables, (4) new data sources, (5) dbt adoption.

> Deep best-practice teaching notes for these tracks now live in
> `docs/context/engineering-playbook.md` (landed 2026-05-30). A companion doc,
> `docs/context/cortex-ai-agents-playbook.md`, covers optimizing Cortex AI &
> Cortex Agents (tools, MCP, orchestration, Web Search enablement).
> `docs/context/met-deepdive.md` is a **decision register** — a granular,
> stable-ID list of open Met collection/ingestion questions (legal, cost,
> pipeline, image-URL lifecycle, deaccession, DDL, automation) and their evolving
> answers, designed to survive across sessions. All three are **reference** docs —
> the guided hands-on build remains the primary learning.

## Workflow domains (navigation — review/verification state lives in Status)

This is a **stable taxonomy**, not a task list. Each domain maps to exactly one
Tier-1 doc. Whether a domain is reviewed/complete is tracked **only** in the
Status table below — never infer status from this list. (Add a domain here only
when a genuinely new area of the repo appears.)

- **CLI connection / auth bootstrap** — installing `snow`, generating the admin
  key pair, registering it, JWT verification, warehouse promotion, loader
  key-pair auth setup. → `docs/context/cli-connection.md`
- **DDL / infrastructure** — databases, schemas, roles, warehouses, stages, file
  formats, tables, tasks, grants, the git-setup bind chain, plus the
  bootstrap/orchestration layer that applies them. → `docs/context/ddl-infrastructure.md`
- **Extraction (runtime ETL)** — the `extraction/met/*` Met OpenAccess loader
  (bootstrap → enrich → upload into `BRONZE.raw_met_objects`) plus the root
  runtime/config files. → `docs/context/extraction.md`
- **dbt adoption (Silver/Gold transforms)** — dbt Core local project, model DAG
  (staging → marts), IaC integration (`dbt_orchestrate.sh`, Makefile peer targets),
  unified variable control (`.env` → `profiles.yml` / `connections.toml` / `config.py`),
  milestone sequence. Strategy → `docs/context/dbt-plan.md`; hands-on teaching →
  `docs/context/dbt-curriculum.md` (+ per-unit journals in `dbt-journal/`).

## Reading protocol (how to stay token-efficient)

Read top-down and **stop as soon as you know enough to act**:

1. **Tier 0 — this file.** Orientation + which workflow you're in.
2. **Tier 1 — the ONE relevant `docs/context/*.md` domain doc.** Self-contained
   summaries (conventions, patterns, gaps). Most tasks need only this.
3. **Tier 2 — `docs/context/file-map.md`.** Per-file purpose + line count +
   an "open full source only if…" trigger. Consult before opening any source.
4. **Tier 3 — the source file itself.** Open ONLY to edit, or when a Tier-2
   trigger says you must. Never bulk-read directories.

Rules of thumb:
- Do **not** read source you are not editing.
- Do **not** re-read a file already summarized here; trust the summary, update it
  if you discover it's stale.
- When you finish a workflow review, **write your findings back into the matching
  Tier-1 doc** so the next window inherits them.
- **Self-lint after editing this file.** AGENTS.md is the cheapest read in the
  repo — after any edit, re-read it whole and check internal consistency:
  headings vs. content, no hardcoded counts that can rot ("two workflows"), and
  Status/Roadmap agreement. Fix contradictions before ending the turn.
- **Don't claim "Complete" without coverage reconciliation.** Before marking a doc
  or `file-map.md` Complete, diff the documented rows against an actual `ls -R`,
  and distinguish files **read this window** from those **trusted from a prior
  window** (see the `Verified` column in `file-map.md`). "Documented" ≠ "verified".

## Status

| Domain doc | State |
|---|---|
| `docs/context/cli-connection.md` | Complete (Workflow 1; `trusted-prior`). **2026-06-01: CLI setup suite hardened + made multi-account.** New `init_profile.sh` (seeds `[connections.<admin>]`); `_lib.sh` is connection-name-aware (`SNOW_LIB_ADMIN_CONN`/`SNOW_LIB_LOADER_CONN`, key-path derivation, `list_connections`/`set_default_connection`); `setup.sh` gained `--profile`/`--admin-conn`/`--loader-conn` + `list`/`switch`/`init-profile` phases. Defaults `admin`/`loader` unchanged. LOCAL-ONLY (config.toml + scripts; no account writes). See `cli-connection.md` "Multi-account" + latest log entry. |
| `docs/context/ddl-infrastructure.md` | Complete (infra `trusted-prior`; git-setup + orchestration internals read 2026-05-30) |
| `docs/context/extraction.md` | Complete (read 2026-05-30) |
| `docs/context/file-map.md` | Complete; per-file provenance in its `Verified` column. File/dir counts intentionally not hardcoded (anti-rot). Session-3 additions (`bronze_views`, `run_control`, ops suite) are row-mapped. |
| `docs/context/engineering-playbook.md` | Complete (forward-learning reference; written 2026-05-30; Snowflake-doc-grounded; Track 4 CMA/AIC/Smithsonian API facts web-verified 2026-05-30) |
| `docs/context/cortex-ai-agents-playbook.md` | Complete (forward-learning reference; written 2026-05-30; Cortex AI/Agents + Web Search enablement) |
| `docs/context/connection-resilience.md` | Complete (written 2026-05-31; problem statement + 10-row prioritized recommendations table + top-3 shortlist + resumable-agent track via Cortex Agents Run+threads + advisory-lease design sketch; doc-grounded, web-verified). **Recs #2 + #3 APPLIED 2026-05-31** via `make infra` (after a scenario-B ghost fork authored the IaC; owner reviewed + accepted the ghost's work). `ABORT_DETACHED_QUERY=TRUE` + `BRONZE.CORTEX_FORK_ALERT` now LIVE. **Rec #1 (advisory lease) explicitly DEFERRED — but evidence-strengthened** by the in-session scenario-B incident. |
| `docs/context/track-d-resumable-agents.md` | Complete (planning doc written 2026-05-31; **next-window briefing** for migrating repeat workflows to Cortex Agents Run + threads; explicit naming clarification Cortex Code vs Cloud Agents vs Cortex Agents OBJECT; quickest-path UI walkthrough + phased plan A→D + cost guardrails + first-action checklist). Phase A smoke test awaits owner sign-off. |
| `docs/context/track-d-checklist.md` | Complete (flexible growth checklist written 2026-05-31; companion to the planning doc; **guideline not declarative plan**; 5 stages from sanity-checks to programmatic runner; explicit "challenge prompts" + "hard stops" + "what will surprise you" journal section; primes the next window to ship data work, not over-build the agent). |
| `docs/context/dbt-plan.md` | Active (written 2026-05-31; locked-in decisions D1-D7, model DAG shape + materializations, IaC integration design, unified variable control (.env split by consumer), 3-milestone sequence M1-M3, 7 open research questions gating M1; strategy-only, no code yet). Next = research window then M1 build. |
| `docs/context/dbt-curriculum.md` | Active (written 2026-06-05; 6-unit hands-on mentorship syllabus with new-window protocol; per-unit journal files in `dbt-journal/` created as entered; status tracking in the file itself). Companion to `dbt-plan.md` (strategy) -- this file is the TEACHING arc. |
| `docs/context/met-deepdive.md` | Active register (created 2026-05-30; ~30 stable-ID Met questions across LEG/IMG/PIPE/DATA/DDL/COST/AUTO/AUTH; Met facts web-verified). **Design→build arc COMPLETE:** S1 strawman → S2 Python review → S2b DDL review → **S3 APPLIED 2026-05-31** (owner ran `make infra`; `DDL-04`/`DDL-05` + the 4 cosmetic decisions → applied; `MET_ENRICHMENT_CONTROL`/`MET_CSV_SNAPSHOT`/`MET_WORKLIST`/`MET_LEASE_RECLAIM_TASK` live in `ARTWORK_DB.BRONZE`). Per-session detail lives in the doc's own sections. **Open = Section C** (data seed, PIPE-06 lease-claim MERGE, DATA-01/DATA-06, AUTO-03; AUTH-01 key-pair CLOSED + verified 2026-05-31). Dual-instance incident this arc → durable restart trail in `session-3-progress-log.md`. |

## Roadmap & deferred work

- **Done (reviewed + documented):** Workflow 1 cli-connection (`trusted-prior`);
  Workflow 2 ddl-infrastructure incl. git-setup Git bind chain (read 2026-05-30)
  and orchestration internals (`apply_sql.sh`, `rollback_sql.sh`, `bootstrap.py`,
  read 2026-05-30); Workflow 3 extraction (`extraction/met/*` + root files, read
  2026-05-30).
- **Repo documentation pass: COMPLETE.** Every substantive file is documented or
  marked trivial in `file-map.md` (file/dir counts not hardcoded — reconcile via
  `ls -R`); provenance is honest per its `Verified` column.
- **Forward learning work — playbooks DONE (2026-05-30):**
  `docs/context/engineering-playbook.md` now exists — best-practice teaching notes
  for the five optimization tracks (medallion delete-propagation, clustering/cost,
  entity normalization, dbt completeness testing, ingestion). Companion
  `docs/context/cortex-ai-agents-playbook.md` covers Cortex AI/Agents optimization.
  Grounded via `cortex search docs`. Track 4's CMA/AIC/Smithsonian API endpoints,
  auth, and license terms were **web-verified 2026-05-30** (account-level Web Search
  now enabled); their `⚠ unverified` flags are cleared. The Met-API `metadataDate`
  note in Track 2 was **also web-verified 2026-05-30** and its flag cleared (full
  Met-facts block in `met-deepdive.md`). (Only the dbt-docs page note in Track 5
  remains flagged — out of scope of the source-API verification.)
- **Met deep-dive register STARTED (2026-05-30):** `docs/context/met-deepdive.md`
  created as a granular, stable-ID decision register for Met collection/ingestion
  questions (legal, cost, pipeline, image-URL lifecycle, deaccession, DDL,
  automation). Seeded with 30 entries; Met facts (CC0 license + `isPublicDomain`
  image gate, `metadataDate` delta endpoint, `images.metmuseum.org` CDN host,
  80 rps, image-URL-less GitHub CSV) web-verified 2026-05-30.
  Most entries are `open`/`exploring`. **PIPE-01/03/05 flipped to `decided`
  2026-05-30** (owner sign-off): keep fetch **local** (egress-bound work off
  per-second compute; native-fetch flip condition recorded); enrichment **state
  authority moves to a thin Snowflake Bronze control table** with SQLite *demoted*
  to disposable in-run scratch (rejected the dual-write "mirror" framing) and
  **batch-grained** (never per-row) status callbacks; Mac↔Snowflake labor split
  formalized as a **two-table contract** (prioritized worklist down, Bronze
  landing + batch status callback up). This operationalizes `AUTO-02` and unblocks
  `AUTO-01/03`. The owner decides remaining sequencing turn-by-turn. **Mentor-flagged gap captured: `DATA-01` deaccession /
  delete-propagation** (UPSERT-only bootstrap never deletes vanished CSV rows).
- **Design→build arc — Sessions 1/2/2b (2026-05-30/31, docs-only) — SUPERSEDED by S3 APPLIED below.** Full per-session detail (strawman, Python review, DDL review, build-impact map) lives in `met-deepdive.md` + `engineering-playbook.md` §2d.
- **Session-3 build arc COMPLETE — APPLIED 2026-05-31 (owner sign-off + execution).**
  Owner picked **Option A**, committed Phase 1 (the 18 reconciled staged files) on
  `donkey-kong-sandbox`, and ran `make infra` on their Mac. All 11 manifest scripts
  applied clean + idempotent. New live IaC objects in `ARTWORK_DB.BRONZE`:
  `MET_ENRICHMENT_CONTROL`, `MET_CSV_SNAPSHOT` (both PK'd), `MET_WORKLIST` view,
  `MET_LEASE_RECLAIM_TASK` (hourly cron / 30-min TTL / resumed). The privilege-contract
  preflight passed live (`bootstrap.py` ↔ `create_roles.sql` agree incl. `EXECUTE TASK`).
  A **read-only provenance/reconciliation audit** preceded the apply (18/18 staged files
  on-spec, 0 off-spec; byte-diff vs baseline blocked by the sandbox — judged by content
  + mtime + the S2b spec). **Dual-instance incident** recurred this arc: two concurrent
  Cortex windows wrote the shared docs/log; resolved by owner confirming a single living
  session + an authoritative window. Durable fix landed: **`docs/context/session-3-progress-log.md`**,
  an append-only restart trail with a resumption contract (read-first, skip `[x]`,
  never assume sole instance). Section C = NEXT session.
- **Decided AND APPLIED 2026-05-31:** the four DDL cosmetic decisions (idempotency split, UPPERCASE identifiers, `grant_privileges.sql → create_grants.sql` rename wiring `drop_grants.sql`, reworded stale V/R/B comments) — landed via Session-3 `make infra`. Was previously gated; now historical.
- **New gated items surfaced (record only — do NOT apply):**
  1. Reword stale V/R/B refs found outside infrastructure:
     `extraction/met/README.md:37`, `/.env.example:9,13`, `apply_sql.sh:38`
     ("B001"), and **`git-setup/README.md` (whole file — B001/B002/B003, V###,
     R### scheme)**. (`config.py:53-54` V### ref FIXED 2026-05-31 during the
     loader key-pair change.)
  2. Decide the fate of `rename_and_update.py` — a spent one-shot rename migration
     (now dead; dense V###/R### source). Candidate for removal.
  3. `profiles.yml.example` uses `env_var()` + key-pair (dbt-core only) — add a
     Snowflake-native dbt profile if/when the project moves to managed dbt.
   4. **RESOLVED + APPLIED + VERIFIED 2026-05-31:** loader auth migrated to key-pair.
      The empty `rotate_loader_password.sql` + `06_rotate_loader_password.sh` are deleted;
      `ARTWORK_LOADER_SVC` is now `TYPE = SERVICE`, `PASSWORD = null` (verified via
      `DESCRIBE USER`), key registered by `setup.sh --phase loader`. Applied via `make iac`;
      `snow connection test -c loader` = OK. The `CREATE … IF NOT EXISTS` no-op gap was
      closed by appending idempotent `ALTER USER … SET TYPE = SERVICE; UNSET PASSWORD`. See `AUTH-01`.
  5. Minor: `SMITHSONIAN_API_KEY` in root `.env.example` has no consumer.
     (The hardcoded sample account in `extraction/met/.env.example` was FIXED
     2026-05-31.)
  6. **Web Search enablement — account toggle now ON (2026-05-30).**
     Account-level `web_search` was **enabled at the account level 2026-05-30**
     (`pa37992`) via the ACCOUNTADMIN Snowsight UI toggle (AI & ML » Agents »
     Settings » Web search). There is still **no documented `ALTER ACCOUNT`
     parameter**, so the account-level enablement is *not* cleanly IaC-able — at
     most a runbook note. The per-agent `web_search` tool *is* IaC-able via
     `CREATE AGENT … FROM SPECIFICATION` once an agent exists. Full cost/token/
     governance analysis + the IaC decision in
     `docs/context/cortex-ai-agents-playbook.md` §4. No agent created; nothing
     else applied.
