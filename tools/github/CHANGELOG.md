# Changelog -- tools/github

## Unreleased (Area B)

### Added
- `ghclient secrets publish --profile-set <name> [--env] [--apply]
  [--overwrite|--force] [--delete-missing] [--allow-role ...]`: maps a
  `~/.snowflake/connections.toml` profile onto a GitHub Environment's **secrets**
  (write-only) and **variables** (readable) for the dbt CI layer. Dry-run by
  default (verifies the Environment exists, reads current state, previews the exact
  create/update/delete plan); `--apply` executes only the planned `gh` calls.
  Pure `build_publish_plan()` in `ghclient/secrets.py`; execution through the
  injected `GhRunner`.
- **H8** secret/variable semantics: a *secret*'s preview shows name + existence +
  intended action only (never a value or value-diff); a *variable* may show an
  `old -> new` diff. Explicit `--no-overwrite` (default) / `--force` /
  `--delete-missing` modes.
- **H5** value hygiene: secret values are resolved lazily at apply time and handed
  to `gh` via **stdin** (`GhRunner.run(..., input_text=)`), never on argv, in the
  preview, or in a log line; any `gh` failure has the value scrubbed from stderr
  before it surfaces. Ships an explicit redaction test.
- **H3** least-privilege CI identity (`assert_ci_identity`): refuses an
  OAuth/session profile, a profile with no `role`, `ACCOUNTADMIN` (override only via
  `--allow-role`), a role absent from the publish-set allowlist, and a connection
  whose `user` equals the local OS user (a personal identity, not a CI service
  account).
- Typed `snowflake_secrets` config block (`SecretsCfg`, `PublishSet`, `MappedField`,
  `ExtraItem`, `TargetRef`; enums `ItemKind`/`TargetType`/`ExtraSource`) parsed and
  validated in `config.py` (unknown keys rejected; file/field-scoped errors).
  `config/github-client-config.yml` declares `staging` + `prod` publish sets.
- `ghclient/connections.py`: import-safe `connections.toml` reader (`Profile`,
  `load_profile`) via stdlib `tomllib`, with session-token field detection and
  file/field-scoped `ConfigError`s.
- `ghclient/_paths.py`: shared `quote_segment()` (percent-encodes a REST path
  segment) used by the Environment precheck.
- `wrappers/push-snowflake-secrets.sh` (thin wrapper, dry-run default).
- Tests: `tests/unit/test_secrets.py` (plan derivation, H8/H3/H5 matrix incl.
  redaction), `tests/unit/test_connections.py`, secrets-publish dispatch in
  `tests/integration/test_cli_smoke.py`; fixtures `tests/fixtures/connections.toml`
  and `tests/fixtures/secrets-config.yml` (synthetic -- no real secrets).

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
