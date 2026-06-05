# Unit 1: First Green Run

> Started: 2026-06-05  |  Completed: 2026-06-05

## Objectives

- Execute `dbt deps` + `dbt run` against the existing `stg_met__artworks` model.
- Observe a VIEW materialize in `ARTWORK_DB.SILVER`.
- Understand what dbt generates under the hood (the compiled SQL).
- Learn why `copy_grants: true` matters from day 1.
- Practice diagnosing a Snowflake auth error via a deliberate role misconfiguration.

---

## Environment Setup (do this ONCE before your first `dbt run`)

### How `profiles.yml` finds its values

dbt's `env_var()` Jinja function reads from **shell environment variables at
invocation time**. It does NOT read `.env` files directly. The `.env` file is just
a flat key=value file sitting on disk -- dbt has no idea it exists.

The bridge between them is one of:
1. **`dbt_orchestrate.sh`** -- sources `.env` with `set -a` (auto-export) then
   invokes dbt. All vars become real env vars for dbt's process.
2. **Manual export** -- you source it yourself before running bare `dbt` commands.
3. **direnv / dotenv shell plugin** -- auto-loads `.env` when you `cd` into the repo.

### Required env vars for `profiles.yml`

| Variable | Source in `.env` | Default in profiles.yml | Notes |
|----------|-----------------|------------------------|-------|
| `SNOWFLAKE_ACCOUNT` | `OBANOYY-MK07348` | _(none -- required)_ | orgname-accountname format |
| `DBT_SNOWFLAKE_USER` | `ARTWORK_TRANSFORMER_SVC` | _(none -- required)_ | service user, TYPE=SERVICE |
| `DBT_SNOWFLAKE_PRIVATE_KEY_PATH` | `~/.snowflake/keys/mk07348_transformer_rsa_key.p8` | _(none -- required)_ | absolute or ~ path to PEM key |
| `SNOWFLAKE_WAREHOUSE` | `ARTWORK_WH` | `ARTWORK_WH` | has a default, but set it anyway |
| `SNOWFLAKE_DATABASE` | `ARTWORK_DB` | `ARTWORK_DB` | has a default, but set it anyway |
| `DBT_SNOWFLAKE_ROLE` | `ARTWORK_TRANSFORMER` | `ARTWORK_TRANSFORMER` | optional (has default) |
| `DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | _(empty if key is unencrypted)_ | `''` | optional |

### Is having `.env` in the working directory enough?

**No.** A `.env` file is just text. dbt will error with:

```
Env var required but not provided: 'SNOWFLAKE_ACCOUNT'
```

You need the variables **exported into your shell**. Two options:

**Option A (recommended for learning): source manually**
```bash
cd /path/to/artwork-db
set -a; source .env; set +a     # -a auto-exports every variable set
cd artwork_pipeline
dbt deps
dbt run
```

**Option B (production path): use the orchestrator**
```bash
scripts/dbt_orchestrate.sh --phase build
```
This sources `.env`, validates the 5 required vars, then calls `dbt build`.
It handles everything. But for Unit 1, do Option A so you see exactly what
happens at each layer.

### Verification: are my vars exported?

```bash
echo $SNOWFLAKE_ACCOUNT         # should print OBANOYY-MK07348
echo $DBT_SNOWFLAKE_USER        # should print ARTWORK_TRANSFORMER_SVC
echo $DBT_SNOWFLAKE_PRIVATE_KEY_PATH   # should print a path ending in .p8
ls -la $DBT_SNOWFLAKE_PRIVATE_KEY_PATH  # should exist and be readable
```

If any of these are blank, your `.env` was not sourced (or the var name has a
typo). If the key file doesn't exist, you need to run `make transformer
CONN=mk07348` first (which mints the key + registers it with Snowflake).

---

## Commands to Run (in order)

### Step 1: Export environment

```bash
cd ~/path/to/artwork-db          # your repo root
set -a; source .env; set +a
```

**Why `set -a`?** Without it, `source .env` sets variables in the current shell
but does NOT export them. Child processes (like `dbt`) would not see them.
`set -a` makes every variable assignment automatically exported. `set +a` turns
that mode back off (so subsequent commands don't accidentally export everything).

### Step 2: Install packages

```bash
cd artwork_pipeline
dbt deps
```

**What this does:** reads `packages.yml`, downloads `dbt_utils` and `codegen` into
`dbt_packages/` (gitignored). This is like `npm install` -- idempotent, safe to
re-run, required before first use.

**Expected output:**
```
Installing dbt-labs/dbt_utils
Installed from version 1.x.x
Installing dbt-labs/codegen
Installed from version 0.14.x
```

### Step 3: Run models

```bash
dbt run
```

**What this does for `stg_met__artworks` (materialized as view):**

1. Connects to Snowflake as `ARTWORK_TRANSFORMER_SVC` / role `ARTWORK_TRANSFORMER`.
2. Compiles the Jinja SQL: resolves `{{ source('met', 'raw_met_objects') }}` to
   the literal `ARTWORK_DB.BRONZE.RAW_MET_OBJECTS`.
3. Executes: `CREATE OR REPLACE VIEW ARTWORK_DB.SILVER.STG_MET__ARTWORKS AS (...)`.
4. Because `copy_grants: true` is set globally, the actual DDL is:
   `CREATE OR REPLACE VIEW ... COPY GRANTS AS (...)`.

**Expected output:**
```
Found 1 model, ...
Concurrency: 4 threads (1 max)

1 of 1 START sql view model SILVER.STG_MET__ARTWORKS ........................ [RUN]
1 of 1 OK created sql view model SILVER.STG_MET__ARTWORKS ................... [SUCCESS 1 in 0.xxs]

Finished running 1 view model in 0 hours ...
Completed successfully
Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

### Step 4: Verify in Snowflake

After `dbt run` succeeds, verify the view exists. Run these read-only queries
(either in Snowsight or via `snow sql`):

```sql
SHOW VIEWS IN SCHEMA ARTWORK_DB.SILVER;
-- Expect one row: STG_MET__ARTWORKS

SELECT COUNT(*) FROM ARTWORK_DB.SILVER.STG_MET__ARTWORKS;
-- Expect: 503 (same as BRONZE.RAW_MET_OBJECTS)

-- Spot-check a row:
SELECT object_id, title, artist_display_name, primary_image_url
FROM ARTWORK_DB.SILVER.STG_MET__ARTWORKS
LIMIT 5;
```

### Step 5: Inspect compiled SQL

```bash
cat target/compiled/artwork_pipeline/models/staging/met/stg_met__artworks.sql
```

**Why this matters:** The `target/compiled/` directory shows you the FINAL SQL
that dbt sent to Snowflake, with all Jinja resolved. This is your debugging
superpower -- when something fails, look here first. You'll see:
- `{{ source(...) }}` replaced with `ARTWORK_DB.BRONZE.RAW_MET_OBJECTS`
- No Jinja left -- pure SQL
- The exact SQL Snowflake received

Also check:
```bash
cat target/run/artwork_pipeline/models/staging/met/stg_met__artworks.sql
```

The `target/run/` version wraps the compiled SQL in the DDL statement
(`CREATE OR REPLACE VIEW ... COPY GRANTS AS (...)`). This is the *actual*
statement executed against Snowflake.

---

## Deliberate Failure Exercise: Wrong Role

**After** the green run succeeds, do this to practice reading dbt's error output:

```bash
export DBT_SNOWFLAKE_ROLE=SYSADMIN    # a role that exists but lacks ARTWORK_DB grants
dbt run
```

**What you will see:** dbt connects successfully (SYSADMIN is a real role the user
can assume), but the CREATE VIEW fails because SYSADMIN does not have:
- USAGE on database ARTWORK_DB
- USAGE on schema ARTWORK_DB.SILVER
- SELECT on ARTWORK_DB.BRONZE.RAW_MET_OBJECTS

The error will look something like:
```
Database Error in model stg_met__artworks
  SQL compilation error: Object 'ARTWORK_DB.BRONZE.RAW_MET_OBJECTS' does not exist
  or not authorized.
```

**Key lesson:** "does not exist or not authorized" is Snowflake's way of saying
"your role can't see this object." It's intentionally ambiguous (security -- don't
reveal whether the object exists to someone who lacks access). When you see this
error in production, FIRST check what role dbt is running as.

**Recovery:**
```bash
export DBT_SNOWFLAKE_ROLE=ARTWORK_TRANSFORMER
dbt run
```

Should go green again (the view already exists, but `CREATE OR REPLACE` is
idempotent -- it just replaces it with the same definition).

---

## Decisions Made

- **Profile strategy:** Dual-mode `profiles.yml` (dev target for Mac key-pair,
  snowflake target for native execution). Keeps one file for both contexts.
- **Governance macros (MVG-1 + MVG-2):** Implemented as dbt-layer code (developer
  UX), not DBA enforcement. DBA enforcement = Snowflake RBAC grants (no CREATE
  SCHEMA on the transformer role). Macro is the sign on the door; RBAC is the lock.

## Errors Encountered

### Real: CREATE SCHEMA privilege denied
- Command: `dbt run` (first attempt, before macros existed)
- Error: `003001 (42501): Insufficient privileges to operate on database
  'ARTWORK_DB'. Your primary role ARTWORK_TRANSFORMER must have CREATE SCHEMA
  granted on DATABASE ARTWORK_DB.`
- Diagnosis: dbt's default behavior runs `CREATE SCHEMA IF NOT EXISTS` before
  every model. ARTWORK_TRANSFORMER intentionally lacks this privilege.
- Fix: Created `macros/override_create_schema.sql` (no-op macro). Suppresses the
  DDL attempt entirely. Schema lifecycle stays with IaC.

### Real: generate_schema_name allowlist rejected dbt_test__audit
- Command: `dbt run` (second attempt, after adding generate_schema_name macro)
- Error: `Compilation Error: Schema 'dbt_test__audit' is not in the approved list`
- Diagnosis: dbt pre-resolves schema names for ALL possible outputs during
  compilation, including the test-failure audit schema, even when no tests use
  `store_failures`. Our allowlist correctly rejected it.
- Fix: Added `DBT_TEST__AUDIT` to the allowlist. Schema doesn't need to exist in
  Snowflake until `store_failures: true` is actually enabled (Unit 2 territory).
- Lesson: The allowlist guard works as designed -- it catches things early. The
  fix is to expand the approved list for legitimate use cases, not remove the guard.

### Skipped: Deliberate wrong-role exercise
- Not performed this session (time spent on governance framework instead).
- The real errors above provided equivalent diagnostic practice.

---

## Teaching Notes: Why `copy_grants` Matters

When dbt materializes a view, it uses `CREATE OR REPLACE`. This DROPS the old
view and creates a new one. In Snowflake, a new object has NO grants -- even if
FUTURE GRANTS exist on the schema.

**Why?** FUTURE GRANTS fire only on `CREATE` of objects that did NOT previously
exist. `CREATE OR REPLACE` is semantically a drop+create of the SAME object name.
Snowflake's behavior: FUTURE GRANTS do NOT re-fire on OR REPLACE.

Without `copy_grants`, every `dbt run` would strip grants from your views. Any
downstream role (e.g., a BI tool reading from SILVER) would lose access after each
dbt refresh. With `copy_grants: true`, the replacement object inherits all grants
from its predecessor.

This is why the project sets it globally in `dbt_project.yml`:
```yaml
models:
  artwork_pipeline:
    +copy_grants: true
```

You set it once, forget it exists, and never lose grants.

---

## Key Takeaways (written by AI after unit completes)

1. **`.env` is not enough -- you must export.** dbt's `env_var()` reads shell
   environment variables, not dotfiles. Use `set -a; source .env; set +a` or
   let `dbt_orchestrate.sh` handle it.

2. **dbt is a DDL engine.** Every `dbt run` executes `CREATE OR REPLACE` against
   Snowflake. Understanding this means understanding that dbt's power IS the risk.

3. **Governance lives at two layers: Snowflake RBAC (enforcement) and dbt macros
   (developer UX).** The DBA's grants are the lock; the macros are the sign on
   the door. Neither depends on the other, but together they provide defense in
   depth.

4. **`copy_grants: true` is non-negotiable.** Without it, every `dbt run` strips
   grants from replaced objects. FUTURE GRANTS do NOT re-fire on `OR REPLACE`.
   Set it globally in `dbt_project.yml` and never think about it again.

5. **`target/compiled/` is your debugging superpower.** It shows the final SQL
   with all Jinja resolved. When something breaks, look there first.

6. **dbt's `generate_schema_name` default concatenates prefixes** (producing
   `SILVER_GOLD`). Override it to use schema names verbatim for a medallion
   architecture with peer schemas.

7. **Dual-mode `profiles.yml` works.** One file with two targets (dev = key-pair
   on Mac, snowflake = session auth in native execution) keeps the project
   deployable in both contexts without branching.

8. **The allowlist pattern catches mistakes at compile time.** Better to get a
   clear "not in approved list" error during `dbt compile` than a cryptic
   Snowflake permission error at runtime. Expand the list deliberately, not
   reactively.
