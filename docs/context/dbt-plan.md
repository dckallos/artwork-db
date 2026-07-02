# dbt-plan.md -- dbt adoption architecture decisions and milestone plan

> **Tier-1 doc.** Captures locked-in decisions from the 2026-05-31 strategy session.
> This is the authoritative reference for the dbt build arc. No code lives here --
> only the WHAT, WHY, and SHAPE. Implementation details belong in the build window.

## Decisions (locked 2026-05-31, owner sign-off)

### D1. Depth before breadth

Build the Silver/Gold transform layer with dbt for Met data BEFORE adding new data
sources (CMA, AIC, Smithsonian). Rationale: teaches entirely new skills (modeling,
testing, incremental strategy, entity normalization, delete propagation) vs repeating
the ingestion pattern already mastered. Source #2 is more instructive AFTER a proven
spine exists to attach it to.

### D2. Execution engine: dbt Core local (Option L)

- dbt Core runs as a Python CLI on the Mac (virtualenv, `pip install dbt-snowflake`).
- Auth: `profiles.yml` with key-pair auth, `ARTWORK_TRANSFORMER` role.
- Future migration path: Option H (hybrid) -- author locally, deploy as a Snowflake-
  native `CREATE DBT PROJECT` object scheduled by Tasks. This is a FUTURE milestone,
  not a current constraint.
- Airflow compatibility: Option L is the natural fit for Airflow orchestration if/when
  adopted. Airflow calls `dbt build` via BashOperator or Cosmos. The Snowflake-native
  path (Option N) conflicts with external orchestrators.

### D3. Pragmatic star schema in Gold

- **Star core:** `dim_artworks`, `dim_artists`, `fct_artwork_images` -- proper
  dimensional model with surrogate keys and FK relationships.
- **Artist-artwork relationship:** Met artworks can have MULTIPLE artists (pipe-
  delimited constituent fields). For M1-M2 simplicity, model as one PRIMARY artist
  per artwork (FK on `dim_artworks`). If multi-artist becomes important, add a bridge
  table (`bridge_artwork_artists`) in a later milestone. This is a documented
  simplification, not an oversight.
- **OBT convenience layer:** `openaccess_catalog` -- wide denormalized table/view for
  BI/app consumption. Pre-joined, filtered to public-domain artworks with images.
- **Images at their own grain:** One row per image URL per artwork in
  `fct_artwork_images`. Justified by one-to-many relationship (primary + additional
  images). Usage is URL-catalog-only (no Cortex image processing planned).
- **Source-neutral Gold naming:** `dim_artworks` not `dim_met_artworks`. A
  `source_system` column (= `'met'` today) provides the thin abstraction for future
  multi-source union without over-engineering now.

### D4. dbt as a peer IaC track

dbt does NOT live inside the IaC toolkit orchestrator/`manifest.txt`. It is a parallel Makefile
target that runs AFTER infrastructure. Rationale: clean separation of concerns; each
tool owns its domain; the Makefile encodes the dependency order.

Execution model:
```
make all
  |-- make infra          [current: sibling snowflake-toolkit -> manifest.txt -> snow sql]
  |-- make dbt-build      [new: dbt_orchestrate.sh --phase build]
  |-- make bootstrap      [existing: git-setup, runs LAST]
```

### D5. Unified variable control

A single `.env` file is the source of truth for connection variables:
- Account, role, warehouse, database, schema, key path.
- `dbt_orchestrate.sh` reads `.env` and generates/validates `profiles.yml`.
- The same `.env` feeds `connections.toml` (Snowflake CLI) and `config.py`
  (extraction loader).
- One place to change a value; all consumers read from it.
- `profiles.yml` uses `env_var()` Jinja function to reference environment variables
  (set by the orchestration script from `.env`), keeping secrets/paths out of the
  checked-in file.

### D6. Error handling and rollback strategy

- `dbt build` (not separate `dbt run` + `dbt test`) is the default command --
  interleaves tests with model execution so failures halt downstream propagation.
- `dbt retry` for recovering from transient failures (reruns only failed nodes).
- `--full-refresh` as the nuclear reset for incremental models in bad state.
- No explicit rollback mechanism. dbt's idempotency = re-run produces correct state.
- Bronze is never touched by dbt. Silver/Gold are fully re-derivable from Bronze.
- Schema-level teardown for full reset: DROP + recreate Silver/Gold schemas, then
  `make infra` (restores grants) + `make dbt-build` (repopulates).

### D7. Completeness testing: dbt tests (in-DAG)

- dbt tests for per-model sanity: `not_null`, `unique`, `accepted_values`,
  `relationships` (FK integrity).
- Custom generic test: `row_count_delta` comparing Silver/Gold counts to Bronze source
  (with tolerance for intentionally filtered rows like non-public-domain).
- `store_failures: true` on critical tests for post-mortem inspection.
- Separate reconciliation task is DEFERRED until source #2 or production scheduling
  creates a cross-pipeline gap that dbt tests cannot cover.

---

## DAG Shape (Silver/Gold model structure)

```
Bronze (raw, existing)
  BRONZE.RAW_MET_OBJECTS (VARIANT, 1 row per object)

Silver (cleaned, typed, source-specific)
  stg_met__artworks      1 row per artwork; flattens csv + api_images into typed cols
  stg_met__artists       1 row per artist; parsed from artistDisplayName/Begin/End/etc
  stg_met__images        1 row per image URL per artwork (primary + additionals)

Gold (business-ready, source-agnostic naming)
  dim_artworks           Canonical artwork dimension; FK to dim_artists
  dim_artists            Canonical artist entity (source_system='met' today)
  fct_artwork_images     One row per image; FK to dim_artworks; is_primary + ordinal
  openaccess_catalog     Wide denormalized OBT; isPublicDomain=true + has image URL
```

### Model responsibilities

| Model | Grain | Materialization | Key logic |
|---|---|---|---|
| `stg_met__artworks` | 1 row per `objectID` | view (M1-M2); incremental table (M3) | VARIANT flattening, type casting, null standardization |
| `stg_met__artists` | 1 row per distinct artist | view | Dedup, handle "Unknown"/null, parse compound names, pick PRIMARY artist per artwork |
| `stg_met__images` | 1 row per image URL per artwork | view | LATERAL FLATTEN on additional_images + primary |
| `dim_artworks` | 1 row per artwork (surrogate key) | table | Joins artist FK, adds source_system, business naming |
| `dim_artists` | 1 row per artist (surrogate key) | table | Cleaned attributes, source-neutral column contract |
| `fct_artwork_images` | 1 row per image per artwork | table | artwork FK, image_url, is_primary, image_ordinal |
| `openaccess_catalog` | 1 row per artwork (filtered) | table (or view -- decide in M3) | Pre-joined wide table, only public-domain + has image |

**Materialization rationale:**
- Silver staging models start as **views** (zero storage cost, always fresh from
  Bronze, fast iteration during development). In M3, `stg_met__artworks` becomes
  **incremental** to support hard-delete propagation.
- Gold models are **tables** (query performance for consumers; acceptable staleness
  since dbt builds on a schedule).

### Data-quality cornerstone mapping

| Cornerstone | Mechanism |
|---|---|
| Deaccession / delete propagation | Two modes: (1) `--full-refresh` rebuilds from Bronze (rows gone from Bronze simply don't appear -- trivial). (2) **Incremental delete** (the hard problem): on normal runs, detect rows present in Silver but absent from Bronze and DELETE them. Exact strategy (microbatch delete step, pre-hook anti-join, or merge with delete clause) is research question #4. |
| Entity normalization (artists) | Logic in `stg_met__artists` (dedup, null handling, compound names). Gold `dim_artists` is canonical output. |
| Completeness | dbt tests: `relationships` (FK integrity), `not_null` on keys, custom `row_count_delta` Bronze-to-Gold. |
| Timeliness | dbt `freshness` source definition checking `_meta.loaded_at` in Bronze. |

---

## IaC Integration Design

### File/directory structure (planned)

```
artwork_pipeline/                  # dbt project root (NEW)
  dbt_project.yml
  packages.yml                     # dbt-utils
  profiles.yml                     # env_var() references, key-pair auth
  models/
    staging/
      met/
        _met__sources.yml
        _met__models.yml
        stg_met__artworks.sql
        stg_met__artists.sql
        stg_met__images.sql
    marts/
      _marts__models.yml
      dim_artworks.sql
      dim_artists.sql
      fct_artwork_images.sql
      openaccess_catalog.sql
  tests/
    generic/
      row_count_delta.sql
  macros/                          # if needed beyond dbt-utils

scripts/
  dbt_orchestrate.sh               # peer to the IaC toolkit orchestrator
  dbt_teardown.sh                  # NEW: schema-level reset (or phase of above)

Makefile                           # MODIFIED: new targets added
.env                               # MODIFIED: canonical source of truth for all vars
.env.example                       # MODIFIED: documents all required vars
```

### `dbt_orchestrate.sh` phases

| Phase | What it does | Equivalent |
|---|---|---|
| `--phase init` | Create/verify virtualenv, pip install dbt-snowflake, `dbt deps`, `dbt debug` | `setup.sh --phase loader` |
| `--phase build` | Source `.env`, export vars, run `dbt build` | the IaC apply path |
| `--phase test` | `dbt test` only (no model execution) | `check.sh` |
| `--phase teardown` | DROP + recreate Silver/Gold schemas, restore grants | `rollback_sql.sh` |
| `--phase full-refresh` | `dbt build --full-refresh` | nuclear reset for incrementals |

### Makefile targets (additions)

```makefile
dbt-init:           scripts/dbt_orchestrate.sh --phase init
dbt-build:          scripts/dbt_orchestrate.sh --phase build
dbt-test:           scripts/dbt_orchestrate.sh --phase test
dbt-teardown:       scripts/dbt_orchestrate.sh --phase teardown
dbt-full-refresh:   scripts/dbt_orchestrate.sh --phase full-refresh
all:                infra dbt-build bootstrap
```

### Object ownership contract

| Schema | Owned by | Created by | Populated by |
|---|---|---|---|
| BRONZE | `make infra` | `create_schemas.sql` | Extraction Python loader |
| SILVER | `make dbt-build` | `create_schemas.sql` (empty shell) | dbt models |
| GOLD | `make dbt-build` | `create_schemas.sql` (empty shell) | dbt models |

Rule: infra creates empty schemas + grants; dbt fills them. No DDL script creates
tables in Silver/Gold. No dbt model touches Bronze structure.

### Variable unification (.env as single source)

```
# .env (source of truth -- all consumers read from here)
SNOWFLAKE_ACCOUNT=pa37992
SNOWFLAKE_DATABASE=ARTWORK_DB
SNOWFLAKE_WAREHOUSE=COMPUTE_WH

# dbt (transform layer) -- uses ARTWORK_TRANSFORMER role
DBT_SNOWFLAKE_ROLE=ARTWORK_TRANSFORMER
DBT_SNOWFLAKE_USER=PORCHANALYTICS
DBT_SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/artwork_transformer_key.p8
DBT_SNOWFLAKE_SCHEMA_SILVER=SILVER
DBT_SNOWFLAKE_SCHEMA_GOLD=GOLD

# Extraction (loader) -- uses ARTWORK_LOADER role
LOADER_SNOWFLAKE_USER=ARTWORK_LOADER_SVC
LOADER_SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/artwork_loader_key.p8

# Consumers:
# - profiles.yml        -> env_var('DBT_SNOWFLAKE_ROLE'), etc.
# - connections.toml    -> referenced by snow CLI (multiple connections)
# - config.py           -> extraction loader (LOADER_* vars)
# - dbt_orchestrate.sh  -> sources .env, exports DBT_* vars, calls dbt
```

---

## Milestone Sequence

### M1: Project scaffold + stg_met__artworks + IaC wiring

**Build:**
- Initialize `artwork_pipeline/` (dbt_project.yml, profiles.yml, packages.yml)
- Write `scripts/dbt_orchestrate.sh` with all phases
- Add Makefile targets
- Unify `.env` as single variable source
- Write `stg_met__artworks` (VARIANT flatten, type cast)
- Basic tests: `unique`/`not_null` on object_id

**Learn:**
- dbt project anatomy, `source()` macro, VARIANT flattening in dbt SQL
- `dbt build` lifecycle, `profiles.yml` connection model
- IaC integration: how dbt fits alongside existing orchestration

**Exit criteria:** `make dbt-build` passes on a clean account (after `make infra`).
`SILVER.STG_MET__ARTWORKS` exists with typed columns and passes tests.

### M2: Artist entity + image fact + Gold dimensions

**Build:**
- `stg_met__artists` (distinct artist extraction, null/compound-name handling)
- `stg_met__images` (LATERAL FLATTEN on additional_images + primary)
- `dim_artists` and `dim_artworks` in Gold (surrogate keys, source_system)
- `fct_artwork_images` in Gold
- Relationship tests (FK integrity across models)

**Learn:**
- Entity extraction and deduplication
- LATERAL FLATTEN in Snowflake SQL
- Surrogate key generation (dbt_utils.generate_surrogate_key)
- `ref()` chains and DAG dependency graph
- Relationship tests across schemas

**Exit criteria:** `dbt build` passes across both schemas. `dim_artists` has one row
per distinct artist. `fct_artwork_images` has one row per image URL per artwork.

### M3: Delete propagation + openaccess_catalog + completeness

**Build:**
- Make `stg_met__artworks` incremental with hard-delete support
- Build `openaccess_catalog` wide OBT (filtered, pre-joined)
- Custom `row_count_delta` completeness test
- `store_failures: true` on critical tests

**Learn:**
- dbt incremental materialization (`is_incremental()`, merge strategy)
- Hard-delete propagation (the DATA-01 gap)
- `--full-refresh` as recovery mechanism
- Custom generic tests
- OBT pattern: when and why to denormalize on top of a star
- Materialization choice: table vs view for the OBT

**Exit criteria:** `dbt build` passes. Deleting a row from Bronze and re-running
causes it to disappear from Gold. Completeness test quantifies the Bronze-to-Gold
delta and explains it.

---

## Future milestones (horizon, not commitments)

- **M4:** Source #2 (CMA) -- `stg_cma__artworks`/`stg_cma__artists`, artist entity
  resolution model merging into existing `dim_artists`.
- **M5:** Migrate to Option H (hybrid) -- `CREATE DBT PROJECT` object + Snowflake
  Task scheduling for production runs. Local dbt Core remains for dev.
- **M6:** Blue/green schema swap on Gold for production safety.
- **M7:** dbt docs + lineage visualization.
- **M8:** Source freshness monitoring and alerting.
- **M9:** Airflow integration (if/when decided) -- Cosmos or BashOperator calling
  `dbt_orchestrate.sh --phase build`.

---

## Open research questions (for the design window)

These need investigation before M1 implementation begins:

1. **`env_var()` in `profiles.yml`:** Exact syntax for key-pair auth with env vars.
   Does dbt-snowflake support `private_key_path` via `env_var()`? Or must it be
   `private_key_content` (base64-encoded)? What is the exact YAML shape?
2. **dbt-utils version compatibility:** Which version of `dbt_utils` is compatible
   with the current `dbt-snowflake` adapter? Surrogate key macro availability
   (renamed to `generate_surrogate_key` or `surrogate_key` in newer versions?).
3. **VARIANT flattening patterns in dbt:** Best practice for flattening nested VARIANT
   in a staging model -- inline `raw:csv:objectID::INT` vs a macro vs a CTE chain.
   Also: does the `source()` ref work directly with VARIANT columns or does dbt need
   a `raw_column` workaround?
4. **Incremental + hard-delete strategy:** Exact dbt config for achieving hard deletes
   on incremental models in Snowflake. `incremental_strategy = 'delete+insert'` vs
   `merge` with a custom delete step vs a pre-hook anti-join DELETE. Which approach
   works when the "absent from source" signal is "row doesn't exist in Bronze anymore"?
   This is the DATA-01 gap and the hardest design question.
5. **Schema grants after dbt creates objects:** Does `dbt run` respect existing
   `FUTURE GRANTS` on the schema, or do new tables need explicit grants? Impact on
   `ARTWORK_TRANSFORMER` role permissions. Does the `grants` config in dbt_project.yml
   help here?
6. **dbt project naming and profile linkage:** `artwork_pipeline` vs `artwork_transforms`
   vs `artwork_dbt` -- which aligns with community conventions? The `profile:` key in
   `dbt_project.yml` must match the profile name in `profiles.yml` -- document the
   exact linkage.
7. **Variable orchestration layer (INFRASTRUCTURE, not dbt):** This is a script-
   engineering question, not a dbt question. The `.env` file feeds three consumers
   (`profiles.yml` via `env_var()`, `connections.toml` for `snow` CLI, `config.py`
   for extraction). Design questions:
   - How does `dbt_orchestrate.sh` validate all required vars are present BEFORE
     invoking dbt? (Fail early with clear error vs. let dbt fail cryptically.)
   - What does dbt's error look like when `env_var()` references an unset variable?
     (Needed to write a useful "did you forget to source .env?" message.)
   - Should there be a `make check-env` target that verifies cross-consumer
     consistency (e.g., same account/warehouse in `.env` and `connections.toml`)?
   - As variables are added/renamed, what prevents drift between the three consumers?
     (Convention + comments? A validation script? A single-source template?)
