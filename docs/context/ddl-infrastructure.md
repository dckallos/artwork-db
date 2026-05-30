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
- `git-setup/*` — full chain reviewed 2026-05-30: `create_git_ops_db.sql`,
  `create_api_integration.sql`, `create_git_repository.sql`, all three paired
  `drop_*.sql`, `operator/rotate_loader_password.sql` (empty), `README.md`,
  `.env.example`. See "git-setup — Git bind chain" below.

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

## Orchestration script internals (confirmed 2026-05-30)

Previously summarized only behaviorally; the AGENTS.md roadmap flagged these as
"internals un-read." Now read end-to-end — the existing summaries above are
**accurate**. Internal detail worth keeping:

- **`scripts/apply_sql.sh`** (67 ln). `set -euo pipefail`; connection precedence
  `arg > $SNOW_CONNECTION > "admin"`. Runs `snow sql --filename` with
  `--enhanced-exit-codes` (exit **5** on any statement failure — needed because
  plain `snow sql` only reports the LAST statement's status in multi-statement
  files). Passes `-D "github_pat=${GITHUB_PAT}"` on **every** apply (template var
  is available to all scripts; only secret-bearing ones reference it). When
  `SNOW_SUPPRESS_STDOUT=1`, redirects stdout to `/dev/null` (no `exec`) and prints
  a remediation pointer on failure; otherwise `exec`s the CLI. stderr always
  preserved.
- **`scripts/rollback_sql.sh`** (32 ln). Mirror of apply for paired drops; same
  connection precedence and `-D github_pat`; always `exec`s with
  `--enhanced-exit-codes`. Relies on every drop being `DROP … IF EXISTS`, so it is
  safe even if the paired create never ran.
- **`scripts/bootstrap.py`** (281 ln). Thin Python preflight; **authors no SQL**
  (only runs the version-controlled `scripts/sql/show_admin_account_grants.sql`).
  Two subcommands: `verify-contract` (static — parses active `GRANT … ON ACCOUNT
  TO ROLE ARTWORK_ADMIN` lines in `create_roles.sql`, stripping `--` comments, and
  asserts they equal the `REQUIRED_ADMIN_ACCOUNT_PRIVILEGES` frozenset
  `{CREATE WAREHOUSE, CREATE DATABASE}` — `EXECUTE TASK` commented in both places)
  and `assert-account-privileges --connection NAME` (runtime — runs SHOW GRANTS
  via `snow sql --format json` with `SNOW_SUPPRESS_STDOUT=1`, keeps `granted_on=
  ACCOUNT` rows, and fails fast with the exact remediation `GRANT` if any required
  privilege is missing). `DEFAULT_CONNECTION="admin"`. `.env` read via
  `dotenv_values` only so the child `snow` inherits `SNOWFLAKE_*`.

## git-setup — Git bind chain (reviewed 2026-05-30)

Optional in-Snowflake mirror layer. Per the 2026-05-29 decision it runs **LAST**,
after infrastructure (create_roles → … → refresh_grants), because
`create_git_repository.sql` grants READ to `ARTWORK_ADMIN` (created by
`create_roles.sql`). Applied via the same `scripts/apply_sql.sh` wrapper, driven by
`make bootstrap` / `make iac`. All three forward scripts succeed in a single pass.

**Forward chain (numeric/dependency order):**

1. `create_git_ops_db.sql` (51 ln) — `CREATE DATABASE IF NOT EXISTS ARTWORK_OPS`
   + `CREATE SCHEMA IF NOT EXISTS GIT` + `CREATE OR REPLACE SECRET
   github_pat_artwork_db` (TYPE=PASSWORD, USERNAME='dckallos', PASSWORD=
   `<% github_pat %>` — snow-sql template placeholder, no committed PAT).
2. `create_api_integration.sql` (38 ln) — `CREATE OR REPLACE API INTEGRATION
   github_artwork_db_integration` (GIT_HTTPS_API, prefix `github.com/dckallos/`),
   whitelists the secret via `ALLOWED_AUTHENTICATION_SECRETS`.
3. `create_git_repository.sql` (67 ln) — `CREATE OR REPLACE GIT REPOSITORY
   artwork_db` binding `API_INTEGRATION` + `GIT_CREDENTIALS` + ORIGIN; then
   `ALTER … FETCH` and `GRANT READ … TO ROLE ARTWORK_ADMIN`.

Missing any of the three reproduces `093550 (22023): Failed to access the Git
Repository`. Object reachable as `@ARTWORK_OPS.GIT.artwork_db/branches/main/<path>`.

**Rollback chain (reverse order, all `IF EXISTS`, fully-qualified names):**
`drop_git_repository.sql` (38) → `drop_api_integration.sql` (39) →
`drop_git_ops_db.sql` (60, owns `DROP SECRET` + `DROP SCHEMA` + `DROP DATABASE`;
DROP SECRET fully-qualified to avoid `090105` with no current DB).

**PAT safety:** secret-bearing apply (#1) flagged by `bootstrap.py` →
`apply_sql.sh` runs with `SNOW_SUPPRESS_STDOUT=1`; PAT injected at apply time via
`-D "github_pat=${GITHUB_PAT}"` sourced from gitignored `git-setup/.env`
(`.env.example` ships blank `GITHUB_PAT=`). Rotate = edit `.env` + re-run `make
iac` (no `ALTER SECRET`).

**Gaps:** `git-setup/operator/rotate_loader_password.sql` is **empty (0 ln)** — no
SQL body (also noted in Gaps). `git-setup/README.md` (112 ln) is the narrative
runbook but is written entirely in the retired `B###`/`V###`/`R###` prefix scheme
(stale — see Stale references). SQL comments reference an external "Phase 0.6 IaC
strategy section 3.3.3" (Notion, not in repo).

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
- `scripts/apply_sql.sh:38` — "Secret-bearing applies (e.g. B001 renders the
  GitHub PAT …)" (B-prefix; reword to name the secret-bearing script/manifest).
- `git-setup/README.md` (whole file) — narrative runbook written entirely in the
  retired `B001/B002/B003`, `V###`, `R###` prefix scheme (naming-convention table,
  execution-order list, bind-chain steps). Reword to prefix-free names + manifest.
- **`git-setup/*.sql` comment bodies — self-contradictory after the mechanical
  rename** (artifact of `rename_and_update.py` blindly substituting old→new
  filenames). E.g. `create_git_ops_db.sql:11` reads "the prior
  create_git_ops_db.sql created the API integration" (was `V001`→`V002` rename
  collision); `drop_api_integration.sql:19` "paired drop for what used to be
  create_git_ops_db.sql"; `drop_git_ops_db.sql:12` "it was the
  create_api_integration.sql drop". The SQL statements are correct; only the prose
  is garbled. Rewrite these comments by hand — do NOT re-run the mechanical script.

These are comment-only; behavior is unaffected, but they contradict the
prefix-free convention and should be reworded to reference the manifest.

## Approved decisions — pending application (NOT yet applied)

Operator-approved on 2026-05-30. **Gated: do NOT apply until the ENTIRE repo is
documented** (policy: no code changes during the documentation pass). This section
is a record for a future dedicated edit window. When that window comes, implement
exactly as specified, keep create↔drop pairs and manifest order consistent, and
validate SQL compiles (do not execute unless told).

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
