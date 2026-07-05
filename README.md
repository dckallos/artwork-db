# artwork-db

`artwork-db` is the project-specific Snowflake + dbt medallion pipeline for museum artwork datasets. It owns the Snowflake DDL, extraction code, dbt project, Dagster/orchestration integration, repository CI, and GitHub governance tooling for this project.

Generic Snowflake orchestration utilities live in the sibling `snowflake-toolkit` repository. Generic dbt diagnostic CLI work lives in the sibling `dbt-diagnostics` repository.

## Current architecture

```text
Museum source data
  ├─ The Metropolitan Museum of Art OpenAccess CSV + object API
  └─ Art Institute of Chicago public data dump
        |
        v
Python extraction layer: extraction/
        |
        v
Snowflake Bronze: ARTWORK_DB.BRONZE
        |
        v
dbt staging layer:
  - dev      -> ARTWORK_DB.<developer_prefix>_SILVER / _GOLD
  - staging  -> ARTWORK_DB.STAGING_SILVER / STAGING_GOLD
  - prod     -> ARTWORK_DB.SILVER / GOLD
        |
        v
dbt mart layer: Gold marts and catalog outputs
```

The current production-oriented path is:

1. Apply Snowflake infrastructure with `make infra` or `make iac`.
2. Create key-pair service-account credentials with `make loader` and `make transformer`.
3. Load Bronze data with the extractors under `extraction/`.
4. Build Silver and Gold with the dbt project under `artwork_pipeline/`.
5. Use GitHub Actions and `tools/github/ghclient` to keep CI and repository governance explicit.

## Repository layout

```text
.
├── .env.example                         # Local environment template; never commit .env
├── .github/workflows/ci.yml             # Main PR/push CI workflow and ci-required aggregate
├── Makefile                             # Operator entry point for infra, extraction, dbt
├── README.md                            # This file
├── requirements.txt                     # Root Python deps for extraction + dbt
├── profiles.yml.example                 # Example dbt profile material
├── analysis/                            # Ad hoc SQL/project analysis
├── artwork_pipeline/                    # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml                     # dev/staging/prod targets, env-var driven
│   ├── macros/
│   ├── models/
│   └── tests/
├── config/
│   └── github-client-config.yml         # ghclient repo/branch/secret/CI config
├── docs/                                # Planning and reference docs
├── extraction/
│   ├── met/                             # Met snapshot, control seeding, enrichment
│   └── aic/                             # AIC snapshot loader
├── git-setup/                           # Optional Snowflake Git mirror / MCP setup
├── infrastructure/                      # Project Snowflake DDL and grants
├── operations/                          # Manual/operator SQL utilities
├── orchestration/                       # Dagster code location and tests
├── scripts/
│   ├── check_no_attribution.sh          # Advisory AI-authorship marker guard
│   ├── ci/ci_local.sh                   # Local equivalent for dbt CI checks
│   ├── dbt_orchestrate.sh               # Local dbt lifecycle wrapper
│   ├── manifest.txt                     # IaC apply/rollback order
│   └── sql/                             # Operator checks
└── tools/github/                        # ghclient package and tests
    ├── ghclient/
    ├── policies/
    ├── tests/
    └── wrappers/
```

## Prerequisites

Install or prepare the following before running the pipeline:

- Python 3.11 recommended.
- A Snowflake account where you can create account-level project objects.
- A sibling clone of `snowflake-toolkit`, by default at `../snowflake-toolkit`.
- Snowflake CLI configured with an admin connection for your target account.
- A local `.env` copied from `.env.example`.
- GitHub CLI (`gh`) authenticated for `dckallos/artwork-db` if you use `ghclient` or manage Actions secrets.
- Repository admin access for GitHub branch protection, Environments, secrets, and variables.
- Optional: GitHub PAT/OAuth values in `.env` if using the Snowflake Git mirror / MCP path in `git-setup/`.

Typical local layout:

```text
~/dev/
├── artwork-db/
├── snowflake-toolkit/
└── dbt-diagnostics/        # optional
```

## Initial local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` before running local extraction or dbt. The important local variables are:

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

## Snowflake infrastructure

The `infrastructure/` directory creates and maintains the project’s Snowflake objects:

- Roles: `ARTWORK_ADMIN`, `ARTWORK_LOADER`, `ARTWORK_TRANSFORMER`.
- Service users: `ARTWORK_LOADER_SVC`, `ARTWORK_TRANSFORMER_SVC`.
- Warehouses: local/dev warehouse plus staging/prod warehouses as provisioned.
- Database/schemas including Bronze, Silver, Gold, staging schemas, and audit/test schemas.
- File formats, stages, Bronze tables, control/worklist tables, tasks, alerts, and grants.

Apply core infrastructure:

```bash
make infra CONN=mk07348
```

Apply core infrastructure plus optional Git mirror / MCP setup:

```bash
make iac CONN=mk07348
```

The apply order is controlled by `scripts/manifest.txt`; do not rely on filename ordering.

### Service-account key pairs

After core infrastructure exists, create local key-pair connections for the service accounts:

```bash
make loader CONN=mk07348
make transformer CONN=mk07348
```

These targets delegate to `snowflake-toolkit` and create namespaced key files such as:

```text
~/.snowflake/keys/mk07348_loader_rsa_key.p8
~/.snowflake/keys/mk07348_transformer_rsa_key.p8
```

Update `.env` with those paths:

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

The `extraction/` package lands raw museum data into Snowflake Bronze.

### Met loader

The current Met path is Snowflake-authoritative:

1. `snapshot` loads the Met OpenAccess CSV into `BRONZE.MET_CSV_SNAPSHOT`.
2. `seed-control` inserts bounded work rows into `BRONZE.MET_ENRICHMENT_CONTROL`.
3. `enrich-met` drains `BRONZE.MET_WORKLIST`, fetches image metadata from the Met API, and writes outcomes back to Snowflake.

Run through Make:

```bash
make extract-met
```

Run steps directly:

```bash
python -m extraction.met.run snapshot -v
python -m extraction.met.run seed-control -v
python -m extraction.met.run enrich-met -v
```

Bounded smoke runs:

```bash
python -m extraction.met.run snapshot --limit 1000 -v
python -m extraction.met.run seed-control --department "European Paintings" --limit 500 -v
python -m extraction.met.run enrich-met --limit 500 -v
```

`make extract` is currently an alias for `make extract-met`.

### AIC loader

The AIC loader downloads the Art Institute of Chicago public data dump, extracts Tier 1 entities, writes gzipped NDJSON, and merges artworks and agents into Snowflake Bronze.

```bash
python -m extraction.aic.run snapshot -v
python -m extraction.aic.run snapshot --limit 1000 -v
python -m extraction.aic.run snapshot --entities artworks -v
python -m extraction.aic.run status -v
```

The AIC `delta` command is present as a placeholder but is not implemented yet.

### Local extraction artifacts

Extraction can create large local files such as downloaded CSVs, tarballs, extracted JSON, NDJSON, checkpoints, and scratch databases. These are ignored by git. Keep source data out of commits unless you are deliberately adding a small fixture.

## dbt layer

The dbt project lives in `artwork_pipeline/` and transforms Bronze data into staging views and mart tables.

### dbt profiles and targets

The active profile name is `dbt_daniel`, matching `artwork_pipeline/dbt_project.yml`.

`artwork_pipeline/profiles.yml` defines three targets:

- `dev`: local development, key-pair via `DBT_SNOWFLAKE_PRIVATE_KEY_PATH`.
- `staging`: CI target, key-pair via inline `DBT_SNOWFLAKE_PRIVATE_KEY` contents.
- `prod`: release/prod target, key-pair via inline `DBT_SNOWFLAKE_PRIVATE_KEY` contents.

All targets are environment-variable driven and contain no secrets.

The default local target is `dev`. CI should set `DBT_TARGET` deliberately once staging/prod workflows are fully wired.

### Initialize dbt

```bash
make dbt-init
```

Direct equivalent:

```bash
bash scripts/dbt_orchestrate.sh --phase init
```

### Build and test

```bash
make dbt-build
make dbt-test
make dbt-full-refresh
make dbt-docs
```

Run dbt directly when your environment is already exported:

```bash
set -a
source .env
set +a

cd artwork_pipeline
dbt deps
dbt build --profiles-dir .
dbt test --profiles-dir .
```

### CI-local dbt checks

The CI-local script is checks-only and intentionally avoids a full warehouse-writing `dbt build`:

```bash
bash scripts/ci/ci_local.sh
```

It runs:

1. `dbt deps`
2. `dbt parse`
3. `sqlfluff lint`
4. `dbt compile`
5. dbt unit tests with `--empty`

## Orchestration layer

The Dagster/orchestration package lives in `orchestration/`.

Local development typically uses an editable install:

```bash
cd orchestration
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The current CI workflow folds orchestration tests into `.github/workflows/ci.yml` under the `orchestration-tests` job instead of using a separate `orchestration-tests.yml` workflow. This keeps the single aggregate `ci-required` check authoritative.

## GitHub Actions CI

The primary workflow is `.github/workflows/ci.yml`.

Important jobs:

- `changes`: detects whether dbt/orchestration paths changed.
- `actionlint`: validates workflow YAML.
- `shellcheck`: validates shell scripts.
- `github-client`: installs and tests `tools/github`.
- `py-quality`: byte-compiles `ghclient` and checks docstring style.
- `authorship-guard`: advisory scan for automated AI-authorship markers.
- `dbt-checks`: credentialed dbt parse/lint/compile/unit-test path.
- `orchestration-tests`: offline Dagster/orchestration test path.
- `ci-required`: the single aggregate gate that branch protection should require.

`ci-required` is designed to always emit on pull requests and to depend on every gating job. Branch protection should require only `ci-required`, not path-specific job names.

### Required GitHub Actions prerequisites

The non-credentialed jobs do not need GitHub secrets.

The `dbt-checks` job needs Snowflake CI credentials. In the current workflow state, `dbt-checks` reads repository-level Actions secrets and writes `DBT_SNOWFLAKE_PRIVATE_KEY` to a temporary key file before running `scripts/ci/ci_local.sh`.

Minimum repository-level secrets for the current workflow:

```text
SNOWFLAKE_ACCOUNT
DBT_SNOWFLAKE_USER
DBT_SNOWFLAKE_PRIVATE_KEY
DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE   # only if the key is encrypted; otherwise leave unset
```

Set them with GitHub CLI:

```bash
# Authenticate once.
gh auth login
gh auth status

# Set non-file values.
gh secret set SNOWFLAKE_ACCOUNT -R dckallos/artwork-db --body "$SNOWFLAKE_ACCOUNT"
gh secret set DBT_SNOWFLAKE_USER -R dckallos/artwork-db --body "ARTWORK_TRANSFORMER_SVC"

# Set the full PEM contents by stdin; do not put the private key on the command line.
gh secret set DBT_SNOWFLAKE_PRIVATE_KEY -R dckallos/artwork-db < ~/.snowflake/keys/mk07348_transformer_rsa_key.p8

# Only if your private key is encrypted.
printf '%s' "$DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE" \
  | gh secret set DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE -R dckallos/artwork-db
```

If the workflow is updated to use GitHub Environments, the job must declare the environment before Environment secrets/variables are available to it.

## GitHub governance client: `ghclient`

`tools/github/` contains a standalone Python package named `artwork-github-client` with CLI entrypoint `ghclient`.

It manages or previews:

- Classic branch protection.
- Branch-protection export and rollback snapshots.
- Ruleset-aware audit.
- Snowflake credential publishing to GitHub Environment secrets/variables.
- Required-check reconciliation to the single `ci-required` aggregate.

Install it locally:

```bash
python -m venv .venv-ghclient
source .venv-ghclient/bin/activate
pip install --upgrade pip
pip install -e "tools/github[dev]"
```

Preflight:

```bash
ghclient preflight
```

Dry-run branch protection:

```bash
ghclient branch-protection apply --branch main
```

Apply branch protection only after reviewing the dry-run:

```bash
ghclient branch-protection apply --branch main --apply
```

Dry-run CI required-check reconcile:

```bash
ghclient ci reconcile --branch main
```

Apply CI required-check reconcile only after `ci-required` exists and the workflow is green:

```bash
ghclient ci reconcile --branch main --apply
```

### Environment-scoped Snowflake publish path

`config/github-client-config.yml` defines `snowflake_secrets` publish sets named `staging` and `prod`. These publish to GitHub Environments, not repository-level secrets.

Create the GitHub Environments before using `ghclient secrets publish`:

```bash
gh api --method PUT repos/dckallos/artwork-db/environments/staging
gh api --method PUT repos/dckallos/artwork-db/environments/prod
```

Prepare local Snowflake connection profiles that match `config/github-client-config.yml`:

```bash
mkdir -p ~/.snowflake/keys
chmod 700 ~/.snowflake/keys

# Put or copy CI private keys at the paths expected by the current config.
install -m 600 /path/to/staging_ci.p8 ~/.snowflake/keys/staging_ci.p8
install -m 600 /path/to/prod_ci.p8 ~/.snowflake/keys/prod_ci.p8
```

Add profile stanzas to `~/.snowflake/connections.toml`:

```toml
[artwork_ci_staging]
account = "ORGNAME-ACCOUNTNAME"
user = "ARTWORK_TRANSFORMER_SVC"
role = "ARTWORK_TRANSFORMER"
warehouse = "ARTWORK_WH_STAGING"
authenticator = "SNOWFLAKE_JWT"
private_key_path = "~/.snowflake/keys/staging_ci.p8"

[artwork_ci_prod]
account = "ORGNAME-ACCOUNTNAME"
user = "ARTWORK_TRANSFORMER_SVC"
role = "ARTWORK_TRANSFORMER"
warehouse = "ARTWORK_WH_PROD"
authenticator = "SNOWFLAKE_JWT"
private_key_path = "~/.snowflake/keys/prod_ci.p8"
```

Dry-run publish:

```bash
ghclient secrets publish --profile-set staging
ghclient secrets publish --profile-set prod
```

Apply after reviewing the plan:

```bash
ghclient secrets publish --profile-set staging --apply
ghclient secrets publish --profile-set prod --apply
```

Use `--force` when intentionally updating existing items:

```bash
ghclient secrets publish --profile-set staging --force --apply
```

### Important current-state caveat

The current `ghclient secrets publish` path targets GitHub Environments. The current `dbt-checks` job in `.github/workflows/ci.yml` uses repository-level `secrets.*` and does not yet declare an Environment. Until the workflow is updated to declare an Environment, Environment-scoped values published by `ghclient secrets publish` will not satisfy the current `dbt-checks` job. Use the repository-level `gh secret set ... -R dckallos/artwork-db` commands above for the current workflow, or update the workflow to use:

```yaml
environment:
  name: staging
  deployment: false
```

and then consume Environment variables/secrets explicitly.

## Common workflows

### Fresh development account

```bash
# 1. Create or update core infrastructure.
make infra CONN=mk07348

# 2. Create loader and transformer key-pair service connections.
make loader CONN=mk07348
make transformer CONN=mk07348

# 3. Update .env with generated key paths, then verify dbt.
make dbt-init

# 4. Load Bronze data.
make extract-met
python -m extraction.aic.run snapshot -v

# 5. Build dbt models and tests.
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

### GitHub client test suite

```bash
pip install -e "tools/github[dev]"
pytest tools/github/tests
```

### Repository shell/doc quality checks

```bash
python -m py_compile tools/github/ghclient/*.py
python3 scripts/normalize_docstrings.py --check
bash scripts/check_no_attribution.sh --files-only
```

## Operator SQL checks

Project-specific SQL checks live under `scripts/sql/`.

```bash
snow sql -f scripts/sql/show_pipeline_status.sql -c mk07348
snow sql -f scripts/sql/check_cross_source_overlap.sql -c mk07348
snow sql -f scripts/sql/check_aic_bronze.sql -c mk07348
snow sql -f scripts/sql/check_aic_agents.sql -c mk07348
```

## Important conventions

- Snowflake object creation is owned by `infrastructure/`, not dbt.
- IaC apply order is owned by `scripts/manifest.txt`.
- Generic Snowflake orchestration is owned by `snowflake-toolkit`.
- Local dbt lifecycle orchestration is owned by `scripts/dbt_orchestrate.sh`.
- Repository GitHub governance is owned by `tools/github/ghclient`.
- `.env`, private keys, source data, dbt build output, logs, and scratch files must not be committed.
- Loader and transformer credentials are key-pair service users, not human passwords.
- `make extract` currently means Met extraction only.
- AIC is run directly with `python -m extraction.aic.run snapshot`.
- CI should require the `ci-required` aggregate, not individual path-gated jobs.

## Troubleshooting

### `snowflake-toolkit not found`

Clone it next to this repo or override `TOOLKIT_DIR`:

```bash
make infra TOOLKIT_DIR=/path/to/snowflake-toolkit CONN=mk07348
```

### `.env not found`

```bash
cp .env.example .env
```

Then fill in account, roles, warehouse, database, and key-pair paths.

### `Private key not found`

Run the service-account setup targets after infrastructure exists:

```bash
make loader CONN=mk07348
make transformer CONN=mk07348
```

Then update `.env` with the generated key paths.

### CI secret expressions are empty

If a GitHub Actions secret has not been created, `${{ secrets.NAME }}` evaluates to an empty string. Set the repository-level secrets for the current workflow or update the workflow to consume Environment secrets/variables.

### dbt cannot find `env_var(...)`

Use the Makefile dbt targets, which source `.env` automatically:

```bash
make dbt-init
make dbt-build
```

If running dbt manually:

```bash
set -a
source .env
set +a
cd artwork_pipeline
dbt build --profiles-dir .
```

### Bronze tables do not exist

Run core infrastructure, then rerun the extractor:

```bash
make infra CONN=mk07348
make extract-met
```

### Silver or Gold objects are missing after teardown

Restore grants and rebuild dbt:

```bash
make infra CONN=mk07348
make dbt-build
```

### `ghclient secrets publish` says the environment does not exist

Create the Environment first:

```bash
gh api --method PUT repos/dckallos/artwork-db/environments/staging
gh api --method PUT repos/dckallos/artwork-db/environments/prod
```

Then rerun the dry-run:

```bash
ghclient secrets publish --profile-set staging
```

### `ci-required` fails

`ci-required` is an aggregate. Inspect the upstream jobs first:

- `shellcheck`
- `github-client`
- `py-quality`
- `dbt-checks`
- `orchestration-tests`

Fix the failing upstream job; do not bypass the aggregate by requiring a different status check.

## Maintainer notes

Keep this repo focused on the artwork pipeline. New project-specific source loaders, Snowflake DDL, dbt models, orchestration integration, CI checks, and operator SQL belong here. Generic Snowflake orchestration belongs in `snowflake-toolkit`; generic dbt diagnostics work belongs in `dbt-diagnostics`.
