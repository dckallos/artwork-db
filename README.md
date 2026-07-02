# artwork-db

`artwork-db` is the project-specific repository for a Snowflake + dbt medallion pipeline over museum artwork datasets.

The repository owns the artwork pipeline itself: Snowflake DDL, extraction code, dbt models, and small operator scripts. Generic Snowflake orchestration code lives in the sibling `snowflake-toolkit` repository, and the standalone dbt diagnostics CLI lives in the sibling `dbt-diagnostics` repository.

## Pipeline overview

```text
Museum source data
  ├─ Met OpenAccess CSV + object API
  └─ Art Institute of Chicago public data dump
        |
        v
Python extraction layer: extraction/
        |
        v
Snowflake Bronze: ARTWORK_DB.BRONZE
        |
        v
dbt staging layer: ARTWORK_DB.SILVER
        |
        v
dbt mart layer: ARTWORK_DB.GOLD
```

The current production-oriented path is:

1. Apply Snowflake infrastructure with `make infra` or `make iac`.
2. Create service-account key-pair connections with `make loader` and `make transformer`.
3. Load Bronze data with the extractors in `extraction/`.
4. Build Silver and Gold with the dbt project in `artwork_pipeline/`.

## Repository layout

```text
.
├── Makefile                       # Main operator entry point
├── .env.example                   # Template for local Snowflake, dbt, and GitHub settings
├── requirements.txt               # Root Python dependencies for extraction + dbt
├── profiles.yml.example           # Example dbt profile material
├── infrastructure/                # Project Snowflake DDL: roles, warehouses, schemas, stages, Bronze tables, tasks, alerts
├── git-setup/                     # Optional in-Snowflake Git mirror and MCP setup scripts
├── extraction/                    # Python Bronze loaders
│   ├── met/                       # Met OpenAccess snapshot, control seeding, API enrichment, and legacy SQLite path
│   └── aic/                       # Art Institute of Chicago snapshot loader
├── artwork_pipeline/              # dbt project for Silver and Gold models
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── packages.yml
│   ├── macros/
│   ├── models/
│   │   ├── staging/met/
│   │   ├── staging/aic/
│   │   └── marts/
│   └── tests/
├── scripts/                       # Local project orchestration glue and operator SQL checks
├── operations/                    # Manual/operator SQL utilities
└── analysis/                      # Ad hoc project analysis SQL
```

The active maintainer surface is concentrated in `infrastructure/`, `extraction/`, and `artwork_pipeline/`. The `scripts/` directory is intentionally small: it contains the local dbt orchestrator, the IaC manifest consumed by `snowflake-toolkit`, secret-output declarations, and project-specific Snowflake check queries.

## Prerequisites

Install or prepare the following before running the pipeline:

- Python 3.10 or newer; Python 3.11 is recommended.
- Access to a Snowflake account where you can bootstrap account-level objects.
- Snowflake CLI configured through the sibling `snowflake-toolkit` repository.
- A local sibling clone of `snowflake-toolkit`, by default at `../snowflake-toolkit`.
- For local dbt and extraction runs, a root `.env` created from `.env.example`.
- Optional: GitHub PAT and OAuth credentials in `.env` if you want the in-Snowflake Git mirror / MCP setup from `git-setup/`.

A typical local directory layout is:

```text
~/dev/
├── artwork-db/
├── snowflake-toolkit/
└── dbt-diagnostics/        # optional, only needed for diagnostic CLI work
```

## Initial setup

### 1. Create a Python environment

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

The root `requirements.txt` covers the main extraction and dbt runtime dependencies. The extractor-specific requirement files under `extraction/met/` and `extraction/aic/` are also available when you want to install only one loader in isolation.

### 2. Create `.env`

```bash
cp .env.example .env
```

Edit `.env` and set at least the Snowflake account, loader service account, transformer service account, warehouse, database, and private-key paths.

The important variables are:

```text
SNOWFLAKE_ACCOUNT
SNOWFLAKE_USER
SNOWFLAKE_PRIVATE_KEY_FILE
SNOWFLAKE_ROLE
SNOWFLAKE_WAREHOUSE
SNOWFLAKE_DATABASE
DBT_SNOWFLAKE_USER
DBT_SNOWFLAKE_PRIVATE_KEY_PATH
DBT_SNOWFLAKE_ROLE
TOOLKIT_DIR
```

The loader variables are used by `extraction/`. The `DBT_*` variables are used by `artwork_pipeline/profiles.yml` through dbt `env_var()` calls.

### 3. Ensure the toolkit sibling repo exists

By default, the Makefile expects:

```text
../snowflake-toolkit
```

Override that path when needed:

```bash
make infra TOOLKIT_DIR=/path/to/snowflake-toolkit
```

The toolkit provides the Snowflake CLI setup scripts and the generic SQL apply/rollback orchestration. This repo provides the project-specific DDL and manifest.

### 4. Configure an admin Snowflake CLI connection

Use the toolkit to create or refresh the admin Snowflake CLI connection for the target account. The profile label becomes the `CONN` value used by Makefile targets.

Example:

```bash
bash ../snowflake-toolkit/snowflake_cli/setup.sh --profile mk07348 --phase all
```

Then pass that profile to Makefile targets:

```bash
make infra CONN=mk07348
```

If `CONN` is omitted, the Makefile defaults to `admin`.

## Infrastructure layer

The `infrastructure/` directory contains project-specific Snowflake DDL. It creates and maintains:

- Account parameters.
- Roles: `ARTWORK_ADMIN`, `ARTWORK_LOADER`, and `ARTWORK_TRANSFORMER`.
- Warehouse: `ARTWORK_WH`.
- Database and schemas: `ARTWORK_DB.BRONZE`, `ARTWORK_DB.SILVER`, `ARTWORK_DB.GOLD`, and `ARTWORK_DB.DBT_TEST__AUDIT`.
- File formats and internal stages for Bronze loads.
- Grants for loader and transformer service roles.
- Bronze raw tables for Met, AIC, CMA, and Smithsonian source shapes.
- Met enrichment control tables and worklist views.
- Service users for loader and transformer key-pair auth.
- Tasks and alerts for pipeline operations.

Apply only the core infrastructure:

```bash
make infra CONN=mk07348
```

Apply core infrastructure plus the optional Git mirror setup:

```bash
make iac CONN=mk07348
```

The apply order is controlled by `scripts/manifest.txt`. Do not rely on filename sorting for IaC order.

### Optional Git setup

The `git-setup/` directory creates optional Snowflake objects for an in-Snowflake Git mirror and MCP integration. These scripts run after core infrastructure when you call:

```bash
make iac CONN=mk07348
```

or directly:

```bash
make bootstrap CONN=mk07348
```

For this path, fill the GitHub variables in `.env`:

```text
GITHUB_PAT
GITHUB_OAUTH_CLIENT_ID
GITHUB_OAUTH_CLIENT_SECRET
```

The Makefile reads those values and injects only non-empty secrets into the toolkit apply path.

### Service-account keys

After core infrastructure exists, create key-pair connections for the service users:

```bash
make loader CONN=mk07348
make transformer CONN=mk07348
```

`make loader` prepares the `ARTWORK_LOADER_SVC` credential used by Python extractors. `make transformer` prepares the `ARTWORK_TRANSFORMER_SVC` credential used by local dbt Core runs.

Update `.env` with the generated private-key paths, for example:

```text
SNOWFLAKE_PRIVATE_KEY_FILE=~/.snowflake/keys/mk07348_loader_rsa_key.p8
DBT_SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/mk07348_transformer_rsa_key.p8
```

### Rollback and teardown

Rollback one forward script through its paired drop script:

```bash
make rollback CONN=mk07348 FILE=infrastructure/create_stages.sql
```

Tear down all IaC-managed objects in reverse manifest order:

```bash
make down CONN=mk07348
```

Tear down from a manifest point:

```bash
make down-from CONN=mk07348 FROM=create_stages.sql
```

Use teardown targets carefully. They are intended for controlled development-account cleanup, not casual production operations.

## Extraction layer

The `extraction/` package lands raw museum source data into Snowflake Bronze.

### Met OpenAccess loader

The current Met path is Snowflake-authoritative:

1. `snapshot` loads the Met OpenAccess CSV into `BRONZE.MET_CSV_SNAPSHOT`.
2. `seed-control` inserts bounded work rows into `BRONZE.MET_ENRICHMENT_CONTROL`.
3. `enrich-met` drains `BRONZE.MET_WORKLIST`, fetches image metadata from the Met API, assembles Bronze rows, and writes outcomes back to Snowflake.

Run the current Met path through Make:

```bash
make extract-met
```

Or run the steps directly:

```bash
python -m extraction.met.run snapshot -v
python -m extraction.met.run seed-control -v
python -m extraction.met.run enrich-met -v
```

Useful bounded runs:

```bash
python -m extraction.met.run snapshot --limit 1000 -v
python -m extraction.met.run seed-control --department "European Paintings" --limit 500 -v
python -m extraction.met.run enrich-met --limit 500 -v
```

`make extract` is currently an alias for `make extract-met`.

The legacy Met SQLite path still exists in the CLI for reference, but it is not the preferred architecture and is not wired into the Makefile pipeline.

### AIC loader

The AIC loader downloads the Art Institute of Chicago public data dump, extracts Tier 1 entities, writes gzipped NDJSON, and merges artworks and agents into Snowflake Bronze.

Run a full snapshot:

```bash
python -m extraction.aic.run snapshot -v
```

Useful options:

```bash
python -m extraction.aic.run snapshot --limit 1000 -v
python -m extraction.aic.run snapshot --entities artworks -v
python -m extraction.aic.run status -v
```

The AIC `delta` command is present as a placeholder but is not implemented yet.

### Local extraction artifacts

Extraction can create large local files such as downloaded CSVs, tarballs, extracted JSON, NDJSON, checkpoints, and scratch databases. These are intentionally ignored by git. Keep source data out of commits unless you are deliberately adding a small fixture.

## dbt layer

The dbt project lives in `artwork_pipeline/` and transforms Bronze data into Silver staging views and Gold mart tables.

### dbt architecture

```text
ARTWORK_DB.BRONZE
  ├── RAW_MET_OBJECTS
  ├── MET_CSV_SNAPSHOT
  ├── MET_ENRICHMENT_CONTROL
  ├── RAW_AIC_ARTWORKS
  └── RAW_AIC_AGENTS
        |
        v
ARTWORK_DB.SILVER
  ├── stg_met__artworks
  ├── stg_met__artists
  ├── stg_met__images
  ├── stg_met__enrichment_status
  ├── stg_aic__artworks
  ├── stg_aic__artists
  └── stg_aic__images
        |
        v
ARTWORK_DB.GOLD
  ├── dim_artworks
  ├── dim_artists
  ├── fct_artwork_images
  └── openaccess_catalog
```

Staging models are views. Mart models are tables. dbt does not own schema creation; schemas and grants are managed by the IaC layer.

### Initialize dbt

```bash
make dbt-init
```

This sources `.env`, installs dbt packages, and runs `dbt debug` with `artwork_pipeline/profiles.yml`.

Direct equivalent:

```bash
bash scripts/dbt_orchestrate.sh --phase init
```

### Build and test

Build models and run tests:

```bash
make dbt-build
```

Run tests only:

```bash
make dbt-test
```

Full-refresh Gold tables:

```bash
make dbt-full-refresh
```

Generate and serve local dbt docs:

```bash
make dbt-docs
```

Run dbt directly when your environment is already exported:

```bash
cd artwork_pipeline
dbt deps
dbt build --profiles-dir .
dbt test --profiles-dir .
```

### Targeted dbt runs

From `artwork_pipeline/`:

```bash
# Build only staging views
dbt run --select staging --profiles-dir .

# Build only marts
dbt run --select marts --profiles-dir .

# Build one mart and its upstream dependencies
dbt run --select +dim_artworks --profiles-dir .

# Run AIC or Met subsets
dbt run --select tag:aic --profiles-dir .
dbt run --select tag:met --profiles-dir .
```

### dbt packages

`artwork_pipeline/packages.yml` uses:

- `dbt_utils` for common SQL utilities and surrogate keys.
- `codegen` for development-time source/model generation.
- `dbt_expectations` for richer data quality tests.
- `audit_helper` for refactoring comparisons.
- `dbt_project_evaluator` for DAG hygiene and governance checks.

After package changes, run:

```bash
make dbt-deps
```

### dbt teardown

To drop and recreate dbt-managed Silver and Gold schemas:

```bash
make dbt-teardown CONN=mk07348
```

This is destructive. It prompts for confirmation, drops `SILVER` and `GOLD`, recreates them, and then expects you to restore grants and rebuild:

```bash
make infra CONN=mk07348
make dbt-build
```

## Common workflows

### Fresh development account

```bash
# 1. Create/update core infrastructure.
make infra CONN=mk07348

# 2. Create loader and transformer key-pair service connections.
make loader CONN=mk07348
make transformer CONN=mk07348

# 3. Update .env with the generated key paths, then verify dbt.
make dbt-init

# 4. Load Bronze data.
make extract-met
python -m extraction.aic.run snapshot -v

# 5. Build Silver and Gold.
make dbt-build
```

### Regular local pipeline run

```bash
source .venv/bin/activate
make extract-met
python -m extraction.aic.run snapshot -v
make dbt-build
```

### Met-only smoke test

```bash
python -m extraction.met.run snapshot --limit 1000 -v
python -m extraction.met.run seed-control --limit 100 -v
python -m extraction.met.run enrich-met --limit 100 -v
make dbt-build
```

### AIC-only smoke test

```bash
python -m extraction.aic.run snapshot --limit 1000 -v
make dbt-build
```

### Infrastructure-only validation

```bash
make -n infra CONN=mk07348
make -n iac CONN=mk07348
```

The `-n` flag prints what Make would run without executing it.

## Operator checks

Project-specific SQL checks live under `scripts/sql/`. They are useful after extraction or dbt builds:

```text
scripts/sql/check_aic_agents.sql
scripts/sql/check_aic_bronze.sql
scripts/sql/check_cross_source_overlap.sql
scripts/sql/show_pipeline_status.sql
scripts/sql/show_run_control.sql
```

Run them with your preferred Snowflake CLI connection, for example:

```bash
snow sql -f scripts/sql/show_pipeline_status.sql -c mk07348
snow sql -f scripts/sql/check_cross_source_overlap.sql -c mk07348
```

## Important conventions

- Snowflake object creation is owned by `infrastructure/`, not dbt.
- IaC apply order is owned by `scripts/manifest.txt`.
- Generic orchestration is owned by `snowflake-toolkit`.
- Local dbt lifecycle orchestration is owned by `scripts/dbt_orchestrate.sh`.
- `.env`, keys, local data, dbt build output, logs, and scratch files are not committed.
- Loader and transformer credentials are key-pair service users, not human passwords.
- `make extract` currently means Met extraction only; AIC is run directly with `python -m extraction.aic.run snapshot`.

## Troubleshooting

### `snowflake-toolkit not found`

The Makefile checks for the toolkit sibling repo before running IaC targets. Clone it next to this repo or override `TOOLKIT_DIR`:

```bash
make infra TOOLKIT_DIR=/path/to/snowflake-toolkit CONN=mk07348
```

### `.env not found`

Create it from the template:

```bash
cp .env.example .env
```

Then fill in account, role, warehouse, database, and key-pair paths.

### `Private key not found`

Run the key setup targets after infrastructure exists:

```bash
make loader CONN=mk07348
make transformer CONN=mk07348
```

Then update `.env` with the generated key paths.

### dbt cannot find `env_var(...)`

Use the Makefile dbt targets, which source `.env` automatically:

```bash
make dbt-init
make dbt-build
```

If running dbt manually, export the variables first:

```bash
set -a
source .env
set +a
cd artwork_pipeline
dbt build --profiles-dir .
```

### Bronze tables do not exist

Run the core infrastructure apply:

```bash
make infra CONN=mk07348
```

Then rerun the extractor.

### Gold or Silver objects are missing after teardown

Restore grants and rebuild dbt:

```bash
make infra CONN=mk07348
make dbt-build
```

## Maintainer notes

This repo should stay focused on the artwork pipeline. Keep generic Snowflake orchestration in `snowflake-toolkit` and generic dbt diagnostic CLI work in `dbt-diagnostics`. New project-specific source loaders, Snowflake DDL, dbt models, and operator checks belong here.
