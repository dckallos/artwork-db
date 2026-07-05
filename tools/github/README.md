# ghclient -- GitHub governance client

Config-driven client for governing the `dckallos/artwork-db` GitHub repo:
branch protection (Area A), GitHub Environment Snowflake secret/variable publishing
(Area B), and CI reconcile (Area C). Behavior is **configured**, not hardcoded --
the repo slug, protected branches, policy bodies, Snowflake profile mappings, and
CI aggregate context all come from `config/github-client-config.yml` and
`policies/*.json`.

## What exists today

- `ghclient preflight` -- verify `gh` auth, `jq`, and config validity.
- `ghclient branch-protection apply|export|rollback` -- classic branch
  protection, **dry-run by default**; `--apply` is required to mutate.
- `ghclient audit export` -- inventory **both** classic protection **and** repo
  rulesets, report overlap (v1 mutates classic only), and snapshot the classic
  state.
- `ghclient secrets publish` -- publish allowlisted Snowflake connection profiles
  to GitHub Environments. Non-sensitive metadata such as `SNOWFLAKE_ACCOUNT`,
  role, and warehouse are Variables; user, private key, and passphrase are
  Secrets. Values are supplied through stdin, not argv.
- `ghclient ci reconcile` -- reconcile required branch-protection checks to the
  single always-emitting `ci-required` aggregate context.

## Install

```
pip install -e tools/github
```

`gh` must be installed and authenticated as a repo admin (`gh auth login`);
`jq` is used for snapshot formatting. Runs from a maintainer's authenticated
terminal -- **never from CI** (no CI job may run `ghclient ... --apply`).

## Usage

```
ghclient preflight
ghclient branch-protection apply              # dry-run: prints the exact PUT body
ghclient branch-protection apply --apply      # applies to all configured branches
ghclient branch-protection apply --branch main --apply
ghclient branch-protection export             # snapshot live state -> policies/exports/
ghclient audit export                         # classic + ruleset inventory + overlap
ghclient branch-protection rollback           # dry-run: preview DELETE/PUT
ghclient branch-protection rollback --apply
ghclient secrets publish --profile-set staging          # dry-run
ghclient secrets publish --profile-set staging --apply
ghclient ci reconcile                                  # dry-run
ghclient ci reconcile --apply
```

Thin wrappers (no arg memorization) live in `wrappers/`:
`protect.sh` -> apply, `rollback.sh` -> rollback.

## Safety model

- **Dry-run by default.** Every mutating verb previews the exact change and does
  nothing without `--apply`.
- **Fail-closed export (H1).** A snapshot records `null` (no protection) ONLY
  for a *verified* HTTP 404. Any other `gh` failure writes no snapshot and exits
  non-zero, so "couldn't reach GitHub" is never mistaken for "no rules".
- **Ruleset-aware (H9).** Apply and rollback audit rulesets alongside classic
  protection first; mutating commands block on overlap unless a maintainer uses
  the explicit override.
- **Snapshots are not committed.** `policies/exports/` is gitignored (§12.2.3);
  the committed source of truth is `policies/policy.main.json`.

## Layout

```
config/github-client-config.yml   # repo, protected branches, policy refs (repo root)
tools/github/
  ghclient/                       # typed, tested Python package
    config.py                     # load + validate config -> frozen dataclasses
    gh.py                         # GhRunner: the single injectable `gh` seam
    branch_protection.py          # apply/export/rollback/audit (pure plan + exec)
    preflight.py                  # environment checks
    cli.py                        # `ghclient` typer entrypoint
    errors.py                     # ConfigError / GhError (file/field-scoped)
    connections.py                  # read Snowflake CLI connections.toml profiles
    secrets.py                      # plan/apply environment secrets + variables
    ci.py                           # reconcile aggregate required-check policy
  policies/policy.main.json       # desired-state body (committed)
  policies/exports/               # before-state snapshots (gitignored)
  wrappers/                       # protect.sh, rollback.sh
  tests/                          # unit + integration (all no-network)
```

## Tests

```
pip install -e tools/github
python -m pytest tools/github/tests
```

All tests are offline: every `gh` call is routed through a stubbed `GhRunner`.

## CI Environment contract

The Snowflake CI profile is Environment-scoped. Jobs that consume published values
must declare the matching GitHub Environment and read Variables with `vars.*` and
Secrets with `secrets.*`. The dbt CI job uses `deployment: false` so it can access
the Environment values without creating a deployment record.
