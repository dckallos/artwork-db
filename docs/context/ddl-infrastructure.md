# Tier 1 — Workflow 2: DDL / infrastructure

> **COMPLETE** (reviewed 2026-05-30, branch `donkey-kong-sandbox`). Self-contained
> summary of the DDL/IaC layer. Trust this before opening source; update if stale.

## Scope (files reviewed in this window)

- `infrastructure/create_*.sql` — databases & schemas, roles, warehouses, stages,
  file formats, bronze tables, tasks, service user.
- `infrastructure/drop_*.sql` — paired rollback scripts.
- `infrastructure/grant_privileges.sql`, `infrastructure/refresh_grants.sql`,
  `infrastructure/drop_grants.sql`.
- `scripts/bootstrap.py`, `scripts/orchestrate.sh`, `scripts/apply_sql.sh`,
  `scripts/rollback_sql.sh`, `scripts/manifest.txt`.
- `Makefile` (already read — see notes below).
- `git-setup/create_git_ops_db.sql` (creates the GIT ops DB + PAT secret).

## Naming convention (CURRENT — authoritative)

- Filenames are **prefix-free**: `infrastructure/create_<thing>.sql` paired with
  `infrastructure/drop_<thing>.sql`; git-setup uses the same `create_/drop_`
  pattern. Pairing is **by matching base name** (`create_roles` ↔ `drop_roles`),
  NOT by any number.
- **Apply / teardown order is NOT encoded in filenames.** It is defined only in
  `scripts/manifest.txt` and `scripts/orchestrate.sh`. Never infer order from a
  filename.
- Idempotency: `CREATE OR REPLACE` for objects; every create has a paired
  `drop_*.sql` for rollback.

### Retired prefixes — DO NOT resurrect

A previous layout used zero-padded prefixes that have been **fully removed**.
The transform was purely mechanical — strip the `V###__` / `R###__` / `B###__`
prefix; the create/drop pair shared the same number. Examples:

- `V001__create_roles.sql` → `create_roles.sql` (`V001__drop_roles.sql` → `drop_roles.sql`)
- `R001__refresh_grants.sql` → `refresh_grants.sql`; `B003__create_git_repository.sql` → `git-setup/create_git_repository.sql`

If you find any `V***` / `R***` / `B***` reference in code, comments, or docs,
treat it as **stale** and flag it for cleanup.

## Carryover from Workflow 1 (already known)

- `Makefile` orchestrates: `bash -> bash -> snow sql`. Apply order is
  **infrastructure first, then git-setup** (the Git-mirror layer runs LAST in
  `make iac`). Targets: `iac` / `infra` / `bootstrap` / `rollback FILE=…` /
  `down [FROM=…]` / `setup` / `pipeline`. Every IaC target depends on `chmod`
  (via `scripts/bootstrap_chmod.sh`) so missing +x bits can't break a run.
  NOTE: the `down FROM=` value refers to a manifest entry, not a filename prefix
  — verify its exact form against `orchestrate.sh` when reviewed.

## Apply order — AUTHORITATIVE (from `scripts/manifest.txt`, NOT filenames)

Forward order is exactly the manifest line order. `orchestrate.sh` reads the
manifest as the single source of truth; filenames carry no order.

Phase 1 — `infrastructure/` (entries whose dir is `infrastructure`):
1. `create_roles.sql`
2. `create_warehouses.sql`
3. `create_databases_and_schemas.sql`
4. `create_file_formats.sql`
5. `create_stages.sql`
6. `grant_privileges.sql`
7. `create_bronze_tables.sql`
8. `create_service_user.sql`
9. `create_tasks.sql`
10. `refresh_grants.sql`

Phase 2 — `git-setup/` (the Git mirror, runs LAST):
11. `git-setup/create_git_ops_db.sql`
12. `git-setup/create_api_integration.sql`
13. `git-setup/create_git_repository.sql`

Dependency sanity: file_formats (`json_raw`) precede stages that reference it;
`grant_privileges` precedes `create_bronze_tables` but uses `FUTURE TABLES`, so
later-created Bronze tables are still covered; service_user follows its grants.

## `orchestrate.sh` phase → file-set mapping

- `--phase infra` — manifest entries under `infrastructure/`, in order.
- `--phase bootstrap` — manifest entries under `git-setup/`, in order.
- `--phase all` — full manifest order (infra first, git-setup last).
- `--phase down [--from FILE]` — reverse manifest, **only `create_*` basenames**,
  applying the paired drop (basename `create_` → `drop_`). `--from FILE` matches a
  create script **by basename** and starts teardown at its drop (corrects the
  earlier carryover guess that `FROM=` was a manifest-prefix token).
- `--down --file FILE` — roll back one script via its paired drop (basename match,
  searches `infrastructure/` then `git-setup/`).
- Phase classification is purely by directory (`phase_of`). Manifest entries must
  live under `infrastructure/` or `git-setup/` or the loader fails fast.
- Preflight (thin `bootstrap.py`): `verify-contract` (static) runs before any
  apply; `assert-account-privileges` runs immediately AFTER `create_roles.sql`
  applies and before `create_warehouses.sql`, turning a deep 003001/42501 into one
  actionable error.
- Secret handling: `scripts/secret_bearing.txt` lists scripts whose stdout must be
  suppressed; an undeclared file rendering the `<% github_pat %>` marker aborts
  the run (fail-closed).

## Role / grant model

- `ARTWORK_LOADER` — writes BRONZE only (USAGE+CREATE TABLE/STAGE on BRONZE;
  S/I/U/D + READ/WRITE on ALL+FUTURE Bronze tables/stages).
- `ARTWORK_TRANSFORMER` — reads BRONZE (SELECT ALL+FUTURE), full DDL/DML on SILVER
  and GOLD (CREATE TABLE/VIEW, S/I/U/D + SELECT on ALL+FUTURE).
- `ARTWORK_ADMIN` — owns DB/WH/objects; inherits both functional roles; granted to
  `SYSADMIN`. Account grants in `create_roles.sql`: `CREATE WAREHOUSE`,
  `CREATE DATABASE`. `EXECUTE TASK` is **commented out**, to be enabled in lockstep
  with real tasks.
- `ARTWORK_LOADER_SVC` — service user (runtime identity for the Python uploader),
  DEFAULT_ROLE `ARTWORK_LOADER`, DEFAULT_NS `ARTWORK_DB.BRONZE`, placeholder
  password `CHANGE_ME_BEFORE_FIRST_RUN` with an in-file rotation note.
- `grant_privileges.sql` sets ALL+FUTURE grants once; `refresh_grants.sql`
  (repeatable, no drop) re-applies the **ALL (current)** grants only — run after
  new objects land. All grant DDL runs as `ARTWORK_ADMIN`; role/user creation runs
  as `ACCOUNTADMIN`.

## Schema layout — BRONZE / SILVER / GOLD

`ARTWORK_DB` with three medallion schemas, all created in
`create_databases_and_schemas.sql`. Only **BRONZE** is populated by IaC (7 tables:
`raw_met_objects`, `raw_aic_artworks`, `raw_cma_artworks`, `raw_cma_creators`,
`raw_cma_exhibitions`, `raw_smithsonian_objects`, `extraction_log`; plus file
formats `json_raw`/`parquet_raw` and stage `bronze_load_stage`). SILVER and GOLD
are intentionally empty shells — dbt models (run as `ARTWORK_TRANSFORMER`) populate
them later. Raw tables follow a uniform shape: `VARIANT raw_payload` + metadata
(`_extracted_at`, `_source_system`, `_batch_id`).

## DDL style conventions (observed — authoritative)

- Banner header comment block on every file: filename + one-line purpose + explicit
  `Paired rollback:` line.
- Session setup: `USE ROLE …;` then `USE DATABASE …; USE SCHEMA …;` where relevant.
- **Idempotency is mixed by object class (NOT "CREATE OR REPLACE for objects" as
  the old stub implied):** `CREATE … IF NOT EXISTS` for stateful objects (roles,
  warehouses, database, schemas, tables, users); `CREATE OR REPLACE` only for
  stateless/derived objects (file formats, stages).
- Identifier casing: roles / DB / schema / warehouse in UPPERCASE; table, file
  format, and stage names in lowercase.
- COMMENTs on objects and (for Bronze tables) on columns; `_`-prefixed audit cols.
- Drops: `DROP … IF EXISTS`; grant-rollback uses cascade-from-parent (no explicit
  REVOKEs — Snowflake REVOKE has no IF EXISTS guard).

## Rollback symmetry

All 8 create/drop pairs present and matched by basename: roles, warehouses,
databases_and_schemas, file_formats, stages, bronze_tables, service_user, tasks.
Non-create scripts: `grant_privileges.sql` (paired no-op `drop_grants.sql`),
`refresh_grants.sql` (repeatable, no drop). NOTE: `drop_grants.sql` is **not in the
manifest** and `teardown()` only runs paired drops of `create_*` entries, so
`drop_grants.sql` is never auto-invoked — harmless (it is a bare SELECT; grants
cascade from dropped parents) but means its only use is manual.

## Gaps / TODOs / empty files

- `create_tasks.sql` + `drop_tasks.sql` — Phase-4 placeholders (bare `SELECT`); no
  real tasks yet. `EXECUTE TASK ON ACCOUNT` grant stays commented out in
  `create_roles.sql` until tasks are defined.
- `create_service_user.sql` ships a placeholder password requiring rotation before
  first run.
- `git-setup/operator/rotate_loader_password.sql` — empty (carried over from
  Workflow 1; the loader-password rotate has no SQL body).

## Stale `V***` / `R***` / `B***` references to clean up (flagged, not fixed)

- `scripts/manifest.txt` header: "V then R", "(V)", optional "(B)", "repeatable
  R### entries", "skips repeatable R###" (lines ~6–8, 13); also still says it is
  read by `bootstrap.py` though `orchestrate.sh` is now the entry point.
- `infrastructure/drop_grants.sql`: "other V### drop scripts" (line ~11) and
  "grants on the ARTWORK_OPS database from B002" (line ~24).
- `infrastructure/drop_roles.sql`: "applies V### drops in REVERSE order" (line ~9).

These are comment-only; behavior is unaffected, but they contradict the
prefix-free convention and should be reworded to reference the manifest.

## Approved decisions — pending application (NOT yet applied)

Operator-approved on 2026-05-30; deferred to a later window. These are
pre-decided — implement exactly as specified, keep create↔drop pairs and manifest
order consistent, and validate SQL compiles (do not execute unless told).

1. **Idempotency policy (ratified).** Keep the class-based split: `CREATE … IF NOT
   EXISTS` for stateful objects (roles, warehouses, database, schemas, tables,
   users); `CREATE OR REPLACE` for stateless/derived (file formats, stages).
   Action: confirm every `infrastructure/*.sql` conforms (currently consistent)
   and apply the same rule to any new object.
2. **Identifier casing → UPPERCASE, unquoted (standardize).** No prior intentional
   convention. Rewrite lowercase object names to UPPERCASE and update every
   reference: `raw_*` tables + `extraction_log` (`create_bronze_tables.sql` /
   `drop_bronze_tables.sql`), `json_raw`/`parquet_raw` (`create_file_formats.sql` /
   `drop_file_formats.sql` + the `FILE_FORMAT =` ref in `create_stages.sql`),
   `bronze_load_stage` (`create_stages.sql` / `drop_stages.sql`), and grant targets
   in `grant_privileges.sql` / `refresh_grants.sql`, plus `DEFAULT_NAMESPACE` in
   `create_service_user.sql`. Cosmetic (unquoted = case-insensitive) but uniform.
3. **Wire `drop_grants.sql` into teardown.** `orchestrate.sh teardown()` derives
   drops only from `create_*` basenames (`create_ → drop_`), so a non-`create_`
   entry is never torn down. Do NOT just add `drop_grants.sql` to the manifest
   (that would *apply* a drop on forward runs). Instead **rename
   `grant_privileges.sql → create_grants.sql`** so `paired_drop` auto-maps it to
   `drop_grants.sql`; update the `manifest.txt` line and all cross-references
   (comments in `drop_grants.sql`, file-map, this doc). Verify against
   `teardown()` after the rename.
4. **Reword stale V/R/B references** (comment-only) to cite the manifest, not
   prefixes: `scripts/manifest.txt` header (\"V then R\", \"(V)\", \"(B)\",
   \"repeatable R###\"; also the stale \"read by bootstrap.py\"), and the
   `V###`/`B002` mentions in `infrastructure/drop_grants.sql` and
   `infrastructure/drop_roles.sql`.

## When to escalate to full source

- Changing apply/teardown order → edit `scripts/manifest.txt` (only source of order).
- Changing phase routing, preflight, or secret suppression → `scripts/orchestrate.sh`.
- Adding/altering grants → `grant_privileges.sql` (+ mirror current-grants in
  `refresh_grants.sql`); rollback stays no-op unless granting on persistent
  non-dropped objects.
- Defining real tasks → fill `create_tasks.sql` + `drop_tasks.sql` and uncomment the
  `EXECUTE TASK` grant in `create_roles.sql` in lockstep.
- Adding a new object class → create both `create_<thing>.sql` and
  `drop_<thing>.sql` and add the create to `manifest.txt`.
