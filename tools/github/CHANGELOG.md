# Changelog -- tools/github

## Unreleased (Area A)

### Added
- `ghclient` package (standalone `tools/github/pyproject.toml`): config loader,
  `GhRunner` seam, `preflight`, and classic branch-protection
  apply/export/rollback + `audit export` (dry-run default; `--apply` to mutate).
- `config/github-client-config.yml` (Model A: protects `main` only).
- `policies/policy.main.json` and thin wrappers `wrappers/protect.sh`,
  `wrappers/rollback.sh`.
- H1 fail-closed export/rollback and H9 ruleset-aware audit.

### Moved (from `bin/`, §12.2.9)
The branch-protection scripts were **ported into this package and deleted** from
`bin/`:
- `bin/apply-branch-protection.sh`  -> `ghclient branch-protection apply` (+ `wrappers/protect.sh`)
- `bin/export-branch-protection.sh` -> `ghclient branch-protection export`
- `bin/rollback-branch-protection.sh` -> `ghclient branch-protection rollback` (+ `wrappers/rollback.sh`)
- `bin/policy.main.json`             -> `tools/github/policies/policy.main.json`

### Removed
- `bin/policy.donkey-kong-sandbox.json` -- Model A protects `main` ONLY
  (§12.2.6); the sandbox policy is not ported.

`bin/check_no_attribution.sh` is intentionally left in place (Area C, H7).
