# artwork_pipeline

dbt project implementing the Medallion architecture (Bronze -> Silver -> Gold) over Met Museum OpenAccess data in Snowflake.

## Architecture

```
ARTWORK_DB.BRONZE              ARTWORK_DB.SILVER              ARTWORK_DB.GOLD
+---------------------+        +------------------------+     +---------------------+
| RAW_MET_OBJECTS     | -----> | stg_met__artworks      | --> | dim_artworks        |
| MET_ENRICHMENT_CTRL |        | stg_met__artists       |     | dim_artists         |
|                     |        | stg_met__images        |     | fct_artwork_images  |
|                     |        | stg_met__enrichment_   |     | openaccess_catalog  |
|                     |        |   status               |     |                     |
+---------------------+        +------------------------+     +---------------------+
       (sources)                    (views)                        (tables)
```

**Staging (Silver):** Views that parse the Bronze VARIANT payloads into typed, snake_case columns. No data copies; compute-on-read.

**Marts (Gold):** Materialized tables for consumption. Surrogate keys, business logic, and denormalized facts ready for analytics.

## Prerequisites

| Requirement | Details |
|---|---|
| dbt-core | >= 1.7 with dbt-snowflake adapter |
| Snowflake role | `ARTWORK_TRANSFORMER` (assumed by `ARTWORK_TRANSFORMER_SVC`) |
| Auth (local) | Key-pair: `~/.snowflake/keys/mk07348_transformer_rsa_key.p8` |
| Auth (Snowflake-native) | Session-inherited (no credentials needed) |
| Warehouse | `ARTWORK_WH` (XS, auto-suspend 60s) |
| Upstream data | `BRONZE.RAW_MET_OBJECTS` populated by the extraction pipeline |

## Quick Start

```bash
cd artwork_pipeline

# Install dbt packages (run once, or after editing packages.yml)
dbt deps

# Validate connection
dbt debug

# Full pipeline run
dbt build
```

## Execution Targets

This project has two profiles configured in `profiles.yml`:

### Local (Mac, dbt Core CLI)

```bash
# Default target -- uses key-pair auth as ARTWORK_TRANSFORMER_SVC
dbt run --target dev

# Required env vars (export from .env or shell):
export SNOWFLAKE_ACCOUNT=OBANOYY-MK07348
export DBT_SNOWFLAKE_USER=ARTWORK_TRANSFORMER_SVC
export DBT_SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/mk07348_transformer_rsa_key.p8
export SNOWFLAKE_DATABASE=ARTWORK_DB
export SNOWFLAKE_WAREHOUSE=ARTWORK_WH
# Optional (have defaults):
# export DBT_SNOWFLAKE_ROLE=ARTWORK_TRANSFORMER
# export DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=
```

### Snowflake-Native (Workspace / EXECUTE DBT PROJECT)

```bash
# Uses session auth -- no credentials, no env_var()
dbt run --target snowflake
```

## Common Workflows

### Run the full pipeline

```bash
dbt build                          # run + test all models
dbt build --full-refresh           # rebuild tables from scratch (GOLD)
```

### Run a specific layer

```bash
# Staging only (Silver views)
dbt run --select staging

# Marts only (Gold tables)
dbt run --select marts

# Single model + all upstream deps
dbt run --select +dim_artworks
```

### Run by tag

```bash
dbt run --select tag:met           # All Met-sourced models
dbt run --select tag:staging       # All staging models
dbt run --select tag:marts         # All mart models
```

### Testing

```bash
# Run all tests (schema + data + custom)
dbt test

# Test one model
dbt test --select stg_met__artworks

# Source freshness check
dbt source freshness
```

### Development utilities

```bash
# Generate YAML stubs for a new source table
dbt run-operation generate_source --args '{"schema_name": "BRONZE", "database_name": "ARTWORK_DB", "table_names": ["MY_NEW_TABLE"]}'

# Generate a base model from an existing source
dbt run-operation generate_base_model --args '{"source_name": "met", "table_name": "raw_met_objects"}'

# Compile SQL without executing (inspect target/compiled/)
dbt compile --select stg_met__artworks

# Show query results inline
dbt show --select stg_met__artworks --limit 20
```

### DAG hygiene audit

```bash
# Build the project evaluator models (creates audit views in DBT_TEST__AUDIT)
dbt build --select package:dbt_project_evaluator
```

### Cost monitoring

```bash
# Build Snowflake monitoring models (requires ACCOUNT_USAGE access)
dbt run --select package:dbt_snowflake_monitoring
```

## Project Structure

```
artwork_pipeline/
|-- dbt_project.yml          # Project config, materializations, tags
|-- profiles.yml             # Connection profiles (dev + snowflake targets)
|-- packages.yml             # External packages (dbt_utils, expectations, etc.)
|-- macros/
|   |-- generate_schema_name.sql   # Routes models to SILVER/GOLD (no prefix)
|   |-- override_create_schema.sql # Prevents dbt from creating schemas (IaC-owned)
|-- models/
|   |-- staging/met/
|   |   |-- _met__sources.yml           # Source definitions (Bronze tables)
|   |   |-- _met__models.yml            # Model docs + column-level tests
|   |   |-- stg_met__artworks.sql       # Core artwork attributes
|   |   |-- stg_met__artists.sql        # Artist extraction + normalization
|   |   |-- stg_met__images.sql         # Image URL parsing
|   |   |-- stg_met__enrichment_status.sql  # Enrichment lifecycle tracking
|   |-- marts/
|       |-- _marts__models.yml          # Mart model docs + tests
|       |-- dim_artworks.sql            # Artwork dimension
|       |-- dim_artists.sql             # Artist dimension (entity-resolved)
|       |-- fct_artwork_images.sql      # Image fact table
|       |-- openaccess_catalog.sql      # Wide denormalized catalog
|-- tests/
|   |-- generic/                        # Custom generic test definitions
|-- target/                             # Compiled output (git-ignored)
|-- dbt_packages/                       # Installed packages (git-ignored)
```

## Schema Routing

The `generate_schema_name` macro uses an **allowlist** pattern:

| Model layer | `+schema` config | Lands in |
|---|---|---|
| staging | _(none, inherits target)_ | `ARTWORK_DB.SILVER` |
| marts | `GOLD` | `ARTWORK_DB.GOLD` |
| project_evaluator | `DBT_TEST__AUDIT` | `ARTWORK_DB.DBT_TEST__AUDIT` |

Unapproved schema names fail at **compile time** (not runtime). To add a new schema:
1. Create it in `infrastructure/create_schemas.sql`
2. Grant access in `infrastructure/create_grants.sql`
3. Run `make infra`
4. Add the name to `allowed_schemas` in `macros/generate_schema_name.sql`

## Packages

| Package | Purpose |
|---|---|
| `dbt_utils` | Surrogate keys, date spines, generic tests |
| `codegen` | Dev-time YAML/model generation from existing tables |
| `dbt_expectations` | 50+ statistical/shape tests (Great Expectations-style) |
| `audit_helper` | Row/column comparison during refactoring |
| `dbt_project_evaluator` | DAG hygiene, naming conventions, fanout checks |
| `dbt_snowflake_monitoring` | Per-query/model cost attribution |

## Key Design Decisions

- **Views for staging, tables for marts.** Staging views avoid data duplication (Bronze is the single copy); Gold tables optimize read-heavy analytics queries.
- **`copy_grants: true` globally.** Prevents privilege loss when dbt runs `CREATE OR REPLACE` (FUTURE GRANTS do not re-fire on OR REPLACE).
- **Schema creation disabled.** The `override_create_schema` macro is a no-op; schemas are owned by IaC (`make infra`), not dbt.
- **No per-developer schema prefixing.** Single-developer project today. The macro is the single edit point when multi-dev is adopted.
- **Source freshness on Bronze.** Warns after 7 days without new data in `RAW_MET_OBJECTS`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Schema 'X' is not in the approved list` | Typo in `+schema` config | Check `generate_schema_name.sql` allowlist |
| `Object does not exist: RAW_MET_OBJECTS` | Extraction pipeline hasn't run | Run `python -m extraction.met.run snapshot` then `enrich-met` |
| `Insufficient privileges` | Wrong role | Ensure `ARTWORK_TRANSFORMER` role has SELECT on BRONZE, WRITE on SILVER/GOLD |
| `env_var('X') not found` | Missing export | Source your `.env` or set the variable in shell |
| Stale staging data | Views read Bronze live | Re-run extraction; no dbt action needed |
| `dbt deps` fails | Network/version issue | Check `packages.yml` version pins; retry |
