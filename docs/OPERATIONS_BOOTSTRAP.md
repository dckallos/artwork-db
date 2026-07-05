# Local Snowflake + GitHub Governance Bootstrap

This document is the runbook for a fresh `artwork-db` checkout paired with the
`snowflake-toolkit` sibling repo.

All scripts are intended to run from the `artwork-db` repo root. The scripts are
safe to preview first: Snowflake/GitHub mutation requires explicit apply flags.

## 0. Clean shell state

```bash
cd ~/dev/artwork-db
git switch feat/optimize-dagster-options

unset GH_TOKEN GITHUB_TOKEN GITHUB_PAT DCKALLOS_GITHUB_TOKEN TMP_GH_TOKEN
export GH_CONFIG_DIR="$HOME/.config/gh-artwork-admin"
mkdir -p "$GH_CONFIG_DIR"
```

Rotate and remove any API tokens that were previously exported from shell startup
files. Do not store real tokens in `.env.example`, git, screenshots, prompts, or
logs.

## 1. Install helper files and write `.env`

```bash
bash scripts/setup/write_local_env.sh --target .env
bash scripts/setup/write_local_env.sh --target .env --apply --force
```

Then edit `.env` for real `SMITHSONIAN_API_KEY`, `GITHUB_PAT`, and optional
GitHub OAuth values. The GitHub values are required only for Snowflake `git-setup`.

## 2. Local doctor

```bash
bash scripts/setup/doctor_local_setup.sh
```

Fix every failure before applying setup. Warnings about old uppercase profiles are
usually solved by using the lowercase profile `kw94245`.

## 3. Bootstrap Snowflake account, infrastructure, loader, and transformer

Preview:

```bash
bash scripts/setup/bootstrap_snowflake_account.sh --replace-existing
```

Apply:

```bash
bash scripts/setup/bootstrap_snowflake_account.sh --replace-existing --apply
```

This wraps the toolkit phases in the correct order:

1. `setup.sh --phase prereq`
2. `setup.sh --phase admin`
3. `make infra CONN=kw94245`
4. `setup.sh --phase promote`
5. `setup.sh --phase loader`
6. `setup.sh --phase transformer`

## 4. Apply Snowflake git-setup

The `git-setup` SQL creates `ARTWORK_OPS`, the GitHub PAT secret, Git API
integration, Git repository objects, and the external MCP integration. The full
manifest needs all three values: `GITHUB_PAT`, `GITHUB_OAUTH_CLIENT_ID`, and
`GITHUB_OAUTH_CLIENT_SECRET`.

Preview:

```bash
bash scripts/setup/run_git_setup.sh
```

Apply:

```bash
bash scripts/setup/run_git_setup.sh --apply
```

Equivalent raw command:

```bash
make bootstrap CONN=kw94245 TOOLKIT_DIR=../snowflake-toolkit ENV_FILE=.env
```

## 5. Create local CI Snowflake profiles for ghclient

Preview:

```bash
python3 scripts/setup/create_ci_snowflake_profiles.py
```

Apply and test:

```bash
python3 scripts/setup/create_ci_snowflake_profiles.py --apply --test
```

This creates/updates local `[artwork_ci_staging]` and `[artwork_ci_prod]` blocks
in `~/.snowflake/connections.toml`, and copies the transformer private key to the
paths used by `config/github-client-config.yml`.

## 6. GitHub Environments, secrets, variables, and governance

Install `ghclient` and log in with repo-admin permission:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e "tools/github[dev]"

gh auth login -h github.com -s repo
ghclient preflight
```

Preview GitHub governance:

```bash
bash scripts/setup/github_governance.sh
```

Create environments and publish environment secrets/variables:

```bash
bash scripts/setup/github_governance.sh --apply --force-secrets
```

Only after CI is green, apply branch protection and reconcile the required check:

```bash
bash scripts/setup/github_governance.sh --apply-branch-protection
```

## 7. Verify

```bash
bash scripts/setup/verify_operational_readiness.sh
```

This checks Snowflake CLI profiles, dbt debug/deps/parse, ghclient preflight,
GitHub Environment secrets/variables, and branch-protection audit.
