I re-reviewed live PR #9 at head `fcf4222`; it is open, now at 5 commits / 57 files, with both `dbt-ci` and `orchestration-tests` failing on the current head.    I treated **Area A** as “scaffold + branch protection” and **Area C** as “`ci reconcile` + CI/doctor + authorship guard,” matching the implementation plan’s own area mapping.

## Highest-priority cross-area issue: A and C currently fight over required checks

The plan correctly says the old required check `test` is a real bug and that the desired required check is the always-emitting `ci-required` aggregate.  The new config also says `aggregate_context: ci-required`.  But the committed branch-protection policy still applies `"contexts": ["test"]`.

That means:

1. `ghclient branch-protection apply --apply` can set the branch back to the known-bad `test`.
2. `ghclient ci reconcile --apply` can then patch required checks to `ci-required`.
3. A later Area A apply can regress Area C again.

This should be fixed before trusting either command.

Concrete improvement: make **one place** authoritative for required checks. I would not keep `required_status_checks` as a static literal in `policy.main.json` when `required_checks_from_workflows: true` is set. Either generate that block from `cfg.ci.aggregate_context` during `plan_apply()`, or make `policy.main.json` intentionally omit/disable status checks and require `ci reconcile` immediately after branch-protection bootstrap. The safer Pythonic design is:

```python
def policy_body_for_apply(cfg: GithubClientConfig, policy: BranchPolicyCfg) -> dict[str, Any]:
    body = load_policy_body(policy.policy_path)

    if policy.required_checks_from_workflows:
        ci = require_ci_cfg(cfg)
        body["required_status_checks"] = {
            "strict": current_or_configured_strict(body, default=True),
            "checks": [{"context": ci.aggregate_context, "app_id": -1}],
            "contexts": [],
        }

    reject_known_bad_contexts(body, forbidden={"test"})
    return body
```

GitHub’s current branch-protection API says `checks` is the more precise mechanism and that `app_id: -1` explicitly allows any app to set the status, while omitting `app_id` asks GitHub to auto-select a recently seen app. ([GitHub Docs][1])

## Area A: branch-protection implementation

### 1. Rollback snapshots are not safely replayable as PUT bodies

`export_snapshot()` stores the raw response from `GET /branches/{branch}/protection`, and `plan_rollback()` later PUTs that stored body back as if it were a valid update payload.   That is likely wrong for real GitHub data: the GET response contains response-only shape such as `url` fields and nested `{enabled: true}` objects, while the update endpoint expects request-body fields such as `enforce_admins: boolean`, `required_status_checks.strict`, `contexts`/`checks`, and `restrictions`. GitHub’s docs show exactly that mismatch between the GET response shape and the update body schema. ([GitHub Docs][1])

Concrete improvement: introduce a normalization layer:

```python
@dataclass(frozen=True)
class ProtectionSnapshot:
    schema_version: int
    repo: str
    branch: str
    captured_at: str
    source: Literal["live", "verified-404"]
    live_response: dict[str, Any] | None
    restore_body: dict[str, Any] | None
```

`export_snapshot()` should store both the raw live response for audit and a computed `restore_body` that conforms to the PUT schema. `plan_rollback()` should only PUT `restore_body`, never the raw GET response. Add a fixture based on `live-protection.json`, but make it realistic: include `enforce_admins: {"enabled": false}` and prove the rollback plan converts it to `enforce_admins: false`. The existing fixture already has GET-shaped fields, but the tests do not currently prove rollback converts them.

### 2. Bare `null` snapshots weaken the “verified 404” invariant

The H1 plan says rollback may DELETE protection only from a `null` snapshot proven to come from a verified 404.  But the implementation writes literal `null` and later treats any file containing literal `null` as `source="verified-404"`.  That means a hand-written `echo null > tools/github/policies/exports/main.json` becomes delete-eligible.

Concrete improvement: replace bare `null` with an envelope:

```json
{
  "schema_version": 1,
  "repo": "dckallos/artwork-db",
  "branch": "main",
  "source": "verified-404",
  "http_status": 404,
  "captured_at": "2026-07-03T23:00:00Z",
  "restore_body": null
}
```

Then `read_snapshot()` should reject bare `null` unless explicitly running a one-time legacy migration. This preserves the good H1 idea but makes the provenance durable.

### 3. Ruleset awareness is implemented as an audit command, not as a mutation guard

The plan says rulesets should be inventoried before any classic-protection mutation, and previews should report ruleset overlap.  The code has `audit()`, `list_rulesets()`, and `get_branch_rules()`, but `run_apply()` does not call `audit()` before rendering or applying the PUT.

Concrete improvement: make `run_apply()` always run a read-only audit first. If branch rules overlap, dry-run should print the warning, and `--apply` should either block or require a very explicit override such as `--allow-ruleset-overlap`.

Also, `get_branch_rules()` should not treat a 404 as “no branch rules.” GitHub documents the branch-rules endpoint as returning all active rules that apply to a branch, and the documented successful status is 200; this endpoint even works for branch names that do not exist. ([GitHub Docs][2]) A 404 here is more likely endpoint/auth/repo ambiguity than “no overlap,” so fail closed.

### 4. Path construction is not future-proof for branch names with `/`

Both classic protection and CI required-check paths interpolate the branch directly into a REST path.   That is fine for `main`, but it contradicts the “one-line config change” claim for future branches like `release/2026.07`. GitHub treats `branch` as a path parameter. ([GitHub Docs][1])

Concrete improvement:

```python
from urllib.parse import quote

def branch_path_segment(branch: str) -> str:
    return quote(branch, safe="")
```

Use it for all branch API paths. Also do not use `f"{branch}.json"` as the snapshot filename for slashed branch names; use a safe slug or a content-addressed filename plus branch metadata inside the snapshot.

### 5. Preflight still checks `jq`, but Area A no longer uses `jq`

`run_preflight()` fails if `jq` is missing.  But snapshots are formatted with Python `json.dumps`, not `jq`.  The README also says `jq` is used for snapshot formatting, which no longer appears true.

Concrete improvement: remove the `jq` preflight check unless some remaining command actually invokes it. Replace it with a higher-value permission check: `gh api repos/{repo}` and require `permissions.admin == true` before allowing mutation. GitHub requires admin/owner permissions to update branch protection and required status checks. ([GitHub Docs][1])

## Area C: CI reconcile and workflow implementation

### 1. The aggregate gate does not actually aggregate `orchestration-tests`

The plan says H2 is a single aggregate gate that depends on path-specific jobs.  The config lists both `.github/workflows/orchestration-tests.yml` and `.github/workflows/ci.yml` as CI workflows.  But the actual `ci-required` job only needs jobs inside `ci.yml`: `changes`, `actionlint`, `shellcheck`, `github-client`, `py-quality`, and `dbt-checks`. It cannot depend on the separate `orchestration-tests.yml` workflow.

That creates a real governance gap: if branch protection requires only `ci-required`, a PR that changes `orchestration/**` can have a failing `orchestration-tests` workflow while the required aggregate does not depend on it. The current head in fact has a failing `orchestration-tests` run.

Concrete improvement: either move the orchestration test job into the always-running `ci.yml` and make it path-conditional like `dbt-checks`, or accept that `orchestration-tests` remains a separate required check and solve its path-filter deadlock another way. The cleanest fix is to fold orchestration into `ci.yml`:

```yaml
jobs:
  changes:
    outputs:
      dbt: ${{ steps.filter.outputs.dbt }}
      orchestration: ${{ steps.filter.outputs.orchestration }}

  orchestration-tests:
    needs: changes
    if: needs.changes.outputs.orchestration == 'true'
    ...

  ci-required:
    needs: [changes, actionlint, shellcheck, github-client, py-quality, dbt-checks, orchestration-tests]
    if: always()
```

Then `ci-required` really means “all relevant gates passed or were legitimately skipped.”

### 2. `ci.py` overstates what parsed workflows “feed” into the aggregate

`ReconcilePlan.workflow_contexts` is documented as the list of path-job contexts that feed the aggregate.  But `build_reconcile_plan()` collects contexts from every configured workflow file, including `orchestration-tests.yml`, even though those jobs do not feed `ci-required`.

Concrete improvement: change the data model from “all workflows” to explicit roles:

```yaml
ci:
  aggregate:
    workflow: .github/workflows/ci.yml
    job: ci-required
  informational_workflows:
    - .github/workflows/orchestration-tests.yml
```

Or, better, after folding orchestration into `ci.yml`, make `ci.workflows` contain only the workflow that actually emits the aggregate. The preview should never imply that an external workflow is part of the gate unless the implementation actually makes it so.

### 3. `ci reconcile` validates that `ci-required` exists, but not that it is always emitted

The code validates that the aggregate context is a job in one configured workflow.  That is necessary but insufficient. A workflow can contain a `ci-required` job and still be skipped at the workflow level via top-level `paths`, `branches`, or commit-message filters. GitHub explicitly documents that if a workflow is skipped due to branch/path filtering, checks associated with it can remain Pending and block merges. ([GitHub Docs][3])

Concrete improvement: add workflow-level validation for the aggregate workflow:

* `on.pull_request` exists.
* `on.pull_request.paths` and `paths-ignore` are absent.
* branch filters are absent unless intentionally allowed.
* aggregate job has `if: always()`.
* aggregate job’s `needs` includes every intended gate.
* aggregate job treats `failure` and `cancelled` as failures.

One implementation detail: PyYAML’s default loader has historically parsed unquoted `on` as a boolean under YAML 1.1 behavior, so use a loader strategy that preserves GitHub Actions keys accurately before adding this validation. The current parser only looks at `jobs`, so it avoids the issue by accident.

### 4. Preserve or explicitly set `strict` when patching required checks

`_get_current_contexts()` discards `strict`, and `_apply_plan()` sends only `{"checks": [{"context": ...}]}`.   GitHub’s update-status-check-protection endpoint supports `strict`, `contexts`, and `checks`; it also says updating required status checks requires branch protection to be enabled. ([GitHub Docs][1])

Concrete improvement: parse and carry `strict` in `ReconcilePlan`, then PATCH with it:

```python
@dataclass(frozen=True)
class RequiredChecksState:
    strict: bool
    checks: tuple[RequiredCheck, ...]

body = {
    "strict": plan.strict,
    "checks": [{"context": ctx, "app_id": -1} for ctx in plan.desired_contexts],
    "contexts": [],
}
```

This makes the preview exact and prevents accidental drift if GitHub interprets omitted fields differently than expected.

### 5. The current CI failures point to useful hardening work, not just flaky CI

For `dbt-ci` on this head, GitHub reports `shellcheck`, `dbt-checks`, and `ci-required` failed; `authorship-guard` also failed but is meant to be advisory.  That is useful signal:

* `shellcheck` should be fixed before merge because Area C explicitly adds shellcheck as a gate.
* `authorship-guard` is advisory-first, but it currently scans `*.md`, `*.yaml`, `*.yml`, and `*.sh`, which will catch deliberate review/documentation references unless those lines use `authorship-marker-ok`.
* `ci-required` correctly fails when one of its required dependencies fails; that part of the aggregate logic is doing its job.

Concrete improvement for the authorship guard: keep the widened file coverage, but separate “automated attribution footer/header” from “docs that discuss tools.” For example, make `*.md` scanning focus on structural locations: first/last N lines, trailers, or exact footer/header patterns. Alternatively, add explicit allow tokens to known historical review docs, but that is more brittle.

### 6. Pin or vendor the actionlint installer

The `actionlint` job currently executes a live script from `raw.githubusercontent.com`.  That is convenient, but it is a supply-chain smell inside a governance gate.

Concrete improvement: pin an actionlint release and checksum, or use a pinned action SHA. A minimal shell version:

```bash
version="1.7.7"
sha256="..."
curl -fsSLo actionlint.tar.gz \
  "https://github.com/rhysd/actionlint/releases/download/v${version}/actionlint_${version}_linux_amd64.tar.gz"
echo "$sha256  actionlint.tar.gz" | sha256sum -c -
tar -xzf actionlint.tar.gz actionlint
./actionlint -color
```

### 7. Add tests that lock the actual governance contract

The Area C tests are good for pure derivation, matrix expansion, dry-run, and patch/no-patch behavior.  They should add tests for the higher-level contract that can currently regress:

* `policy.main.json` must not contain `"test"` when `required_checks_from_workflows: true`.
* `branch-protection apply` must not regress required checks away from `cfg.ci.aggregate_context`.
* `ci-required` workflow has no top-level path filter.
* `ci-required` job uses `if: always()`.
* every intended gate appears in `ci-required.needs`.
* no workflow contains `ghclient ... --apply`.
* a GET-shaped branch-protection snapshot normalizes to a PUT-shaped restore body.

Those tests are all deterministic and credential-free.

## Documentation and implementation Markdown conflicts

The implementation plan still starts with “No code written yet,” even though Area A and Area C are implemented in this PR.  The plan also says the CLI entrypoint is `argparse/click`, while the decision brief says Typer and the implementation uses Typer.

The `tools/github/README.md` is stale too: it still says Area C is deferred/stub-only and advertises `ghclient audit export`, but the CLI exposes a top-level `audit` command and now has `ci reconcile`.

Concrete improvement: add a small “Implementation status” table near the top of `docs/github_client_and_readmes_plan.md`:

```md
| Area | Status in PR #9 | Current commands | Known follow-ups |
| --- | --- | --- | --- |
| A | Implemented, needs hardening | `ghclient branch-protection ...`, `ghclient audit` | snapshot envelope, rollback normalization, policy/CI check unification |
| C | Implemented, needs hardening | `ghclient ci reconcile`, `scripts/check_no_attribution.sh`, `ci-required` | fold orchestration into aggregate, workflow-level validation, update README |
```

That would make the Markdown file useful to Claude instead of mixing target-state, historical decisions, and current implementation state.

[1]: https://docs.github.com/en/rest/branches/branch-protection?apiVersion=2022-11-28 "REST API endpoints for protected branches - GitHub Docs"
[2]: https://docs.github.com/en/rest/repos/rules?apiVersion=2022-11-28 "REST API endpoints for rules - GitHub Docs"
[3]: https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions "Workflow syntax for GitHub Actions - GitHub Docs"
