# Changelog -- tools/github

## Unreleased (Area C)

### Added
- `ghclient ci reconcile [--branch] [--apply]`: reconciles a protected branch's
  required status checks to the always-emitting aggregate context `ci-required`
  (H2), derived from and validated against the workflows in `ci.workflows`
  (matrix / skipped / duplicate jobs handled). Dry-run by default; `--apply`
  issues one idempotent `PATCH`. Pure plan-building in `ghclient/ci.py`;
  execution through the injected `GhRunner`.
- Typed `ci` config block (`CiCfg`: `workflows`, `required_checks`,
  `aggregate_context`) parsed and validated in `config.py` (unknown keys
  rejected; file/field-scoped errors). `config/github-client-config.yml` now
  declares `aggregate_context: ci-required`.
- `wrappers/reconcile-ci.sh` (thin wrapper, dry-run default).
- Tests: `tests/unit/test_ci.py` (derivation + H2 + H5 adversarial),
  `ci reconcile` dispatch in `tests/integration/test_cli_smoke.py`, and
  `tests/integration/test_authorship_guard.py`; workflow fixtures under
  `tests/fixtures/`.

### Changed
- `.github/workflows/ci.yml`: triggers on every PR and ends in an always-emitting
  `ci-required` aggregate job (fixes the docs-only-PR deadlock); adds actionlint,
  shellcheck, a `tools/github` installed-package smoke, byte-compile + docstring
  gates, explicit minimal `permissions:`, and per-workflow+ref `concurrency:`.
  The credentialed dbt checks are isolated in a path-conditional job. No CI job
  runs `ghclient --apply`.
- `.github/workflows/orchestration-tests.yml`: added minimal `permissions:` and
  `concurrency:`.

### Moved (from `bin/`, H7)
- `bin/check_no_attribution.sh` -> `scripts/check_no_attribution.sh`, hardened:
  base-ref selection no longer defaults to a sandbox branch; file coverage widened
  to `*.md *.yaml *.yml *.sh` (incl. workflows). Wired into CI **advisory-first**
  (non-blocking); promotion to a required gate is deferred.

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

`bin/check_no_attribution.sh` was moved and hardened in Area C (see above).
