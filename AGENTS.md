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
| `docs/context/file-map.md` | Partial (auth + infrastructure done; extraction pending) |
