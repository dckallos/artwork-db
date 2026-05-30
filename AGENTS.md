# AGENTS.md — Context anchor for the artwork-db IaC repo

> **Read this file first, every window.** It is the cheapest read in the repo and
> tells you exactly how much more to read. The goal: maximize understanding while
> spending the fewest tokens.

## What this repo is

An infrastructure-as-code repository where **every Snowflake object is created
through the Snowflake CLI (`snow`)** and reproducible end-to-end from automated
scripts. Default branch: `main`. Active design branch: `donkey-kong-sandbox`.

In-Snowflake mirror of this repo: `ARTWORK_OPS.GIT.ARTWORK_DB`
(origin `https://github.com/dckallos/artwork-db.git`).

## The two workflows (compartmentalized — review one per context window)

1. **CLI connection / auth bootstrap** — installing `snow`, generating the admin
   key pair, registering it, JWT verification, warehouse promotion, loader
   credential rotation. → `docs/context/cli-connection.md`
2. **DDL / infrastructure** — creating databases, schemas, roles, warehouses,
   stages, file formats, tables, tasks, grants, plus the bootstrap/orchestration
   layer that applies them. → `docs/context/ddl-infrastructure.md`
3. **Extraction (runtime ETL)** — the `extraction/met/*` Met OpenAccess loader
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

## Status

| Domain doc | State |
|---|---|
| `docs/context/cli-connection.md` | Complete |
| `docs/context/ddl-infrastructure.md` | Complete |
| `docs/context/extraction.md` | Complete |
| `docs/context/file-map.md` | Complete (auth + infrastructure + orchestration + extraction + root) |

## Roadmap & deferred work

- **Done (reviewed + documented):** Workflow 1 cli-connection; Workflow 2
  ddl-infrastructure; Workflow 3 extraction (`extraction/met/*` + root
  `.env.example` / `profiles.yml.example` / `requirements.txt` /
  `rename_and_update.py`); orchestration internals (`apply_sql.sh`,
  `rollback_sql.sh`, `bootstrap.py`) confirmed.
- **Repo documentation pass: COMPLETE.** All source is now summarized in a Tier-1
  doc and indexed in `file-map.md`. The gating policy below can now be lifted by
  the operator for a dedicated edit window.
- **Decided, but GATED — do NOT apply yet:** four DDL edits (idempotency split,
  UPPERCASE identifiers, wire `drop_grants.sql` via renaming
  `grant_privileges.sql → create_grants.sql`, reword stale V/R/B comments). Full
  spec in "Approved decisions — pending application" in
  `docs/context/ddl-infrastructure.md`.
- **New gated items surfaced this window (record only — do NOT apply):**
  1. Reword stale V/R/B refs found outside infrastructure: `config.py:53-54`,
     `README.md:37`, `/.env.example:9,13`, and `apply_sql.sh:38` ("B001").
  2. Decide the fate of `rename_and_update.py` — a spent one-shot rename migration
     (now dead; dense V###/R### source). Candidate for removal.
  3. `profiles.yml.example` uses `env_var()` + key-pair (dbt-core only) — add a
     Snowflake-native dbt profile if/when the project moves to managed dbt.
  4. Minor: hardcoded sample account in `extraction/met/.env.example:14`;
     `SMITHSONIAN_API_KEY` in root `.env.example` has no consumer.
- **Reconciled discrepancy:** AGENTS previously listed `apply_sql.sh`,
  `rollback_sql.sh`, `bootstrap.py` internals as "un-read" while
  `ddl-infrastructure.md` listed them reviewed. Now read end-to-end — prior
  behavioral summaries confirmed accurate; internal detail added there.
