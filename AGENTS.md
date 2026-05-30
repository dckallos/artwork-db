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
| `docs/context/file-map.md` | Complete — reconciled vs `ls -R` (77 files / 12 dirs); see `Verified` column for per-file provenance |
| `docs/context/engineering-playbook.md` | Complete (forward-learning reference; written 2026-05-30; Snowflake-doc-grounded; Track 4 CMA/AIC/Smithsonian API facts web-verified 2026-05-30) |
| `docs/context/cortex-ai-agents-playbook.md` | Complete (forward-learning reference; written 2026-05-30; Cortex AI/Agents + Web Search enablement) |
| `docs/context/met-deepdive.md` | Active register (created 2026-05-30; seeded with 26 stable-ID Met questions across LEG/IMG/PIPE/DATA/DDL/COST/AUTO; Met facts web-verified; grows as we work) |

## Roadmap & deferred work

- **Done (reviewed + documented):** Workflow 1 cli-connection (`trusted-prior`);
  Workflow 2 ddl-infrastructure incl. git-setup Git bind chain (read 2026-05-30)
  and orchestration internals (`apply_sql.sh`, `rollback_sql.sh`, `bootstrap.py`,
  read 2026-05-30); Workflow 3 extraction (`extraction/met/*` + root files, read
  2026-05-30).
- **Repo documentation pass: COMPLETE — coverage reconciled.** All 77 files are
  either documented or explicitly marked trivial in `file-map.md`. Provenance is
  honest: most rows are `read this window` (2026-05-30); the Workflow-1 scripts and
  the `infrastructure/*` DDL are `trusted-prior` (summarized in earlier windows,
  not re-read). The gating policy below can now be lifted for a dedicated edit
  window. *(Correction: a prior window prematurely flipped `file-map.md` to
  "Complete" while git-setup DDL was still un-reviewed; that gap is now closed.)*
- **Forward learning work — playbooks DONE (2026-05-30):**
  `docs/context/engineering-playbook.md` now exists — best-practice teaching notes
  for the five optimization tracks (medallion delete-propagation, clustering/cost,
  entity normalization, dbt completeness testing, ingestion). Companion
  `docs/context/cortex-ai-agents-playbook.md` covers Cortex AI/Agents optimization.
  Grounded via `cortex search docs`. Track 4's CMA/AIC/Smithsonian API endpoints,
  auth, and license terms were **web-verified 2026-05-30** (account-level Web Search
  now enabled); their `⚠ unverified` flags are cleared. (The Met-API `metadataDate`
  note in Track 2 and the dbt-docs page note in Track 5 remain flagged — out of
  scope of the museum-source verification.)
- **Met deep-dive register STARTED (2026-05-30):** `docs/context/met-deepdive.md`
  created as a granular, stable-ID decision register for Met collection/ingestion
  questions (legal, cost, pipeline, image-URL lifecycle, deaccession, DDL,
  automation). Seeded with 26 entries; Met facts (CC0 license, `metadataDate`
  delta endpoint, `images.metmuseum.org` host, 80 rps) web-verified 2026-05-30.
  Most entries are `open`/`exploring` — none `decided`; the owner decides
  sequencing turn-by-turn. **Mentor-flagged gap captured: `DATA-01` deaccession /
  delete-propagation** (UPSERT-only bootstrap never deletes vanished CSV rows).
- **Decided, but GATED — do NOT apply yet:** four DDL edits (idempotency split,
  UPPERCASE identifiers, wire `drop_grants.sql` via renaming
  `grant_privileges.sql → create_grants.sql`, reword stale V/R/B comments). Full
  spec in "Approved decisions — pending application" in
  `docs/context/ddl-infrastructure.md`.
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
