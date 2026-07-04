# SETUP_COMMANDS.md

Comprehensive setup command runbook for `dckallos/artwork-db` on macOS, using the companion `dckallos/snowflake-toolkit` repo and the helper scripts added during the `feat/optimize-dagster-options` work.

This file is intentionally command-heavy. Use it as the single place to find the setup sequence for:

- Snowflake CLI profile creation and repair.
- Snowflake DDL / IaC setup.
- Loader and dbt transformer service-user key setup.
- Optional Snowflake Git Repository / MCP git-setup.
- dbt local validation.
- CI Snowflake profiles used by `ghclient`.
- GitHub Environment Secrets / Variables.
- Optional branch-protection setup after CI is green.

---

## 0. Assumptions and Safety Rules

### Assumed local paths

```text
artwork-db repo:        ~/dev/artwork-db
snowflake-toolkit repo: ~/dev/snowflake-toolkit
artwork-db branch:      feat/optimize-dagster-options
Snowflake account:      DSHXYWJ-KW94245
Snowflake CLI profile:  kw94245
Admin Snowflake user:   PORCHORCH
```

### Critical safety rules

1. **Use lowercase `kw94245`; do not use uppercase `KW94245`.**
   The uppercase profile previously pointed at the old account `KUNHTEL-GL13131`, which caused JWT/password failures.

2. **Do not run Snowflake admin/bootstrap commands from a shell polluted with project runtime `SNOWFLAKE_*` variables.**
   Use `source ../snowflake-toolkit/unload_profile.sh` or explicit helper scripts before bootstrap.

3. **Do not store live API tokens in `~/.zshrc`.**
   Rotate any GitHub/OpenAI/Anthropic tokens that were pasted or committed, remove them from shell startup, and start a fresh shell.

4. **Do not apply branch protection until CI is green.**
   Branch protection should require only `ci-required`, but applying it too early can block merges.

5. **Review `git diff` before running anything that mutates Snowflake or GitHub.**

---

## 1. Full Setup Order at a Glance

| Order | Area | Command |
| ---: | --- | --- |
| 1 | Repo / helper sanity | `bash scripts/setup/fix_helper_permissions.sh` or `chmod +x ...` |
| 2 | Clean GitHub token env | `unset GH_TOKEN GITHUB_TOKEN GITHUB_PAT DCKALLOS_GITHUB_TOKEN TMP_GH_TOKEN` |
| 3 | Generate `.env` | `bash scripts/setup/write_local_env.sh --target .env --apply --force` |
| 4 | Local doctor | `bash scripts/setup/doctor_local_setup.sh` |
| 5 | Snowflake bootstrap + DDL + service keys | `bash scripts/setup/bootstrap_snowflake_account.sh --replace-existing --apply` |
| 6 | Optional Snowflake git-setup | `bash scripts/setup/run_git_setup.sh --apply` |
| 7 | Create CI Snowflake profiles | `python3 scripts/setup/create_ci_snowflake_profiles.py --apply --test` |
| 8 | Install `ghclient` | `bash scripts/setup/install_ghclient.sh` |
| 9 | GitHub auth / preflight | `gh auth login -h github.com -s repo && ghclient preflight` |
| 10 | GitHub Environments + CI secrets/vars | `bash scripts/setup/github_governance.sh --apply --force-secrets` |
| 11 | Full readiness verification | `bash scripts/setup/verify_operational_readiness.sh` |
| 12 | Branch protection later only | `bash scripts/setup/github_governance.sh --apply-branch-protection` |

---

## 2. Setup Script Index

| Script | Dry-run by default? | Mutates? | Purpose |
| --- | ---: | --- | --- |
| `scripts/setup/write_local_env.sh` | Yes | `.env` only with `--apply` | Generate `.env` from `.env.example`, backing up old `.env`. |
| `scripts/setup/doctor_local_setup.sh` | Read-only | No | Check branch, tools, `.env`, Snowflake profile target, token env, and stale shell startup tokens. |
| `scripts/setup/bootstrap_snowflake_account.sh` | Yes | Snowflake + local files with `--apply` | Run toolkit prereq/admin, `make infra`, promote, loader, transformer. |
| `scripts/setup/run_git_setup.sh` | Yes | Snowflake with `--apply` | Run `make bootstrap` for `git-setup/` SQL. |
| `scripts/setup/create_ci_snowflake_profiles.py` | Yes | `~/.snowflake` with `--apply` | Create `artwork_ci_staging` and `artwork_ci_prod` profiles for `ghclient`. |
| `scripts/setup/install_ghclient.sh` | No | Local venv | Install `tools/github[dev]` safely under zsh. |
| `scripts/setup/github_governance.sh` | Yes | GitHub with `--apply` | Create GitHub Environments and publish CI secrets/variables. Branch protection is separate. |
| `scripts/setup/verify_operational_readiness.sh` | Read-only | No | Verify Snowflake, dbt, ghclient, GitHub Environments, secrets, and variables. |
| `scripts/setup/fix_helper_permissions.sh` | No | File modes only | Ensure helper/wrapper scripts are executable. |
| `scripts/setup/diagnose_branch_protection_access.sh` | Read-only | No | Diagnose GitHub branch-protection API permissions/feature availability. |

If one of the scripts above is not present in your checkout, apply the latest helper bundle or use the raw command equivalents shown below.

---

## 3. Start from a Clean Shell

Run this before GitHub governance work:

```bash
cd ~/dev/artwork-db
git switch feat/optimize-dagster-options

unset GH_TOKEN GITHUB_TOKEN GITHUB_PAT DCKALLOS_GITHUB_TOKEN TMP_GH_TOKEN
export GH_CONFIG_DIR="$HOME/.config/gh-artwork-admin"
mkdir -p "$GH_CONFIG_DIR"
```

Clean up stale shell startup tokens:

```bash
# Inspect only. Do not paste tokens anywhere.
grep -nE 'GH_TOKEN|GITHUB_TOKEN|GITHUB_PAT|DCKALLOS_GITHUB_TOKEN|TMP_GH_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY' ~/.zshrc || true
```

Edit `~/.zshrc` and remove any exported API tokens. Then rotate/revoke those tokens in their provider UIs and start a new shell.

Sample expected output after cleanup:

```text
# no output from grep, or only commented documentation lines
```

---

## 4. Apply Helper Permissions

Preferred:

```bash
bash scripts/setup/fix_helper_permissions.sh
```

Fallback if that helper is not present:

```bash
rm -rf scripts/setup/__pycache__
chmod +x scripts/setup/*.sh scripts/snowflake_account_defaults.sh tools/github/wrappers/*.sh
```

Sample output:

```text
chmod +x scripts/setup/*.sh scripts/snowflake_account_defaults.sh tools/github/wrappers/*.sh
helper permissions fixed
```

---

## 5. Generate and Review `.env`

Preview:

```bash
bash scripts/setup/write_local_env.sh --target .env
```

Apply:

```bash
bash scripts/setup/write_local_env.sh --target .env --apply --force
chmod 600 .env
```

Sample output:

```text
DRY-RUN: would write .env from /Users/daniel/dev/artwork-db/.env.example
Nothing changed. Re-run with:
  bash scripts/setup/write_local_env.sh --target .env --apply --force
```

Apply sample output:

```text
backed up .env -> .env.bak.20260704T184612Z
wrote .env (mode 600)
Edit SMITHSONIAN_API_KEY and GitHub git-setup values before using those integrations.
```

Now edit `.env` and fill values that are intentionally blank or placeholder-only:

```bash
$EDITOR .env
```

Minimum values for normal Snowflake/dbt setup:

```bash
SNOWFLAKE_ACCOUNT=DSHXYWJ-KW94245
SNOW_CONNECTION=kw94245
SNOWFLAKE_USER=ARTWORK_LOADER_SVC
SNOWFLAKE_PRIVATE_KEY_FILE=~/.snowflake/keys/kw94245_loader_rsa_key.p8
SNOWFLAKE_ROLE=ARTWORK_LOADER
SNOWFLAKE_WAREHOUSE=ARTWORK_WH
SNOWFLAKE_DATABASE=ARTWORK_DB
DBT_TARGET=dev
DBT_SNOWFLAKE_USER=ARTWORK_TRANSFORMER_SVC
DBT_SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/kw94245_transformer_rsa_key.p8
DBT_SNOWFLAKE_ROLE=ARTWORK_TRANSFORMER
DBT_SNOWFLAKE_SCHEMA=dbt_daniel
TOOLKIT_DIR=../snowflake-toolkit
```

Values needed only for extraction / APIs:

```bash
SMITHSONIAN_API_KEY=...
MET_SQLITE_PATH=./data/met.db
MET_CSV_LOCAL_PATH=./data/MetObjects.csv
MET_API_CONCURRENCY=10
MET_API_RPS=20
MET_API_MAX_RETRIES=5
MET_API_TIMEOUT=30
MET_API_USER_AGENT="artwork-medallion-pipeline/1.0 (contact: you@example.com)"
MET_UPLOAD_CHUNK=5000
AIC_DATA_DIR=./data
AIC_TAR_PATH=./data/aic_dump.tar.bz2
AIC_EXTRACT_DIR=./data/aic_extract
```

Values needed only for Snowflake `git-setup`:

```bash
GITHUB_PAT=...
GITHUB_OAUTH_CLIENT_ID=...
GITHUB_OAUTH_CLIENT_SECRET=...
```

Do not commit `.env`.

---

## 6. Run the Local Doctor

```bash
bash scripts/setup/doctor_local_setup.sh
```

Sample successful-ish output:

```text
==> artwork-db local setup doctor
Snowflake target:
  profile          kw94245
  account          DSHXYWJ-KW94245
  admin user       PORCHORCH
  admin role       ACCOUNTADMIN
  init warehouse   COMPUTE_WH
  project wh/db    ARTWORK_WH / ARTWORK_DB
  staging/prod wh  ARTWORK_WH_STAGING / ARTWORK_WH_PROD
  dev schema       dbt_daniel
  loader           ARTWORK_LOADER_SVC / ARTWORK_LOADER
  transformer      ARTWORK_TRANSFORMER_SVC / ARTWORK_TRANSFORMER
  toolkit          /Users/daniel/dev/artwork-db/../snowflake-toolkit
✅ repo root: /Users/daniel/dev/artwork-db
✅ git branch: feat/optimize-dagster-options
✅ found command: bash
✅ found command: python3
✅ found command: snow
✅ found command: gh
✅ snowflake-toolkit found: /Users/daniel/dev/artwork-db/../snowflake-toolkit
✅ env file exists: /Users/daniel/dev/artwork-db/.env
✅ .env SNOWFLAKE_ACCOUNT=DSHXYWJ-KW94245
✅ Snowflake CLI profile 'kw94245' points at DSHXYWJ-KW94245
✅ no GH_TOKEN/GITHUB_TOKEN/GITHUB_PAT-style variables exported

Doctor summary: 0 failure(s), 0 warning(s).
```

If doctor warns about tokens in `~/.zshrc`, fix that before continuing.

---

## 7. Bootstrap Snowflake Profile, DDL, Loader Key, and Transformer Key

### Preferred helper flow

Preview:

```bash
bash scripts/setup/bootstrap_snowflake_account.sh --replace-existing
```

Apply:

```bash
bash scripts/setup/bootstrap_snowflake_account.sh --replace-existing --apply
```

What this performs, in order:

```bash
# local prereqs + seed [kw94245]
bash ../snowflake-toolkit/snowflake_cli/setup.sh \
  --profile kw94245 \
  --account DSHXYWJ-KW94245 \
  --admin-user PORCHORCH \
  --admin-role ACCOUNTADMIN \
  --init-warehouse COMPUTE_WH \
  --replace-existing \
  --phase prereq

# register the admin public key; prompts for Snowflake admin password
bash ../snowflake-toolkit/snowflake_cli/setup.sh \
  --profile kw94245 \
  --account DSHXYWJ-KW94245 \
  --admin-user PORCHORCH \
  --phase admin

# apply core infrastructure / DDL
make infra CONN=kw94245 TOOLKIT_DIR=../snowflake-toolkit

# promote admin profile from COMPUTE_WH to ARTWORK_WH
bash ../snowflake-toolkit/snowflake_cli/setup.sh \
  --profile kw94245 \
  --target-warehouse ARTWORK_WH \
  --phase promote

# register loader and transformer service-user public keys
bash ../snowflake-toolkit/snowflake_cli/setup.sh --profile kw94245 --phase loader
bash ../snowflake-toolkit/snowflake_cli/setup.sh --profile kw94245 --phase transformer
```

Sample successful snippets:

```text
==> connections: admin='kw94245' loader='kw94245_loader' transformer='kw94245_transformer'
==> admin target: account='DSHXYWJ-KW94245' user='PORCHORCH'
...
==> Applying infrastructure via sibling snowflake-toolkit -> snow sql --filename...
==> [orchestrate_modern] Executing script: create_roles.sql
==> [orchestrate_modern] Executing script: create_warehouses.sql
==> [orchestrate_modern] Executing script: create_databases_and_schemas.sql
...
==> setup.sh phase 'transformer' complete.
```

Verify Snowflake CLI profiles:

```bash
snow connection test --connection kw94245
snow connection test --connection kw94245_loader
snow connection test --connection kw94245_transformer
```

Sample output:

```text
+----------------------------------------------------------+
| key             | value                                  |
|-----------------|----------------------------------------|
| Connection name | kw94245                                |
| Status          | OK                                     |
| Host            | DSHXYWJ-KW94245.snowflakecomputing.com |
| Account         | DSHXYWJ-KW94245                        |
| User            | PORCHORCH                              |
| Role            | ACCOUNTADMIN                           |
| Warehouse       | ARTWORK_WH                             |
+----------------------------------------------------------+
```

### Raw command fallback

Use this if the helper script is unavailable:

```bash
cd ~/dev/artwork-db
source ../snowflake-toolkit/unload_profile.sh 2>/dev/null || true

bash ../snowflake-toolkit/snowflake_cli/setup.sh \
  --profile kw94245 \
  --account DSHXYWJ-KW94245 \
  --admin-user PORCHORCH \
  --admin-role ACCOUNTADMIN \
  --init-warehouse COMPUTE_WH \
  --replace-existing \
  --phase prereq

bash ../snowflake-toolkit/snowflake_cli/setup.sh \
  --profile kw94245 \
  --account DSHXYWJ-KW94245 \
  --admin-user PORCHORCH \
  --phase admin

make infra CONN=kw94245 TOOLKIT_DIR=../snowflake-toolkit

bash ../snowflake-toolkit/snowflake_cli/setup.sh \
  --profile kw94245 \
  --target-warehouse ARTWORK_WH \
  --phase promote

bash ../snowflake-toolkit/snowflake_cli/setup.sh --profile kw94245 --phase loader
bash ../snowflake-toolkit/snowflake_cli/setup.sh --profile kw94245 --phase transformer
```

---

## 8. Avoid the Known Bad Profile Trap

Do **not** run:

```bash
make infra CONN=KW94245
```

Do **not** run:

```bash
bash ../snowflake-toolkit/snowflake_cli/setup.sh --profile KW94245 --phase all
```

If you accidentally created `[KW94245]` and it points to the wrong account, back up your Snowflake config and remove that profile manually:

```bash
cp ~/.snowflake/connections.toml ~/.snowflake/connections.toml.bak.$(date -u +%Y%m%dT%H%M%SZ)
$EDITOR ~/.snowflake/connections.toml
```

Delete the entire bad block:

```toml
[KW94245]
account = "KUNHTEL-GL13131"
...
```

Then use lowercase only:

```bash
snow connection test --connection kw94245
make infra CONN=kw94245 TOOLKIT_DIR=../snowflake-toolkit
```

If `echo $SNOWFLAKE_ACCOUNT` shows an old account such as `KUNHTEL-GL13131`, clean the shell:

```bash
source ../snowflake-toolkit/unload_profile.sh 2>/dev/null || true
unset SNOWFLAKE_ACCOUNT SNOWFLAKE_USER SNOWFLAKE_ROLE SNOWFLAKE_WAREHOUSE SNOWFLAKE_DATABASE SNOWFLAKE_PRIVATE_KEY_FILE SNOWFLAKE_PRIVATE_KEY_PATH
unset DBT_TARGET DBT_SNOWFLAKE_USER DBT_SNOWFLAKE_PRIVATE_KEY_PATH DBT_SNOWFLAKE_ROLE DBT_SNOWFLAKE_SCHEMA
```

Then check `.env`:

```bash
grep '^SNOWFLAKE_ACCOUNT=' .env
# expected:
# SNOWFLAKE_ACCOUNT=DSHXYWJ-KW94245
```

---

## 9. Validate dbt Locally

Install Python requirements:

```bash
cd ~/dev/artwork-db
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Load runtime variables only when doing runtime/dbt work, not admin/bootstrap work:

```bash
set -a
source .env
set +a
```

Validate dbt:

```bash
dbt debug --project-dir artwork_pipeline --profiles-dir artwork_pipeline
dbt deps  --project-dir artwork_pipeline --profiles-dir artwork_pipeline
dbt parse --project-dir artwork_pipeline --profiles-dir artwork_pipeline --target dev --no-partial-parse
```

Sample success output:

```text
Connection test: [OK connection ok]
All checks passed!
...
Running with dbt=1.x.x
Registered adapter: snowflake=1.x.x
Performance info: artwork_pipeline/target/perf_info.json
```

Optional local build:

```bash
make dbt-build
make dbt-test
```

---

## 10. Optional Snowflake `git-setup` / Git Repository / MCP Setup

Run this only if `.env` contains real values for:

```bash
GITHUB_PAT=...
GITHUB_OAUTH_CLIENT_ID=...
GITHUB_OAUTH_CLIENT_SECRET=...
```

Preview:

```bash
bash scripts/setup/run_git_setup.sh
```

Apply:

```bash
bash scripts/setup/run_git_setup.sh --apply
```

Raw equivalent:

```bash
make bootstrap CONN=kw94245 TOOLKIT_DIR=../snowflake-toolkit ENV_FILE=.env
```

Sample output:

```text
==> Applying git-setup (B) via bash orchestrator -> snow sql --filename...
==> [orchestrate_modern] Executing script: create_git_ops_db.sql
==> [orchestrate_modern] Executing script: create_api_integration.sql
==> [orchestrate_modern] Executing script: create_git_repository.sql
==> [orchestrate_modern] Executing script: create_mcp_integration.sql
```

Verify in Snowflake:

```bash
snow sql --connection kw94245 --query "SHOW GIT REPOSITORIES IN SCHEMA ARTWORK_OPS.GIT"
snow sql --connection kw94245 --query "SHOW API INTEGRATIONS LIKE 'GITHUB_%'"
```

---

## 11. Create CI Snowflake Profiles for `ghclient`

Preview:

```bash
python3 scripts/setup/create_ci_snowflake_profiles.py
```

Apply and test:

```bash
python3 scripts/setup/create_ci_snowflake_profiles.py --apply --test
```

This creates or updates:

```text
[artwork_ci_staging]
[artwork_ci_prod]
```

Sample dry-run output:

```text
Snowflake CI profile plan
  connections.toml: /Users/daniel/.snowflake/connections.toml
  account:          DSHXYWJ-KW94245
  user/role:        ARTWORK_TRANSFORMER_SVC / ARTWORK_TRANSFORMER
  database:         ARTWORK_DB
  source key:       /Users/daniel/.snowflake/keys/kw94245_transformer_rsa_key.p8
  mode:             DRY-RUN
would copy /Users/daniel/.snowflake/keys/kw94245_transformer_rsa_key.p8 -> /Users/daniel/.snowflake/keys/staging_ci.p8
would copy /Users/daniel/.snowflake/keys/kw94245_transformer_rsa_key.p8 -> /Users/daniel/.snowflake/keys/prod_ci.p8
would upsert [artwork_ci_staging] warehouse=ARTWORK_WH_STAGING
would upsert [artwork_ci_prod] warehouse=ARTWORK_WH_PROD
dry-run: nothing changed; re-run with --apply to write profiles
```

Sample apply/test output:

```text
testing snow connection: artwork_ci_staging
+----------------------------------------------------------+
| key             | value                                  |
|-----------------|----------------------------------------|
| Connection name | artwork_ci_staging                     |
| Status          | OK                                     |
| Host            | DSHXYWJ-KW94245.snowflakecomputing.com |
| Account         | DSHXYWJ-KW94245                        |
| User            | ARTWORK_TRANSFORMER_SVC                |
| Role            | ARTWORK_TRANSFORMER                    |
| Database        | ARTWORK_DB                             |
| Warehouse       | ARTWORK_WH_STAGING                     |
+----------------------------------------------------------+
```

---

## 12. Install and Preflight `ghclient`

Preferred helper:

```bash
bash scripts/setup/install_ghclient.sh
```

Direct zsh-safe command:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e 'tools/github[dev]'
hash -r
ghclient --help
```

If zsh says `no matches found: tools/github[dev]`, quote the entire argument or use `noglob`:

```bash
python -m pip install -e 'tools/github[dev]'
# or
noglob python -m pip install -e tools/github[dev]
```

Authenticate GitHub CLI into a clean config directory:

```bash
unset GH_TOKEN GITHUB_TOKEN GITHUB_PAT DCKALLOS_GITHUB_TOKEN TMP_GH_TOKEN
export GH_CONFIG_DIR="$HOME/.config/gh-artwork-admin"
mkdir -p "$GH_CONFIG_DIR"

gh auth login -h github.com -s repo
gh auth status -h github.com
ghclient preflight
```

Sample `ghclient preflight` output:

```text
[ok] gh auth: authenticated
[ok] config: dckallos/artwork-db (1 protected branch(es))
[ok] repo admin: admin: true
preflight: PASS
```

---

## 13. Create GitHub Environments and Publish CI Secrets/Variables

Dry-run / preview:

```bash
bash scripts/setup/github_governance.sh
```

Apply Environments + CI settings:

```bash
bash scripts/setup/github_governance.sh --apply --force-secrets
```

Expected GitHub objects:

```text
GitHub Environments:
  staging
  prod

Environment Variables:
  SNOWFLAKE_ACCOUNT
  SNOWFLAKE_DATABASE
  DBT_SNOWFLAKE_ROLE
  SNOWFLAKE_WAREHOUSE
  DBT_TARGET

Environment Secrets:
  DBT_SNOWFLAKE_USER
  DBT_SNOWFLAKE_PRIVATE_KEY
```

Sample dry-run output:

```text
==> GitHub governance for dckallos/artwork-db
GH_CONFIG_DIR=/Users/daniel/.config/gh-artwork-admin
[ok] gh auth: authenticated
[ok] config: dckallos/artwork-db (1 protected branch(es))
[ok] repo admin: admin: true
preflight: PASS
+ gh api --method PUT repos/dckallos/artwork-db/environments/staging --input ...
+ gh api --method PUT repos/dckallos/artwork-db/environments/prod --input ...
+ ghclient secrets publish --profile-set staging
  [create] staging/SNOWFLAKE_ACCOUNT (variable)  None -> 'DSHXYWJ-KW94245'
  [create] staging/SNOWFLAKE_DATABASE (variable) None -> 'ARTWORK_DB'
  [create] staging/DBT_SNOWFLAKE_USER (secret)
  [create] staging/DBT_SNOWFLAKE_ROLE (variable) None -> 'ARTWORK_TRANSFORMER'
  [create] staging/SNOWFLAKE_WAREHOUSE (variable) None -> 'ARTWORK_WH_STAGING'
  [create] staging/DBT_SNOWFLAKE_PRIVATE_KEY (secret)
```

Verify GitHub Environment settings:

```bash
gh secret list --env staging --repo dckallos/artwork-db
gh variable list --env staging --repo dckallos/artwork-db

gh secret list --env prod --repo dckallos/artwork-db
gh variable list --env prod --repo dckallos/artwork-db
```

Sample output:

```text
DBT_SNOWFLAKE_PRIVATE_KEY   2026-07-04T18:56:00Z
DBT_SNOWFLAKE_USER          2026-07-04T18:56:00Z
```

```text
DBT_SNOWFLAKE_ROLE    ARTWORK_TRANSFORMER
DBT_TARGET            staging
SNOWFLAKE_ACCOUNT     DSHXYWJ-KW94245
SNOWFLAKE_DATABASE    ARTWORK_DB
SNOWFLAKE_WAREHOUSE   ARTWORK_WH_STAGING
```

---

## 14. Verify Operational Readiness

Run all read-only checks:

```bash
bash scripts/setup/verify_operational_readiness.sh
```

Skip branch-protection checks unless explicitly requested. If your version checks branch protection by default and you hit a `403`, use the fixed helper or skip GitHub branch protection for now.

Useful variants:

```bash
# Snowflake/dbt only
bash scripts/setup/verify_operational_readiness.sh --skip-gh

# GitHub Environment checks only
bash scripts/setup/verify_operational_readiness.sh --skip-snow --skip-dbt

# Staging only
bash scripts/setup/verify_operational_readiness.sh --staging-only
```

Sample success output:

```text
==> snow admin connection
+ snow connection test --connection kw94245
✅ snow admin connection passed

==> snow loader connection
+ snow connection test --connection kw94245_loader
✅ snow loader connection passed

==> snow transformer connection
+ snow connection test --connection kw94245_transformer
✅ snow transformer connection passed

==> snow staging CI connection
+ snow connection test --connection artwork_ci_staging
✅ snow staging CI connection passed

==> dbt debug
+ dbt debug --project-dir artwork_pipeline --profiles-dir artwork_pipeline
✅ dbt debug passed

==> ghclient preflight
+ ghclient preflight
✅ ghclient preflight passed

Readiness summary: 0 failure(s).
```

---

## 15. Optional Extraction and Pipeline Commands

After Snowflake/dbt readiness passes, run extraction and dbt workflows as needed.

Met extraction:

```bash
make extract-met
```

Pipeline:

```bash
make pipeline
```

dbt only:

```bash
make dbt-build
make dbt-test
make dbt-docs
```

Status SQL helpers:

```bash
snow sql --connection kw94245_loader --filename scripts/sql/show_pipeline_status.sql
snow sql --connection kw94245_loader --filename scripts/sql/show_run_control.sql
```

---

## 16. Branch Protection: Diagnose / Preview / Apply Later

Branch protection is intentionally separate from GitHub Environment setup.

### Diagnose access

```bash
bash scripts/setup/diagnose_branch_protection_access.sh
```

Raw API diagnostic:

```bash
gh api -i repos/dckallos/artwork-db/branches/main/protection
```

If you see `403`, do not block Snowflake/GitHub Environment setup on it. A private repo may need the right GitHub plan/feature availability for protected branches, even when repo-admin metadata is true.

### Preview branch protection

```bash
bash scripts/setup/github_governance.sh --preview-branch-protection
```

Raw preview commands:

```bash
ghclient audit --branch main || true
bash tools/github/wrappers/protect.sh --branch main
bash tools/github/wrappers/reconcile-ci.sh --branch main || true
```

### Apply branch protection only after CI is green

```bash
bash scripts/setup/github_governance.sh --apply-branch-protection
```

Raw apply commands:

```bash
ghclient branch-protection export --branch main
bash tools/github/wrappers/protect.sh --branch main --apply
bash tools/github/wrappers/reconcile-ci.sh --branch main --apply
```

Rollback if needed:

```bash
bash tools/github/wrappers/rollback.sh --branch main
bash tools/github/wrappers/rollback.sh --branch main --apply
```

Stop if there is a ruleset-overlap warning unless you have deliberately reviewed it.

---

## 17. Troubleshooting Matrix

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `zsh: no matches found: tools/github[dev]` | zsh glob expansion | `python -m pip install -e 'tools/github[dev]'` |
| `SNOWFLAKE_ACCOUNT=KUNHTEL-GL13131` | Old `.env` or sourced toolkit `.env` | Unload/unset env vars; regenerate `.env`; use helper scripts. |
| `make infra CONN=KW94245` fails against `KUNHTEL-GL13131` | Bad uppercase Snowflake CLI profile | Remove `[KW94245]`; use lowercase `kw94245`. |
| `JWT token is invalid` | Key not registered for that user/account, or wrong account/profile | Re-run `setup.sh --profile kw94245 --account DSHXYWJ-KW94245 --admin-user PORCHORCH --phase admin`; verify profile account. |
| `Incorrect username or password` during admin registration | Wrong account/user or password | Confirm Snowflake account details and admin user; use explicit flags. |
| `prod environment does not exist yet` in dry-run | Dry-run does not create Environments | Run `bash scripts/setup/github_governance.sh --apply --force-secrets`. |
| `Permission denied: tools/github/wrappers/protect.sh` | Missing executable bit | Run `bash scripts/setup/fix_helper_permissions.sh` or call wrapper via `bash`. |
| `ghclient audit --branch main` gives `403` | Branch-protection endpoint unavailable/forbidden | Diagnose separately; continue with Environment secrets/vars; do not apply branch protection. |
| GitHub CLI uses wrong token | `GH_TOKEN`/`GITHUB_TOKEN` exported in shell | `unset` token variables and use `GH_CONFIG_DIR=$HOME/.config/gh-artwork-admin`. |
| `.zshrc` contains tokens | Unsafe shell startup | Rotate/revoke tokens, remove exports, start a new shell. |

---

## 18. End-State Checklist

Use this as the final pass/fail list.

### Local Snowflake CLI

```bash
snow connection test --connection kw94245
snow connection test --connection kw94245_loader
snow connection test --connection kw94245_transformer
snow connection test --connection artwork_ci_staging
snow connection test --connection artwork_ci_prod
```

Expected: all `Status = OK` and all accounts show `DSHXYWJ-KW94245`.

### dbt

```bash
dbt debug --project-dir artwork_pipeline --profiles-dir artwork_pipeline
dbt deps --project-dir artwork_pipeline --profiles-dir artwork_pipeline
dbt parse --project-dir artwork_pipeline --profiles-dir artwork_pipeline --target dev --no-partial-parse
```

Expected: all commands pass.

### GitHub CLI / ghclient

```bash
gh auth status -h github.com
ghclient preflight
```

Expected:

```text
[ok] gh auth: authenticated
[ok] config: dckallos/artwork-db (1 protected branch(es))
[ok] repo admin: admin: true
preflight: PASS
```

### GitHub Environments

```bash
gh secret list --env staging --repo dckallos/artwork-db
gh variable list --env staging --repo dckallos/artwork-db
gh secret list --env prod --repo dckallos/artwork-db
gh variable list --env prod --repo dckallos/artwork-db
```

Expected staging/prod secrets:

```text
DBT_SNOWFLAKE_USER
DBT_SNOWFLAKE_PRIVATE_KEY
```

Expected staging/prod variables:

```text
SNOWFLAKE_ACCOUNT
SNOWFLAKE_DATABASE
DBT_SNOWFLAKE_ROLE
SNOWFLAKE_WAREHOUSE
DBT_TARGET
```

### Optional Snowflake git-setup

```bash
snow sql --connection kw94245 --query "SHOW GIT REPOSITORIES IN SCHEMA ARTWORK_OPS.GIT"
snow sql --connection kw94245 --query "SHOW API INTEGRATIONS LIKE 'GITHUB_%'"
```

Expected: `artwork_db`, `dbt_diagnostics`, and `snowflake_toolkit` Git repositories exist if git-setup was applied.

---

## 19. Minimal Golden Path Copy/Paste

This assumes helper scripts are already present and reviewed.

```bash
cd ~/dev/artwork-db
git switch feat/optimize-dagster-options

unset GH_TOKEN GITHUB_TOKEN GITHUB_PAT DCKALLOS_GITHUB_TOKEN TMP_GH_TOKEN
export GH_CONFIG_DIR="$HOME/.config/gh-artwork-admin"
mkdir -p "$GH_CONFIG_DIR"

bash scripts/setup/fix_helper_permissions.sh 2>/dev/null || chmod +x scripts/setup/*.sh scripts/snowflake_account_defaults.sh tools/github/wrappers/*.sh
bash scripts/setup/write_local_env.sh --target .env --apply --force
$EDITOR .env
bash scripts/setup/doctor_local_setup.sh

bash scripts/setup/bootstrap_snowflake_account.sh --replace-existing --apply
python3 scripts/setup/create_ci_snowflake_profiles.py --apply --test

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
bash scripts/setup/install_ghclient.sh 2>/dev/null || python -m pip install -e 'tools/github[dev]'

gh auth login -h github.com -s repo
ghclient preflight

bash scripts/setup/github_governance.sh --apply --force-secrets
bash scripts/setup/verify_operational_readiness.sh
```

Optional after `.env` has real GitHub PAT/OAuth values:

```bash
bash scripts/setup/run_git_setup.sh --apply
```

Optional after CI is green and branch-protection access is confirmed:

```bash
bash scripts/setup/diagnose_branch_protection_access.sh
bash scripts/setup/github_governance.sh --apply-branch-protection
```
