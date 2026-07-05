# setup helpers

These helper scripts are intentionally dry-run first where practical. They are
repo-local wrappers around the already-versioned Snowflake toolkit, Makefile,
Snowflake CLI, GitHub CLI, and ghclient commands.

Run from the artwork-db repository root unless a script says otherwise.

Suggested order:

1. `bash scripts/setup/doctor_local_setup.sh`
2. `bash scripts/setup/write_local_env.sh --target .env --apply`
3. `bash scripts/setup/bootstrap_snowflake_account.sh --replace-existing --apply`
4. `bash scripts/setup/run_git_setup.sh` then `bash scripts/setup/run_git_setup.sh --apply`
5. `python3 scripts/setup/create_ci_snowflake_profiles.py --apply --test`
6. `bash scripts/setup/github_governance.sh` then `bash scripts/setup/github_governance.sh --apply --force-secrets`
7. `bash scripts/setup/verify_operational_readiness.sh`
8. Only after CI is green: `bash scripts/setup/github_governance.sh --apply-branch-protection`

No script writes secret values to stdout. Scripts that can mutate Snowflake or
GitHub require explicit apply flags.
