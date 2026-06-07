# Tier 1 — Workflow 2: DDL / infrastructure

> **COMPLETE** (reviewed 2026-05-30, branch `donkey-kong-sandbox`). Self-contained
> summary of the DDL/IaC layer. Trust this before opening source; update if stale.

## Scope (files reviewed in this window)

- `infrastructure/create_*.sql` — databases & schemas, roles, warehouses, stages,
  file formats, bronze tables, tasks, service user.
- `infrastructure/drop_*.sql` — paired rollback scripts.
- `infrastructure/grant_privileges.sql`, `infrastructure/refresh_grants.sql`,
  `infrastructure/drop_grants.sql`.
- `$(TOOLKIT_DIR)/bootstrap.py`, `scripts/orchestrate.sh` (legacy, local),
  `$(TOOLKIT_DIR)/apply_sql.sh`, `$(TOOLKIT_DIR)/rollback_sql.sh`,
  `scripts/manifest.txt` (artwork deploy ordering, stays local).
- `Makefile` (already read — see notes below).
- `git-setup/*` — full chain reviewed 2026-05-30: `create_git_ops_db.sql`,
  `create_api_integration.sql`, `create_git_repository.sql`, all three paired
  `drop_*.sql`, `operator/register_loader_public_key.sql`, `README.md`,
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
  (via `$(TOOLKIT_DIR)/bootstrap_chmod.sh`) so missing +x bits can't break a run.
  NOTE: the `down FROM=` value refers to a manifest entry, not a filename prefix
  — verify its exact form against `orchestrate.sh` when reviewed.

## Apply order — AUTHORITATIVE (from `scripts/manifest.txt`, NOT filenames)

Forward order is exactly the manifest line order. `orchestrate.sh` reads the
manifest as the single source of truth; filenames carry no order.

Phase 1 — `infrastructure/` (entries whose dir is `infrastructure`):
1. `create_account_parameters.sql`
2. `create_roles.sql`
3. `create_warehouses.sql`
4. `create_databases_and_schemas.sql`
5. `create_file_formats.sql`
6. `create_stages.sql`
7. `create_grants.sql` (formerly `grant_privileges.sql`)
8. `create_bronze_tables.sql`
9. `create_run_control.sql`
10. `create_bronze_views.sql`
11. `create_service_user.sql`
12. `create_tasks.sql`
13. `create_alerts.sql`
14. `refresh_grants.sql`

Phase 2 — `git-setup/` (the Git mirror, runs LAST):
15. `git-setup/create_git_ops_db.sql`
16. `git-setup/create_api_integration.sql`
17. `git-setup/create_git_repository.sql`

Dependency sanity: file_formats (`json_raw`) precede stages that reference it;
`create_grants` precedes `create_bronze_tables` but uses `FUTURE TABLES`, so
later-created Bronze tables are still covered; `create_bronze_views` follows
`create_bronze_tables` + `create_run_control` (the `MET_WORKLIST` view reads
`MET_ENRICHMENT_CONTROL` + `MET_CSV_SNAPSHOT`); `create_tasks` follows the control
table it reclaims; service_user follows its grants.

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

## Met control plane — object reference (live-verified 2026-06-05)

Stable reference for the four Session-3 Met enrichment objects, all in
`ARTWORK_DB.BRONZE`. Shapes verified live via `DESCRIBE` / `GET_DDL` / `SHOW TASKS`
on account `OBANOYY-MK07348`. Source DDL + paired drops:
`create_bronze_tables.sql` (the two tables), `create_bronze_views.sql` /
`drop_bronze_views.sql` (the view), `create_tasks.sql` / `drop_tasks.sql` (the task).

**Data flow (the two-table contract).** Mac and Snowflake split the labor:

    snapshot (full CSV, no API)  ->  MET_CSV_SNAPSHOT   (descriptive truth)
    seed-control (bounded slice) ->  MET_ENRICHMENT_CONTROL (state only)
                                         |
                              MET_WORKLIST (view: control x snapshot, lease-aware)
                                         |  Mac claims a batch (lease), fetches
                                         v  image URLs, assembles server-side
                                     RAW_MET_OBJECTS (enriched Bronze rows)
    MET_LEASE_RECLAIM_TASK (hourly): frees leases older than 30 min so a crashed
                                     batch's rows re-enter the worklist.

**`MET_CSV_SNAPSHOT`** (table, PK `OBJECT_ID`). Full Met OpenAccess CSV, one
VARIANT row per object, landed by `snapshot` via stage -> COPY -> MERGE
(MERGE-keyed on `object_id`, so re-runs upsert, never append). Columns:
`OBJECT_ID NUMBER` (PK), `RAW_PAYLOAD VARIANT` (full CSV row, snake_case keys),
`_EXTRACTED_AT`, `_SOURCE_SYSTEM` ('met_museum'), `_BATCH_ID`. Independent of
enrichment, so PENDING rows can be prioritized before any API call, and DATA-01
deaccession is a clean anti-join (object_ids in a prior snapshot, absent now).

**`MET_ENRICHMENT_CONTROL`** (table, PK `OBJECT_ID`). Thin, Snowflake-authoritative
state/lease table — never the wide descriptive row. 10 columns:
`OBJECT_ID` (PK), `ENRICHMENT_STATUS` (`pending|done|no_image|error`, default
`pending`), `LAST_ENRICHED_AT`, `METADATA_DATE` (Met `metadataDate`, the
incremental-change signal), `HAS_PRIMARY_IMAGE` (monetization gate), `IMAGE_STATUS`
(`unknown|live|dead`, CDN liveness IMG-04), `LAST_HEAD_CHECK_AT`,
**`CLAIMED_BY_BATCH`** (lease owner batch_id; NULL = free), **`CLAIMED_AT`** (lease
timestamp), `ENRICHMENT_ERROR` (last failure, cleared on success).

**`MET_WORKLIST`** (view; `CREATE OR REPLACE`, stateless). The prioritized,
lease-aware queue the Mac drains. Joins control x snapshot 1:1 on `object_id` and
filters `CLAIMED_AT IS NULL` (not leased) AND (`status IN ('pending','error')` OR
`metadata_date > last_enriched_at` OR `has_primary_image IS NULL`). Orders by
`is_public_domain DESC, is_highlight DESC, department_priority ASC, object_id ASC`
(department_priority: painting=1, drawing/print=2, photograph=3, sculpture=4,
else 9). Priority inputs are read from the snapshot VARIANT, never duplicated into
control — so the view can never drift from the single authority.

**Lease / claim mechanics (what "leased" means).** `enrich-met` claims a batch by
stamping `CLAIMED_BY_BATCH` + `CLAIMED_AT` on up to `--limit` worklist rows
(mutual exclusion: the `CLAIMED_AT IS NULL` filter hides them from other runs).
On success the rows are assembled into `RAW_MET_OBJECTS` and marked `done`. If the
run dies mid-batch, the rows stay leased to a dead batch and are skipped until
**`MET_LEASE_RECLAIM_TASK`** clears them.

**`MET_LEASE_RECLAIM_TASK`** (task; `CREATE OR REPLACE`, stateless). Owner
`ARTWORK_ADMIN`, warehouse `ARTWORK_WH`, `SCHEDULE = USING CRON 0 * * * * UTC`
(hourly), `NO_OVERLAP`, state `started`. Body: `UPDATE MET_ENRICHMENT_CONTROL SET
claimed_by_batch=NULL, claimed_at=NULL WHERE claimed_at < DATEADD(minute,-30,
CURRENT_TIMESTAMP())`. Needs `EXECUTE TASK ON ACCOUNT` granted to `ARTWORK_ADMIN`
(in `create_roles.sql`). TTL-vs-throttling caveat: see "Gaps / TODOs" below.

**Delete-propagation / uniqueness hooks.** Both tables declare PRIMARY KEYs to
signal one-row-per-object intent, but Snowflake does NOT enforce PK/UNIQUE — the
MERGE load pattern carries the guarantee at runtime (Section C). The PKs keep the
`MET_WORKLIST` join strictly 1:1 (no fan-out) and make DATA-01 deaccession a clean
snapshot anti-join. Non-enforcement is the open Section-C mentor-flag (see below).

## Orchestration script internals (confirmed 2026-05-30)

Previously summarized only behaviorally; the AGENTS.md roadmap flagged these as
"internals un-read." Now read end-to-end — the existing summaries above are
**accurate**. Internal detail worth keeping:

- **`$(TOOLKIT_DIR)/apply_sql.sh`** (67 ln). `set -euo pipefail`; connection precedence
  `arg > $SNOW_CONNECTION > "admin"`. Runs `snow sql --filename` with
  `--enhanced-exit-codes` (exit **5** on any statement failure — needed because
  plain `snow sql` only reports the LAST statement's status in multi-statement
  files). Passes `-D "github_pat=${GITHUB_PAT}"` on **every** apply (template var
  is available to all scripts; only secret-bearing ones reference it). When
  `SNOW_SUPPRESS_STDOUT=1`, redirects stdout to `/dev/null` (no `exec`) and prints
  a remediation pointer on failure; otherwise `exec`s the CLI. stderr always
  preserved.
- **`$(TOOLKIT_DIR)/rollback_sql.sh`** (32 ln). Mirror of apply for paired drops; same
  connection precedence and `-D github_pat`; always `exec`s with
  `--enhanced-exit-codes`. Relies on every drop being `DROP … IF EXISTS`, so it is
  safe even if the paired create never ran.
- **`$(TOOLKIT_DIR)/bootstrap.py`** (281 ln). Thin Python preflight; **authors no SQL**
  (only runs the version-controlled `$(TOOLKIT_DIR)/sql/show_admin_account_grants.sql`).
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
`create_roles.sql`). Applied via the same `$(TOOLKIT_DIR)/apply_sql.sh` wrapper, driven by
`make bootstrap` / `make iac`. All three forward scripts succeed in a single pass.

**Forward chain (numeric/dependency order):**

1. `create_git_ops_db.sql` (51 ln) — `CREATE DATABASE IF NOT EXISTS ARTWORK_OPS`
   + `CREATE SCHEMA IF NOT EXISTS GIT` + `CREATE OR REPLACE SECRET
   github_pat_artwork_db` (TYPE=PASSWORD, USERNAME='dckallos', PASSWORD=
   `<% github_pat %>` — snow-sql template placeholder, no committed PAT).
2. `create_api_integration.sql` (38 ln) — `CREATE OR REPLACE API INTEGRATION
   GITHUB_ARTWORK_DB_INTEGRATION` (GIT_HTTPS_API, prefix `github.com/dckallos/`),
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

**Gaps:** `git-setup/README.md` (112 ln) is the narrative
runbook but is written entirely in the retired `B###`/`V###`/`R###` prefix scheme
(stale — see Stale references). SQL comments reference an external "Phase 0.6 IaC
strategy section 3.3.3" (Notion, not in repo). (The former empty
`rotate_loader_password.sql` gap is RESOLVED 2026-05-31 — replaced by
`operator/register_loader_public_key.sql`; loader is now key-pair.)

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

## Met control plane — object reference (verified live 2026-06-05)

Four `ARTWORK_DB.BRONZE` objects implement the Met enrichment control plane (the
`snapshot -> seed-control -> enrich-met` pipeline). All checked against live
`GET_DDL`/`SHOW`/`DESCRIBE` this date; inline comments in the source `create_*.sql`
are the per-line authority — this is the consolidated map.

1. **`MET_CSV_SNAPSHOT`** (table; `create_bronze_tables.sql`). Full Met OpenAccess
   CSV as VARIANT, one row per objectID. Cols: `object_id NUMBER` **PK**,
   `raw_payload VARIANT` (whole CSV row, snake_case keys), `_extracted_at`,
   `_source_system='met_museum'`, `_batch_id`. Loaded via stage -> `COPY` -> **`MERGE`
   keyed on `object_id`** (insert new / update changed, never append) — Snowflake does
   not enforce PK, so the MERGE pattern carries the 1:1 guarantee. Feeds `MET_WORKLIST`
   priority inputs and the `DATA-01` deaccession diff (anti-join: object_ids in a prior
   snapshot absent from the current CSV). Live rows 2026-06-05: **484,956**.

2. **`MET_ENRICHMENT_CONTROL`** (table; `create_bronze_tables.sql`). Thin, Snowflake-
   authoritative **state** table (never the wide descriptive row), one row per objectID
   (**PK**). 10 cols: `object_id` PK; `enrichment_status` DEFAULT `'pending'`
   (enum `pending|done|no_image|error`); `last_enriched_at`; `metadata_date` (incremental
   change signal); `has_primary_image` (monetization gate, LEG-02/IMG-02); `image_status`
   DEFAULT `'unknown'` (`unknown|live|dead`, IMG-04); `last_head_check_at`;
   `claimed_by_batch` (lease owner batch_id, NULL = free); `claimed_at` (lease ts);
   `enrichment_error VARCHAR(500)` (also added via idempotent `ALTER ADD COLUMN IF NOT
   EXISTS` for pre-existing installs, P-D1).
   - **Lease mechanics:** a run stamps `claimed_by_batch`+`claimed_at` to mutually
     exclude other runs; cleared on clean finish (status flips). Abandoned leases
     (crash/Ctrl-C) are reset by `MET_LEASE_RECLAIM_TASK`.
   - **Delete-propagation hooks:** `enrichment_status`/`metadata_date` drive
     re-enrichment; `DATA-01` deaccession rides the snapshot membership diff.

3. **`MET_WORKLIST`** (view; `create_bronze_views.sql`). `CREATE OR REPLACE VIEW`
   (stateless — cannot drift from control). `MET_ENRICHMENT_CONTROL c` JOIN
   `MET_CSV_SNAPSHOT s` on `object_id`. Surfaces 9 cols incl. derived `is_public_domain`,
   `is_highlight`, `department`, `department_priority` (CASE: painting=1, drawing/print=2,
   photograph=3, sculpture=4, else 9). `WHERE claimed_at IS NULL` (free) `AND (status IN
   ('pending','error') OR metadata_date > last_enriched_at OR has_primary_image IS NULL)`.
   `ORDER BY is_public_domain DESC, is_highlight DESC, department_priority ASC,
   object_id ASC`. The Snowflake->Mac half of the two-table contract; requires LOADER
   `SELECT` on BRONZE views (grant landed Session 3). Live free-pending 2026-06-05: **1,827**.

4. **`MET_LEASE_RECLAIM_TASK`** (task; `create_tasks.sql`). Owner `ARTWORK_ADMIN`,
   `WAREHOUSE=ARTWORK_WH`, `SCHEDULE='USING CRON 0 * * * * UTC'` (hourly), state
   `started`. Body: `UPDATE MET_ENRICHMENT_CONTROL SET claimed_by_batch=NULL,
   claimed_at=NULL WHERE claimed_at IS NOT NULL AND claimed_at < DATEADD(minute,-30,
   CURRENT_TIMESTAMP())` — **30-min TTL**. `CREATE OR REPLACE` then `RESUME`. Needs
   `EXECUTE TASK ON ACCOUNT` (granted to `ARTWORK_ADMIN` in lockstep; enforced by the
   `bootstrap.py` contract). TTL-vs-throttling caveat (2026-06-05): under Met API
   throttling ~1 rps a 500-row batch took ~10 min; a batch outliving 30 min can be
   reclaimed mid-flight (concurrent re-claim = wasted work; Bronze stays correct because
   assemble is `object_id`-keyed). Mitigate with `--limit`; raising the TTL is deferred,
   sign-off-gated.

**Flow:** `snapshot` (land CSV) -> `seed-control` (insert `pending` rows for a bounded
slice) -> `enrich-met` (claim from `MET_WORKLIST`, fetch images locally, assemble
`RAW_MET_OBJECTS` server-side, write status back). Source:
`extraction/met/{snapshot_loader,control_seeder,control_enricher}.py`. The enrich step
streams a live `Progress: X/<worklist> done=.. no_image=.. error=..` INFO line every N
completed API calls (2026-06-05 change in `control_enricher.py:_fetch_blocks`).

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

- `create_tasks.sql` + `drop_tasks.sql` — Session-3: real `MET_LEASE_RECLAIM_TASK`
  (hourly CRON, 30-min TTL lease reclaim; created + `RESUME`d). `EXECUTE TASK ON ACCOUNT`
  is now granted to `ARTWORK_ADMIN` (uncommented in `create_roles.sql`, lockstep). [updated 2026-05-31]
  - **TTL-vs-throttling caveat [2026-06-05]:** the 30-min TTL assumed ~20 rps
    (batch finishes in seconds). Observed under Met API throttling: ~1 rps, so a
    500-row batch took ~10 min and a 2000-row batch could exceed the TTL. If a
    batch outlives 30 min, the task can reclaim in-flight rows and a concurrent run
    may re-claim them (wasted work; Bronze stays correct — assemble is `object_id`-
    keyed). Mitigation today: bound `enrich-met` with `--limit`. Raising the TTL is
    a deferred, sign-off-gated decision (comment landed in `create_tasks.sql`).
- `create_service_user.sql` creates `ARTWORK_LOADER_SVC` then CONVERGES it to
  `TYPE = SERVICE` + removed password via idempotent `ALTER USER … SET TYPE = SERVICE;
  UNSET PASSWORD` (because `CREATE … IF NOT EXISTS` cannot alter a pre-existing user).
  Verified 2026-05-31: `TYPE=SERVICE`, `PASSWORD=null`; RSA key registered out-of-band
  by `setup.sh --phase loader` (key-pair only). [updated 2026-05-31]

## Stale `V***` / `R***` / `B***` references to clean up (flagged, not fixed)

- `scripts/manifest.txt` header: "V then R", "(V)", optional "(B)", "repeatable
  R### entries", "skips repeatable R###" (lines ~6–8, 13); also still says it is
  read by `bootstrap.py` though `orchestrate.sh` is now the entry point.
- `infrastructure/drop_grants.sql`: "other V### drop scripts" (line ~11) and
  "grants on the ARTWORK_OPS database from B002" (line ~24).
- `infrastructure/drop_roles.sql`: "applies V### drops in REVERSE order" (line ~9).
- `$(TOOLKIT_DIR)/apply_sql.sh:38` — "Secret-bearing applies (e.g. B001 renders the
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

## Approved cosmetic decisions — APPLIED 2026-05-31

Operator-approved 2026-05-30; applied in Session 3 (committed + `make infra`; see the
"Decision + outcome" block below). Kept as a record of WHAT changed. One carve-out is
still PENDING: item 4's V/R/B rewords were done for `infrastructure/*` only — the garbled
`git-setup/*.sql` comments (section above) and non-infra refs (`config.py`, READMEs,
`.env.example`; see AGENTS.md gated items) are NOT yet done.

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

## Session-2b reconciliation notes (2026-05-31)

Full `infrastructure/` review against the Session-1 strawman + `DDL-04`/`DDL-05`.
Detailed findings and the build-impact map are in `met-deepdive.md` → "Session-2b
DDL review" block. Summary of **net changes for Session 3:**

| What | Where | Kind |
|---|---|---|
| `MET_ENRICHMENT_CONTROL` table DDL | append `create_bronze_tables.sql` | new SQL |
| `MET_CSV_SNAPSHOT` table DDL | append `create_bronze_tables.sql` | new SQL |
| `MET_WORKLIST` view DDL | **new** `create_bronze_views.sql` + manifest entry (after step 7) | new file |
| Paired drop for tables | append `drop_bronze_tables.sql` | new SQL |
| Paired drop for view | **new** `drop_bronze_views.sql` | new file |
| VIEW grant for LOADER | add to `grant_privileges.sql` + `refresh_grants.sql` | new lines |
| Lease-reclaim TASK | fill `create_tasks.sql` placeholder | replace SELECT |
| EXECUTE TASK account grant | uncomment l.45 `create_roles.sql` | uncomment |
| Drop task | fill `drop_tasks.sql` placeholder | replace SELECT |

**Grant gap found:** `grant_privileges.sql` has no `GRANT SELECT ON ALL/FUTURE
VIEWS IN SCHEMA ARTWORK_DB.BRONZE TO ROLE ARTWORK_LOADER`. Today harmless (no
Bronze views exist), but the `MET_WORKLIST` view requires it for the loader's
lease-claim MERGE to read the worklist. Add in Session 3.

**No new stage, file format, or warehouse needed.** Status-callback uses
`bronze_load_stage` with a `/status/met/` path prefix. `MET_CSV_SNAPSHOT` loads
via NDJSON + existing `json_raw` format.

**Gated-decisions collision check: CLEAR.** All four approved-but-pending
decisions (idempotency, UPPERCASE, rename `grant_privileges→create_grants`,
V/R/B comment rewords) are orthogonal to the new objects. Recommended: apply
them first in Session 3 as a pre-patch, then add new objects.

## Session-3 reconciliation (2026-05-31) — dual-instance audit outcome

**Context — dual-instance incident.** Repeated connection drops caused overlapping
Cortex windows; the staged `donkey-kong-sandbox` tree was written across two ghost
clusters (00:51–00:52 and 01:04–01:07 GMT) with NO review trail in the surviving
chat. A new window resumed via `docs/context/session-3-progress-log.md` (append-only
restart trail) and ran a read-only **provenance + reconciliation audit** (no account
execution, no commit) plus an owner-authorized **mirror diff** vs committed baseline
`2e957708`.

**Audit outcome — CLEAN.** Every staged change maps to the Session-2b build-impact
map and/or the four approved cosmetic decisions; ZERO off-spec changes:
- New objects landed on-spec: `MET_ENRICHMENT_CONTROL` + `MET_CSV_SNAPSHOT` (in
  `create_bronze_tables.sql`), `MET_WORKLIST` (new `create_bronze_views.sql`),
  paired `drop_bronze_views.sql`, `MET_LEASE_RECLAIM_TASK` (real `create_tasks.sql`,
  hourly CRON / 30-min TTL / ARTWORK_WH), `drop_tasks.sql`.
- Grant gap fixed: `create_grants.sql` + `refresh_grants.sql` now grant LOADER
  `SELECT ON ALL+FUTURE VIEWS IN BRONZE`.
- All four cosmetic decisions applied: idempotency class-split (tables `IF NOT
  EXISTS`; view/format/stage/task `OR REPLACE`); UPPERCASE identifiers; rename
  `grant_privileges.sql → create_grants.sql` (auto-pairs to `drop_grants.sql` via
  orchestrate's `create_→drop_` rule; manifest updated); stale-comment rewords.
- `create_roles.sql` `EXECUTE TASK ON ACCOUNT` uncommented in lockstep; `bootstrap.py`
  privilege-contract frozenset adds `"EXECUTE TASK"` — verified self-consistent (the
  preflight passes iff both agree; it would fail-fast otherwise).
- Manifest order: `create_bronze_views.sql` inserted after `create_bronze_tables.sql`
  (step 8), before `create_service_user`/`create_tasks`/`refresh_grants`.

**Mirror diff (read-only, owner-authorized) confirmed it independently:** committed
baseline still has `grant_privileges.sql` and lacks both view files → the rename + 2
new files are genuinely uncommitted; all byte-size deltas map to expected edits;
nothing unexplained. (Line-level diff not run — would need a named file format =
ad-hoc DDL; diffed on file-set + size, cross-checked vs full content reads.)

**IaC reproducibility verdict:** *structure — reproducible after audit; working
pipeline — not until Section C.* Idempotency / manifest dep-order / paired-drop
coverage / privilege-contract preflight all PASS. Known gaps deferred to Section C
(NOT this session): (1) data seed not codified — control + snapshot land EMPTY;
(2) AUTH-01 — CLOSED 2026-05-31 (service user now `TYPE=SERVICE`, `PASSWORD=null`,
key-pair verified); (3) dead code `rename_and_update.py` still present.

**Decision + outcome — Option A, APPLIED 2026-05-31 (owner sign-off + execution).**
Owner picked Option A, committed Phase 1 (the 18 reconciled files) on
`donkey-kong-sandbox`, and ran `make infra` locally. The orchestrator applied all 11
manifest scripts cleanly + idempotently (pre-existing → "already exists, statement
succeeded"; new objects created): `MET_ENRICHMENT_CONTROL`, `MET_CSV_SNAPSHOT`,
`MET_WORKLIST` (view), `MET_LEASE_RECLAIM_TASK` (created + `RESUME`d; first hourly run
SUCCEEDED). Privilege preflight passed live, validating the `bootstrap.py` ↔
`create_roles.sql` `EXECUTE TASK` contract; LOADER VIEW grant landed; worklist returns
0 rows pre-seed (bases empty), as designed. (`BRONZE.RUN_CONTROL` checkpoint table was
added + applied the same day; see `create_run_control.sql` + the ad-hoc `$(TOOLKIT_DIR)/check.sh`
suite.)

**Mentor-flag (Section C, not a DDL blocker):** `MET_CSV_SNAPSHOT` and
`MET_ENRICHMENT_CONTROL` now declare PRIMARY KEYs (uniqueness INTENT), but Snowflake does
NOT enforce PK — the 1:1 control×snapshot join guarantee rides on the MERGE load pattern.
Re-landing the snapshot by append (which DATA-01 diff history wants) would still fan out
`MET_WORKLIST`; resolve with a snapshot discriminator/dedup or replace-on-bootstrap when
the seed/diff Python lands.

**Dual-instance note:** this section was authored across overlapping aborted runs; owner
confirmed a single authoritative window (full incident in `session-3-progress-log.md`).
Section C (data seed, dead-code removal, PIPE-06 lease-claim MERGE,
DATA-06 guard, AUTO-03 writes) = NEXT session. (AUTH-01 key-pair CLOSED + verified 2026-05-31.)

## When to escalate to full source

- Changing apply/teardown order → edit `scripts/manifest.txt` (only source of order).
- Changing phase routing, preflight, or secret suppression → `scripts/orchestrate.sh`.
- Adding/altering grants → `create_grants.sql` (renamed from `grant_privileges.sql`;
  + mirror current-grants in `refresh_grants.sql`); rollback stays no-op unless granting
  on persistent non-dropped objects.
- Altering the lease-reclaim task → edit `create_tasks.sql` + `drop_tasks.sql`; the
  `EXECUTE TASK` grant in `create_roles.sql` is already active — keep it in lockstep.
- Adding a new object class → create both `create_<thing>.sql` and
  `drop_<thing>.sql` and add the create to `manifest.txt`.
