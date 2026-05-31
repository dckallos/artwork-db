# AGENTS.md — Context anchor for the artwork-db learning repo

> **Read this file first, every window.** It is the cheapest read in the repo and
> tells you exactly how much more to read. The goal: maximize understanding while
> spending the fewest tokens.

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
  credential rotation. → `docs/context/cli-connection.md`
- **DDL / infrastructure** — databases, schemas, roles, warehouses, stages, file
  formats, tables, tasks, grants, the git-setup bind chain, plus the
  bootstrap/orchestration layer that applies them. → `docs/context/ddl-infrastructure.md`
- **Extraction (runtime ETL)** — the `extraction/met/*` Met OpenAccess loader
  (bootstrap → enrich → upload into `BRONZE.raw_met_objects`) plus the root
  runtime/config files. → `docs/context/extraction.md`

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
| `docs/context/cli-connection.md` | Complete (Workflow 1; `trusted-prior`) |
| `docs/context/ddl-infrastructure.md` | Complete (infra `trusted-prior`; git-setup + orchestration internals read 2026-05-30) |
| `docs/context/extraction.md` | Complete (read 2026-05-30) |
| `docs/context/file-map.md` | Complete; per-file provenance in its `Verified` column. File/dir counts intentionally not hardcoded (anti-rot). Session-3 additions (`bronze_views`, `run_control`, ops suite) are row-mapped. |
| `docs/context/engineering-playbook.md` | Complete (forward-learning reference; written 2026-05-30; Snowflake-doc-grounded; Track 4 CMA/AIC/Smithsonian API facts web-verified 2026-05-30) |
| `docs/context/cortex-ai-agents-playbook.md` | Complete (forward-learning reference; written 2026-05-30; Cortex AI/Agents + Web Search enablement) |
| `docs/context/connection-resilience.md` | Complete (written 2026-05-31; problem statement + 10-row prioritized recommendations table + top-3 shortlist + resumable-agent track via Cortex Agents Run+threads + advisory-lease design sketch; doc-grounded, web-verified). Top-3 actions await owner pick. |
| `docs/context/track-d-resumable-agents.md` | Complete (planning doc written 2026-05-31; **next-window briefing** for migrating repeat workflows to Cortex Agents Run + threads; explicit naming clarification Cortex Code vs Cloud Agents vs Cortex Agents OBJECT; quickest-path UI walkthrough + phased plan A→D + cost guardrails + first-action checklist). Phase A smoke test awaits owner sign-off. |
| `docs/context/met-deepdive.md` | Active register (created 2026-05-30; ~30 stable-ID Met questions across LEG/IMG/PIPE/DATA/DDL/COST/AUTO/AUTH; Met facts web-verified). **Design→build arc COMPLETE:** S1 strawman → S2 Python review → S2b DDL review → **S3 APPLIED 2026-05-31** (owner ran `make infra`; `DDL-04`/`DDL-05` + the 4 cosmetic decisions → applied; `MET_ENRICHMENT_CONTROL`/`MET_CSV_SNAPSHOT`/`MET_WORKLIST`/`MET_LEASE_RECLAIM_TASK` live in `ARTWORK_DB.BRONZE`). Per-session detail lives in the doc's own sections. **Open = Section C** (data seed, AUTH-01 key-pair, PIPE-06 lease-claim MERGE, DATA-01/DATA-06, AUTO-03). Dual-instance incident this arc → durable restart trail in `session-3-progress-log.md`. |

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
  1. Reword stale V/R/B refs found outside infrastructure: `config.py:53-54`,
     `extraction/met/README.md:37`, `/.env.example:9,13`, `apply_sql.sh:38`
     ("B001"), and **`git-setup/README.md` (whole file — B001/B002/B003, V###,
     R### scheme)**.
  2. Decide the fate of `rename_and_update.py` — a spent one-shot rename migration
     (now dead; dense V###/R### source). Candidate for removal.
  3. `profiles.yml.example` uses `env_var()` + key-pair (dbt-core only) — add a
     Snowflake-native dbt profile if/when the project moves to managed dbt.
  4. **`git-setup/operator/rotate_loader_password.sql` is empty (0 ln)** — no SQL
     body; implement the `ALTER USER … SET PASSWORD` or remove.
  5. Minor: hardcoded sample account in `extraction/met/.env.example:14`;
     `SMITHSONIAN_API_KEY` in root `.env.example` has no consumer.
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
