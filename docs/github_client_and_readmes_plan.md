# Master Optimization & Implementation Plan — artwork-db

**Status:** DRAFT (Stage 2, iteration 1). Areas A, B, and C have repository-local
implementation on this branch and are under review; this remains the planning and
review artifact for the broader optimization effort: GitHub client,
per-folder READMEs, Dagster/orchestration enrichment UX, and dbt hardening. It is the
review artifact; we iterate on it until it is explicitly approved, then implement in the
sliced sequence at the end.

**Documentation depth vs delivery order are decoupled.** Every phase below — including the
Dagster/orchestration and dbt work — is specified to the same granular, decision-capturing
depth so that no design choice is lost, *regardless* of when it ships. Delivery is
sequenced (§10); documentation is complete for all phases.

**Branch:** `feat/optimize-dagster-options`
**Repo:** `dckallos/artwork-db` (private) — confirmed via `git-setup/README.md:80`.

---

## 0. How to read this document

Priority order (agreed):

1. **Phase 1 — GitHub client module** (`tools/github/`): branch protection, publishing
   Snowflake connection values to GitHub Environment secrets for the dbt layer, and
   CI reconcile/optimization. Config-decoupled via `github-client-config.yml`.
2. **Phase 2 — READMEs per major folder.**
3. **Phase 3 (later) — Enrichment UX** (custom-N = YAML/env only).
4. **Phase 4 (later) — dbt hardening** (`int_` layer, source-decoupled marts,
   dev→staging→prod targets/isolation, promotion CI).

Phases 3–4 are **fully specified** here (§5A Dagster, §5B dbt) with file:line evidence,
options-with-tradeoffs, and locked decisions — they are simply sequenced **after** Phases
1–2 in delivery (§10). "Later" means later to *build*, not lightly *planned*.

### 0.1 Decision conventions (how questions are posed)

**Rule (binding for this document):** every design decision is written up *before* it is
asked about — the choice being made, the realistic options, their tradeoffs, and a
recommendation — in **both technical and plain-language (layman's) terms**. No abbreviated
question/answer chips without that background living here first. The decision briefs are in
**§12**; the interactive question tool only *confirms* a choice already explained here. If a
new decision surfaces mid-work, its brief is added here before it is acted on.

---

## 1. Goals and non-goals

### Goals

- A **decoupled, reusable GitHub client** that removes manual `gh api` invocations for the
  workflows this repo uses often. Repo-specific facts live in **config**, not code.
- **Branch protection** as version-controlled desired-state with dry-run, export
  (before-state), and rollback — preserving the good pattern already in `bin/`.
- **"Update Snowflake instance"**: publish selected fields from a
  `~/.snowflake/connections.toml` profile into **GitHub Environment secrets** consumed by
  the dbt layer (`SNOWFLAKE_*` / `DBT_SNOWFLAKE_*`), field-mapped in config. Kept **open to
  expansion** (repo/org targets, more fields, PAT bridge) without a redesign.
- **CI optimization**: reconcile required status checks against a single always-emitting
  aggregate gate (`ci-required`, H2) rather than path-filtered job names; add
  caching + concurrency-cancel; install the AI-authorship guard as a gate; validate
  workflows.
- **Consistent READMEs** for every major directory, from one template.
- Everything **typed, unit-tested, dry-runnable, and secret-safe** (never print secret
  values).

### Non-goals

- Not reimplementing `gh` auth — the client **shells out to `gh`** (v2.94 present) so it
  inherits `gh auth`.
- Not managing org-wide policy or multiple repos in the first slice (config is shaped to
  allow it later).
- Not touching the orchestration framework `.py` grep gate (that constraint is scoped to
  `orchestration/artwork_orchestration/**`; this module is unrelated to it).
- Not implementing Phases 3–4 in this slice.
- Not committing anything until explicitly asked; never committing secrets.

---

## 2. Current-state findings (with evidence)

### 2.1 The `bin/` uploads are mis-targeted and repo-coupled

- All three scripts hardcode a **different repo**: `REPO="dckallos/dbt-diagnostics"`
  (`bin/apply-branch-protection.sh:24`, `bin/export-branch-protection.sh:18`,
  `bin/rollback-branch-protection.sh:21`) and `BRANCHES="donkey-kong-sandbox main"`.
  This repo is `dckallos/artwork-db`. The scripts also self-describe paths as
  `scripts/governance/...` in their help text, i.e. they came from another layout.
- The **mechanism is sound** and worth preserving:
  - `PUT repos/<repo>/branches/<b>/protection` from `policy.<branch>.json` (desired state),
    idempotent (`apply-branch-protection.sh:56-62`).
  - Auto-export current live config to `exports/<branch>.json` before applying
    (`apply-branch-protection.sh:53-54`), so there is always a before-state.
  - `null`-aware rollback: delete protection if the branch was unprotected at snapshot
    time, else restore (`rollback-branch-protection.sh:43-64`).
  - `--dry-run` prints target + body and changes nothing.
- `bin/policy.main.json` requires check `test` (`strict:true`), linear history, no
  force-push/deletion, PR required (`required_approving_review_count:0`),
  `enforce_admins:false`, `restrictions:null`.

### 2.2 Required-check name mismatch (a real bug to fix via the client)

- Branch protection requires a status check literally named **`test`**
  (`bin/policy.main.json:4`).
- Actual workflows produce different check names: `orchestration-tests.yml` (job `pytest`)
  and `ci.yml` (`name: dbt-ci`, job `checks`). GitHub reports checks by
  `workflow`/`job`, so **no check named `test` is ever emitted** → a strict required check
  can block merges indefinitely. **Fix (H2, refines the original "set contexts from job
  names"):** the client's **`ci reconcile`** requires the single always-emitting aggregate
  context **`ci-required`** (which depends on the path-specific jobs), not the raw
  `workflow`/`job` names — so path-filtered workflows never leave a required check pending.

### 2.3 Connection profile shape and the CI-credential caveat

- `~/.snowflake/connections.toml` `[default]` profile: `account`, `user`,
  `authenticator = "oauth"`, `token_file_path = "/snowflake/session/token"`, `host`,
  `role = "ACCOUNTADMIN"`.
- **Caveat:** this profile is **OAuth/session** — not usable as a CI credential. CI
  (`ci.yml:30-37`) needs **key-pair** secrets (`DBT_SNOWFLAKE_USER`,
  `DBT_SNOWFLAKE_PRIVATE_KEY`, `DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, `SNOWFLAKE_ACCOUNT`).
- Therefore "publish a profile → GitHub secrets" must be a **declarative field mapping**
  (which TOML keys → which secret names), and must support a value that **does not live in
  the TOML** (the private key, read `from_file`). We publish only what maps cleanly; we
  never invent credentials.

### 2.4 dbt layer secret names (the publish target for now)

- `ci.yml` consumes: `SNOWFLAKE_ACCOUNT`, `DBT_SNOWFLAKE_USER`,
  `DBT_SNOWFLAKE_PRIVATE_KEY`, `DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, and env
  `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE`, `DBT_SNOWFLAKE_ROLE`
  (`ci.yml:30-37`). `profiles.yml` dev target reads the same via `env_var()`.
- **Decision:** the first slice publishes **only these dbt-layer secrets**, to **GitHub
  Environment** secrets; documented as **open to expansion**.

### 2.5 Snowflake↔GitHub bridge already exists (relevant to the PAT-bridge idea)

- `git-setup/` creates a Snowflake SECRET `github_pat_artwork_db` from a PAT in gitignored
  `git-setup/.env` (`git-setup/README.md:55`, `.env.example:6`). Rotation today =
  edit `.env`, re-run `make iac`. A future client command could rotate the GitHub PAT and
  update this Snowflake SECRET together (noted, not in first slice).

### 2.6 Environment / hand-off facts (confirmed)

- `orchestration/pyproject.toml` **exists** (confirmed) — CI editable-installs
  `orchestration[dev]` (`orchestration-tests.yml:44`) and dev runs
  `dagster dev -m artwork_orchestration.definitions` (`run_dagster_dev.sh:54`) from
  `.venv`. So **dev loads your working tree via the editable install**; edits are live on
  reload.
- Both dbt sources hardcode `database: ARTWORK_DB`, `schema: BRONZE`
  (`_met__sources.yml:12-13`, `_aic__sources.yml:15-16`) → dev/staging/prod share one
  Bronze; env isolation is Phase 4 work.

### 2.7 `gh` and tooling availability

- `gh` v2.94.0 at `/usr/local/bin/gh`; `jq` present at `/usr/sbin/jq` (used by the existing
  export script). The client will **preflight** `gh auth status` and required scopes before
  mutating anything.
- `scripts/ci/ci_local.sh` exists (invoked by `ci.yml:57`); the `Makefile` already injects
  `GITHUB_PAT`/`GITHUB_OAUTH_CLIENT_ID`/`GITHUB_OAUTH_CLIENT_SECRET` from `.env`
  (`Makefile:60-69`) for the Snowflake-side git-setup — the client should not duplicate that
  PAT flow, only bridge to it if/when the PAT-rotation command is pulled in.

---

## 3. Naming decision

`gh-cli-config.yml` is retired: `gh` collides with the distinct `gh` tool, and `cli` is
overloaded. The client config is **`config/github-client-config.yml`** (a repo-root `config/`
dir — DECIDED 2026-07, resolves the earlier §3-vs-§11-vs-§4.1 conflict; consistent with §11/§12.1).
Alternatives considered: repo root (discoverable but clutters root) and `tools/github/config.yml`
(co-located but less discoverable) — both rejected; a top-level `config/` dir signals "this
configures repo governance" while keeping the root clean.

---

## 4. Proposed design — the GitHub client module

### 4.1 Shape (agreed: Python core + CLI + shell wrappers)

```
config/
  github-client-config.yml           # DECIDED (§3): repo-root config/ dir
tools/github/
  README.md
  pyproject.toml                     # DECIDED (§11): standalone package
  ghclient/                          # Python package (importable, typed, tested)
    __init__.py
    config.py        # load + validate github-client-config.yml -> typed dataclasses
    gh.py            # GhRunner: thin, injectable wrapper around `gh` (subprocess seam)
    connections.py   # read ~/.snowflake/connections.toml -> typed Profile
    branch_protection.py   # apply / export / rollback (desired-state, dry-run)
    secrets.py       # publish mapped profile fields -> GitHub Environment secrets
    ci.py            # reconcile required checks; workflow lint/caching helpers
    cli.py           # argparse/click entrypoint: `ghclient <verb> ...`
    errors.py        # ConfigError etc. (file/field-scoped, like the loader)
  wrappers/          # thin bash scripts for frequent workflows (no arg memorization)
    protect.sh       # -> ghclient branch-protection apply
    rollback.sh      # -> ghclient branch-protection rollback
    push-snowflake-secrets.sh  # -> ghclient secrets publish --env <env>
    reconcile-ci.sh  # -> ghclient ci reconcile
  policies/
    policy.main.json
    policy.<sandbox>.json
    exports/         # generated before-state snapshots (gitignored — DECIDED §12.2.3)
  tests/
    unit/ integration/ conftest.py fixtures/
```

Design principles (mirroring `CODE_STANDARDS.md`):

- **`GhRunner` is the single seam** to `gh` (one place builds subprocess argv; injectable so
  tests stub it — no live GitHub). Analogous to `orchestration/_runner.py`.
- **Config → frozen dataclasses**, validated once with **file/field-scoped errors**
  (`errors.ConfigError`), unknown keys rejected — same discipline as `loader.py`.
- **Pure functions of config** produce the `gh` command plans; execution is a separate,
  dry-runnable step (every verb supports `--dry-run` that prints the plan).
- **Secret-safe:** values are passed to `gh secret set` via stdin/file, never logged; the
  client prints secret *names* and *targets* only.
- **House docstring style** applies to all new `.py` (triple quotes on their own lines);
  run `scripts/normalize_docstrings.py --check`.

### 4.2 `github-client-config.yml` schema (illustrative)

```yaml
repo: dckallos/artwork-db

branch_protection:
  branches:
    main:
      policy: policies/policy.main.json
      required_checks_from_workflows: true    # H2: reconcile to the aggregate `ci-required` context, not raw job names
    # Model A (§12.2.6): v1 protects `main` only. Add more protected branches here as one-line entries when needed.

snowflake_secrets:
  source: ~/.snowflake/connections.toml
  profiles:
    prod:                                     # a named publish set
      profile: default                        # which connections.toml profile
      target: { type: environment, name: prod }   # environment | (later) repo | org
      map:                                    # TOML field -> GitHub secret/variable
        account: { secret: SNOWFLAKE_ACCOUNT }
        user:    { secret: DBT_SNOWFLAKE_USER }
        role:    { variable: DBT_SNOWFLAKE_ROLE }
      extra:                                  # values NOT in the TOML
        DBT_SNOWFLAKE_PRIVATE_KEY: { from_file: "~/.snowflake/keys/prod.p8" }
        DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE: { prompt: true }

ci:
  workflows: [.github/workflows/orchestration-tests.yml, .github/workflows/ci.yml]
  required_checks: auto        # or explicit list
```

Open to expansion: additional `target.type` values, multiple repos, label/ruleset/env
protection-rule blocks — all additive.

### 4.3 Capability set (v1 vs brainstorm menu)

**v1 (first slice):**
- `branch-protection apply|export|rollback [--dry-run] [--branch]` — port of `bin/`,
  repo/branches/policy from config.
- `secrets publish --profile-set <name> [--dry-run] [--no-overwrite|--force] [--delete-missing]`
  — map connections.toml → GitHub Environment secrets/variables for the dbt layer (H8: Secrets
  show name/existence/intended action only, never a value diff; Variables may value-diff).
- `ci reconcile [--dry-run]` — set the required check to the always-emitting aggregate
  `ci-required` context (H2), not path-filtered job names.
- `preflight` — verify `gh auth status`, scopes, `jq`, config validity.
- `audit export` — snapshot current live settings to versioned JSON; **inventories BOTH classic
  branch protection AND active repo/org rulesets** (H9) and reports ruleset overlap (v1 mutates
  classic only).

**Brainstorm menu (documented; pull into later slices on request):**
- GitHub Environments + approval gates (dev/staging/prod) — enables Phase 4 promotion.
- Repo settings hygiene (squash-only merge to match linear history; auto-delete head
  branches; default branch).
- Rulesets (modern replacement for classic protection).
- PAT rotation bridge (GitHub PAT + Snowflake `github_pat_artwork_db` SECRET).
- Workflow linting (actionlint), pip caching, `concurrency:` cancel groups.
- Install `scripts/check_no_attribution.sh` as a **pre-commit hook + advisory** CI check first,
  promoting to a required gate only after the H7 hardening (§12.2.9 / §7).
- Multi-repo fan-out (config lists repos).
- Labels / PR & issue templates / CODEOWNERS validation.

### 4.4 Config-vs-code boundary

- **Config (`github-client-config.yml` + `policies/*.json`)**: repo name, branches, policy
  bodies, secret field mappings, environment names, CI workflow list. Changing *what* is
  governed is config-only.
- **Code (`ghclient/`)**: the *mechanism* — how a plan is built and executed, validation,
  secret-safe transport, dry-run rendering. Adding a *new capability* (e.g. rulesets) is
  code + a new config block.
- **Wrappers (`wrappers/*.sh`)**: fixed, memorized-workflow shortcuts; no logic beyond
  calling the CLI with your common args.

---

## 5. READMEs per major folder (Phase 2)

### 5.1 "Major directory" definition (proposed, to iterate)

> A **major directory** represents a distinct, independently-reasoned concern with its own
> entrypoints/config/lifecycle — a layer or deployable unit — as opposed to a leaf, utility,
> generated, or purely-nested-implementation directory.

**Needs a README (new), reconciled against the actual tree (2026-07 audit):**
- *Orchestration:* `orchestration/` (only `PRODUCTION.md` today),
  `orchestration/artwork_orchestration/` (has `SCHEMA.md` + `ADDING_A_SOURCE.md`),
  `orchestration/tests/`.
- *dbt:* `artwork_pipeline/models/staging/`, `artwork_pipeline/models/marts/`,
  `artwork_pipeline/macros/`, `artwork_pipeline/tests/`.
- *Extraction:* `extraction/` (top). `extraction/cma/` is being **removed** (§12.4.5); `aic`/`met`
  already have READMEs.
- *Platform:* `infrastructure/`, `operations/`, `analysis/`, `scripts/` (top), `scripts/ci/`,
  `scripts/sql/`.
- *Meta:* `docs/` (index), `.github/`, `tools/github/` (new — created with the client).

**Deltas from the iteration-1 list (now corrected):** added `orchestration/` (top),
`artwork_pipeline/macros/`, `artwork_pipeline/tests/`, `scripts/ci/`, `scripts/sql/`; dropped
`extraction/cma/` (cma removal); confirmed `models/staging|marts/` paths.

**Excluded (generated/leaf/archive):** `target/`, `dbt_packages/`, `__pycache__/`,
`orchestration/dagster_home/`, and the frozen archive `docs/bin/repo-cleanup-*/`.

**Already present (audit, don't clobber):** `artwork_pipeline/README.md`, `bin/README.md`
(retired, §12.2.9), `extraction/aic/README.md`, `extraction/met/README.md`,
`git-setup/README.md`, `scripts/orchestration/README.md`.
(`artwork_pipeline/models/staging/cma/README.md` is removed with cma.)

**DECIDED (depth):** **concise, template-sized (~15–25 lines)** per README — skimmable and
low-maintenance, not narrative.
**DECIDED (docs/ archive):** the `docs/` README **indexes current/curated docs and explicitly
marks `docs/bin/repo-cleanup-*` as a frozen archive** (linked, not maintained); `docs/context/*`
playbooks are indexed as reference.

### 5.2 README template (uniform, concise)

Purpose (1–2 lines) · Where it fits (layer + upstream/downstream) · Layout (key files) ·
How to run / entrypoints · Config it reads · **Related** (repo-relative cross-links to the
dirs/docs it hands off to/from) · Conventions/links (to `AGENTS.md`, `CODE_STANDARDS.md`,
`SCHEMA.md`) · Gotchas.

Every README carries a **Related** line so the doc set forms a navigable graph (orchestration ↔
artwork_pipeline ↔ extraction; `.github` ↔ scripts/ci ↔ tools/github); the top-level `docs/`
README holds the full link map. Worked sample: `orchestration/artwork_orchestration/README.md`
(drafted in review — persist when generating).

**Current-state only (H6):** every README describes **what exists today**; anything not yet built
is labelled `planned (§X)`, never written as operational fact (e.g. the Phase-3 refresh **sensor**
is planned, not current). Applies when Area D is implemented.

---

## 5A. Phase 3 — Enrichment UX optimization (Dagster/orchestration)

Goal: give the operator first-class control over Met enrichment — **enrich all**, a
**custom N**, and **beyond-departments** slicing — without breaking the prime directive
(no source identifiers in framework `.py`; grep gate `\b(met|aic|cma)\b|…` stays 0) or the
"config is data in YAML" rule.

### 5A.1 Current-state findings (evidence)

- **Why a department is forced (UI):** the enrichment step is statically partitioned by
  department. `sources/met.yaml:38-60` declares `partition_by {name: department, cli_flag:
  --department, values:{…19…}}`; `spec.py:46-47` builds `StaticPartitionsDefinition(
  partition_keys())`; `factories/assets.py:107` sets it on the asset; `assets.py:49-51`
  *requires* `context.partition_key`, and `:56-57` appends `--department <value>`. A
  statically-partitioned asset cannot be materialized in the UI without picking a key.
- **The CLI already supports "all" and "N":** `run.py` `enrich-met` defaults `--department`
  to `None` = all (`run.py:165-169, 204-209`); `control_enricher.enrich_from_control(
  department=None)` drains the **whole** worklist; `--limit` is a one-batch smoke bound
  (`run.py:151-154, 198-201`). So the capability exists; only the Dagster partition hides it.
- **The per-run limit:** ceiling = `BATCH_SIZE × MAX_BATCHES`. Defaults `2000 × 1`
  (`framework.yaml:46-47`) → `policies.py:46-47` → appended in `assets.py:58-62`. Rate:
  `per_worker_rps = rps_budget/concurrency` = `30/3 = 10` (`model.py:146-147`,
  `framework.yaml:49-50`), injected at `assets.py:66`.
- **Eligibility truth lives in Bronze:** `MET_WORKLIST` (eligible+unprocessed) + 
  `MET_ENRICHMENT_CONTROL` (status + lease), seeded by the `seed-control` CLI from
  `MET_CSV_SNAPSHOT` (`run.py:130-145`). `met.yaml` SQL is **display-only** counters
  (`:64-71, 80-82`); eligibility is **not** defined in YAML or dbt today.
- **Jobs/schedules:** `{key}_enrich_next_batch_job` and `hourly_{key}_enrich_batch` exist
  **only** when `enrich_step()` returns non-None, and that requires *both* `rate_limited` and
  a partition (`spec.py:162-170`, `factories/jobs.py:87-103`, `factories/schedules.py:38`).
  Enrichment is deliberately excluded from `ingest_all`/`full_pipeline` (`jobs.py:14-21`).
- **Concurrency-cap gap (safety):** `jobs.py:14-21` relies on a single-valued
  `artwork/rate_limited_api` run tag for per-museum capping, but the seeded
  `dagster_home/dagster.yaml.example` has `max_concurrent_runs:2` and **no
  `tag_concurrency_limits` block** — so the cap the docs describe (`ADDING_A_SOURCE.md:32-34`)
  is not actually enforced by the seeded instance. Must be fixed before raising volume.

### 5A.2 Design — the three controls

**(a) Enrich all / beyond departments — Option D (config-declared dynamic partitions), your
pick.** The partition *dimension name* + `cli_flag` stay in `sources/met.yaml` (as now), but
the partition **values are discovered from the worklist** instead of the hand-listed 19
departments. `met.yaml` would declare, e.g.:

```yaml
partition_by:
  name: department
  cli_flag: --department
  from_worklist:                 # NEW: values come from a query, not a literal map
    query: "SELECT DISTINCT department FROM {db}.{schema}.MET_WORKLIST"
  include_all: true              # SUPERSEDED by §12.3.4 (the `all` sentinel is dropped; a separate unpartitioned drain job replaces it)
```

Framework changes (generic, source-agnostic, grep-safe):
- A new `PartitionDim` variant sourcing keys from a Snowflake query result (reuses
  `_snowflake.sf_scalars`/a list query) → `DynamicPartitionsDefinition` instead of
  `StaticPartitionsDefinition` (`spec.py:46-47`).
- Slug↔value mapping for Dagster-legal partition keys (Dagster forbids some chars).
- A sentinel `all` key whose `value_for` returns `""` so `assets.py:56-57` **omits**
  `--department` → the CLI drains the whole worklist (already supported, §5A.1).
  **SUPERSEDED by §12.3.4:** no `all` partition key; whole-worklist drain lives in a separate
  unpartitioned enrich-all/drain job (§12.3.5 budget applies).
- **Zero museum literals in `.py`** — departments/culture/medium remain in `met.yaml`.

**(b) Custom N — YAML/env only (your decision). — SUPERSEDED by §12.3.5 (DECIDED (a)):** a typed
per-run launchpad override, YAML-bounded, plus an explicit `all_remaining` drain mode with a
safety budget now exists; YAML owns the *ceilings*, the launchpad chooses within them. The
"no per-run launchpad knob" statement below is retained only as history. Operators set
`BATCH_SIZE` / `MAX_BATCHES` via env or `framework.yaml:46-47` before launch; `MAX_BATCHES`
high = "drain to empty" (loop stops at `claimed==0`, `control_enricher`). No code change
needed for the knob itself; we only **document** it and surface both values in asset
metadata (already done, `assets.py:83-85`).

**(c) Refresh mechanism — DECIDED in §12.3.1 (sensor + manual op).** How the dynamic partition set
is discovered/kept current is no longer deferred; see §12.3.1/§12.3.7. (Original "deferred" text
retained below as history.)
Tradeoffs to weigh: at-load is simplest but needs a reload to update *and* would add a
Snowflake query at import time (tension with the "no import-time side effects" rule,
`CODE_STANDARDS §3`); a sensor is live but adds a moving part; a manual `refresh-partitions`
op is explicit but requires operator action. Decision captured in §12.

### 5A.3 Eligibility/worklist ownership (options, tradeoffs)

| Owner | Pro | Con |
|---|---|---|
| **Keep CLI-owned `MET_WORKLIST`+control (today)** | leasing/resumability already built | truth split across 2 tables + CLI; opaque to dbt; dynamic-partition query reads it directly |
| **Expose worklist as a dbt view** (`stg_met__worklist`) | declarative, testable, lineage | dbt can't own leasing; claim table still needed; adds a dbt dep to partition discovery |
| **Bronze query at materialization** | no new object | recomputes each run; racey without the lease |

**DECIDED (§12.3.2 (a)):** **keep the control table for leasing**, and have Option D's discovery
query read `MET_WORKLIST` directly (smallest blast radius; the display counters at
`met.yaml:64-66,82` already query it).

### 5A.4 Config-vs-code boundary (this phase)

> **Updated per §12.3.4/§12.3.5:** the `include_all` sentinel is dropped (whole-worklist drain is a
> separate **unpartitioned job**, not a partition key), and the **per-run launchpad override**
> (`BATCH_SIZE`/`MAX_BATCHES` at launch time) is **net-new typed framework `.py` + new `framework.yaml`
> knobs + loader validation** — *not* zero-code. The bullets below describe the pre-§12.3 boundary.

- **YAML-only, zero code:** `rps_budget`/`concurrency`,
  retries/timeouts, which steps are partitioned/rate-limited/batched, the department list,
  metadata counters, freshness, checks. (`BATCH_SIZE`/`MAX_BATCHES` *defaults* remain YAML, but the
  overridable-at-launch behavior is new code — see the note above.)
- **Needs generic framework `.py` (grep-safe):** the `from_worklist` partition mechanics (a) above;
  the unpartitioned drain job + typed per-run run-config (§12.3.4/§12.3.5). The
  `tag_concurrency_limits` fix (§5A.1) is `dagster.yaml` config, not `.py`.

---

## 5B. Phase 4 — dbt hardening

Goal: make the medallion project source-decoupled and promotable dev→staging→prod. The
project is real and competent (staging for `met`/`aic`; marts `dim_artists`, `dim_artworks`,
`fct_artwork_images`, `openaccess_catalog`); this is hardening, not a rebuild.

### 5B.1 Current-state findings (evidence)

- **Marts hardcode each source** as `UNION ALL` branches with literal `source_system`
  (`dim_artists.sql:25,44`; `dim_artworks.sql:44,75`; `fct_artwork_images.sql:42,61`) and
  repeat `accepted_values:['met_museum','art_institute_chicago']` per mart. Adding a source =
  hand-editing every mart — the "add a source = one YAML" promise stops at dbt.
- **No intermediate (`int_`) layer**; staging feeds marts directly, so union/conform logic is
  duplicated across marts.
- **Sources hardcode `ARTWORK_DB.BRONZE`** (`_met__sources.yml:12-13`, `_aic__sources.yml:15-16`)
  → dev/staging/prod all read the same Bronze; no read-side isolation.
- **Only two targets exist** — `dev` + `snowflake` (`profiles.yml:38-51`); **no `staging`/`prod`.**
  `generate_schema_name.sql:64` routes `target.name in ['prod','snowflake']` to verbatim
  `SILVER`/`GOLD`, else a dev prefix — but with no `prod` target the branch is unreachable and
  a `staging` target would silently get a dev prefix. Isolation is schema-only; the **database
  is constant** (`ARTWORK_DB`). `override_create_schema.sql` no-ops schema creation (RBAC).
- **Naming smells:** profile is personal (`dbt_daniel`), dev schema hardcoded `DBT_DKALLEWARD`,
  machine-specific `private_key_path` committed; `openaccess_catalog` breaks the `dim_`/`fct_`
  prefix convention; `cma` staging is a `README` stub only (asymmetric with `cma.yaml`).
- **Cosmetic:** `fct_artwork_images` `cluster_by=['source_system']` is a self-described no-op
  at <1M rows (`fct_artwork_images.sql:19`).

### 5B.2 Design (options + leanings)

- **Source-decoupled marts:** introduce an `int_` layer (`int_artists__unioned`,
  `int_artworks__unioned`, `int_images__unioned`). **DECIDED (§12.4.6):** each source is first
  **conformed** (`int_<src>__<entity>_conformed`, a per-source tested contract) and the union runs
  over the *conformed* models, driven by the `enabled_sources` dbt `var` (§12.4.3); a new source is
  one var entry + its `stg_`/conformed models, not edits to every mart. Marts then `ref()` the
  unioned `int_` model.
- **dev→staging→prod:** add explicit `staging` + `prod` targets. **DECIDED (§12.4.1, reversed
  2026-07):** isolation is **schema-based in one DB `ARTWORK_DB`** via `generate_schema_name_for_env`
  (not separate databases); **DECIDED (§12.4.2):** Bronze is the **shared `ARTWORK_DB.BRONZE`** with a
  `bronze_db` `var` override seam — each env reads the same Bronze and writes env-routed schemas.
- **Promotion CI:** a credentialed `dbt build` against **staging** on merge to the integration
  branch and **prod** on release/tag; gate prod behind a GitHub **Environment** (Phase 1 client
  publishes those Environment secrets — the two phases meet here).
- **Naming fixes:** keep profile `dbt_daniel` (rename to `artwork_pipeline` reversed 2026-07);
  move per-dev schema + key path to env; rename `openaccess_catalog` → `obt_openaccess_catalog`
  (§12.4.5); **DECIDED: remove the `cma`
  stub** everywhere (re-add Cleveland as one clean onboarding when built).

### 5B.3 Config-vs-code boundary (this phase)

All dbt-side: `profiles.yml` targets, `dbt_project.yml` vars/materializations, the union
macro, `generate_schema_name.sql` `allowed_schemas`, and CI workflow YAML. No orchestration
framework `.py` change except possibly `framework.yaml connection.target` docs for prod.

---


## 6. Environment / deployment and Dagster↔GitHub hand-off

- Reality: dev = editable install of `orchestration[dev]` in `.venv`, run via
  `dagster dev -m …` (`run_dagster_dev.sh:54`); working-tree edits live on reload.
  Schedules ship **STOPPED** (`factories/schedules.py:9`).
- Options for a clean hand-off (documented; not built in slice 1):
  - Keep dev on the working tree; stand up a **separate prod code location** that installs a
    pinned tag/branch and sets `DBT_TARGET=prod`, enabling schedules there.
  - The GitHub client manages the **Environment secrets** those hosts consume, aligning the
    GitHub side of dev→staging→prod with the dbt side (Phase 4).

---

## 7. CI enhancement plan

- **`orchestration-tests.yml`** (offline, solid): add `python -m py_compile` gate,
  `scripts/normalize_docstrings.py --check`, an offline `doctor_orchestration.sh` run, pip
  caching, and `concurrency: { group: …, cancel-in-progress: true }`.
- **CI-wide hardening (H4):** add **actionlint** + **shellcheck** jobs; an **installed-package
  smoke** test for `tools/github` (`pip install` then import + `ghclient --help`); explicit
  **minimal `permissions:`** per workflow; concrete **per-workflow + per-ref `concurrency:`**
  group naming; and a **hard rule that no CI job ever runs `ghclient … --apply`** (CI is
  dry-run/validate only; mutations are operator-run).
- **Always-emitting aggregate gate (H2):** add one job **`ci-required`** that **always runs**
  (even docs-only / `tools/github`-only PRs), **depends on** the path-specific jobs, and emits a
  single stable result. Branch protection requires **that** context — not the path-filtered job
  names — so path-filtered workflows can't leave a required check permanently pending.
- **`ci.yml`** (dbt, credentialed): keep checks-only for now; Phase 4 adds a real
  `dbt build` against staging on merge and prod on release/tag (depends on staging/prod
  targets existing).
- **Client-driven:** `ci reconcile` keeps branch-protection required checks in sync with the
  stable **`ci-required`** aggregate context (H2), not the raw job names (fixes §2.2).
- **Authorship guard:** wire `scripts/check_no_attribution.sh` (moved from `bin/`, §12.2.9) into CI
  + pre-commit **advisory-first** (H7): non-blocking until the base-ref selection, expanded file
  coverage (md/yaml/sh/workflow), `fetch-depth: 0`, and temp-repo tests land; only then gate.

---

## 8. Test plan (mapped to `tools/github/tests/`)

- **Unit (no network):**
  - `config.py`: valid parse → dataclasses; unknown key → `ConfigError` (file/field
    scoped); missing policy file → actionable error.
  - `connections.py`: parse fixture `connections.toml` → typed profile; OAuth profile is
    flagged as "not a CI credential."
  - `secrets.py`: field-map → the exact `gh secret set` plan (stub `GhRunner`); asserts
    **no secret value** appears in rendered/logged output; `from_file`/`prompt` handled.
  - `branch_protection.py`: desired-state → `PUT` plan; dry-run renders, executes nothing.
    **(H1) fail-closed export:** a verified HTTP **404** → `null` snapshot (delete-eligible);
    **any other failure** (auth/403/5xx/network/rate-limit/bad-repo) → **no snapshot written +
    non-zero exit**; rollback may DELETE protection **only** from a null snapshot proven to come
    from a verified 404 — never from a null produced by an error.
  - `ci.py`: workflow YAML fixtures → derived required-check contexts. **(H2)** asserts the
    reconciled required context is the always-emitting aggregate **`ci-required`**, never a
    path-filtered job name; inference is correct with **matrix / skipped / duplicate** jobs.
- **Adversarial matrix (H5, unit, marked no-network):** `gh` returns
  **404 / 403 / 500 / timeout**; **malformed JSON**; **missing / unauthenticated `gh`**;
  **insufficient scopes**; **URL-encoded environment names**; **branch-not-found**; **partial
  apply**; **snapshot-push-ok-but-apply-fails** and **apply-ok-but-ops-repo-push-fails**; **secret
  values never appear in exception text** (redaction test); **corrupt-snapshot** rollback refusal;
  **ruleset conflicts** surfaced. Every case asserts a file/field-scoped, actionable error and
  (where mutating) a non-zero exit with no partial side effect left unreported.
- **Integration (stubbed `gh`):** end-to-end verb dispatch through the CLI with a fake
  `GhRunner` recording commands; assert idempotent apply and correct rollback branching.
- **Data-driven:** expectations from fixtures, not scattered literals. Determinism: no live
  `gh`; tests pass with `PYTHONPATH` cleared.
- Mirror the repo's existing test layout/pytest conventions
  (`orchestration/tests/{unit,integration}` + `conftest.py`).

---

## 9. Risks, assumptions, rollback

- **Assumption:** `gh` is authenticated with admin + `repo`/secrets scopes on the target
  repo; `preflight` fails loudly otherwise.
- **Risk:** publishing wrong values to prod secrets. **Mitigation:** `--dry-run` default in
  wrappers, explicit `--yes` to mutate, name/target-only echo, and `audit export` before
  changes.
- **Risk:** OAuth/session profile can't seed CI creds. **Mitigation:** config maps only what
  applies; private key via `from_file`; validation refuses to publish a session token as a
  credential.
- **Risk:** `ci reconcile` sets a wrong required check → merges block. **Mitigation:**
  dry-run diff + `audit export` rollback of protection.
- **Rollback:** branch-protection has export/rollback; secret changes are re-runnable from a
  corrected config; nothing is destructive without `--yes`.

---

## 10. Delivery sequence (sliced, independently green)

**Area label ↔ slice mapping (DECIDED 2026-07, ratified):** **A** = slices 1–2 (scaffold + branch
protection); **B** = slice 3 (`secrets publish`); **C** = slice 4 (`ci reconcile` + CI/doctor +
authorship guard); **D** = slice 5 (READMEs); **E** = slice 6 (Phase 3); **F** = slice 7 (Phase 4).
(E/F already labelled explicitly elsewhere; A–D now pinned.)

1. **Scaffold `tools/github/`** + `config/github-client-config.yml` + `preflight` + `GhRunner`
   seam + config loader + unit tests. (No behavior change to the repo.)
2. **Branch protection** ported from `bin/` (config-driven), with tests; retire `bin/`
   copies. Wrapper: `protect.sh`, `rollback.sh`.
3. **`secrets publish`** (dbt-layer → Environment secrets) + tests. Wrapper:
   `push-snowflake-secrets.sh`.
4. **`ci reconcile`** + CI workflow enhancements (py_compile, docstring check, caching,
   concurrency, authorship guard) + tests. Wrapper: `reconcile-ci.sh`.
5. **Phase 2 — READMEs** for all major dirs from the template.
6. **Phase 3 — Enrichment UX** (typed per-run launchpad override, YAML-bounded, + `all_remaining`
   drain with safety budget per §12.3.5; config-declared dynamic partitions; refresh via
   sensor + manual op per §12.3.1; two jobs — dept-partitioned + unpartitioned drain — per §12.3.4).
7. **Phase 4 — dbt hardening** (`int_` layer, source-decoupled marts, staging/prod targets +
   Bronze source parameterization, promotion CI).

Each step compiles, passes its tests, and leaves the tree green.

---

## 11. Locked decisions (from Stage 1 + iteration 1)

- Config file: **`config/github-client-config.yml`** (in a repo-root `config/` dir).
- Packaging: **standalone `tools/github/pyproject.toml`** (own installable package).
- CLI command name: **`ghclient`**.
- Client shape: **Python module + CLI + thin shell wrappers** (wrappers run frequent
  workflows so exact `gh`/`ghclient` args need not be memorized).
- Location: **`tools/github/`** (retire `bin/`).
- Secret targets (v1): **GitHub Environment secrets, dbt-layer only**; open to expansion.
- Custom-N (Phase 3): **per-run launchpad override + drain safety budget** (§12.3.5) —
  **supersedes the earlier "YAML/env only"** (YAML now owns the ceilings; the launchpad chooses
  within them).
- "Enrich all" (Phase 3): **two primitives** — a department-partitioned job + a separate
  **unpartitioned** enrich-all/drain job (§12.3.4); the `all` partition sentinel is dropped.
- Beyond-departments (Phase 3): **deferred** (§12.3.6) — cheap to add later (one control-table
  column + predicate) since the drain job and control table already exist.
- Option D dimension (Phase 3): **config-declared**, values discovered from the worklist for the
  **department-partitioned** job only; refresh mechanism = sensor + manual op (§12.3.1).
- Documentation: **this is the single authoritative master plan**; all phases specified to
  equal depth regardless of delivery order.
- CLI framework: **typer** (§12.2.1) — explicitly reversible to argparse/click if it feels heavy.
- Mutation-safety: **dry-run by default with a full preview; `--apply` mutates** (§12.2.2).
- Secret publish: **diff-and-confirm + Secrets/Variables split** — private key stays a Secret,
  connection metadata becomes Variables (§12.2.4).
- `exports/` snapshots: **gitignored** in this repo (§12.2.3); their secure private home is a
  **separate private repo `dckallos/artwork-db-ops`** (§12.2.10) — SOPS+age noted as the upgrade
  path if a snapshot ever holds a sensitive value.
- CI key-pair reuse: **verified** one private key may serve local dev + CI simultaneously; the
  two-public-key feature is for rotation only, not a usage cap (§12.2.5).
- CI private-key source: **`from_file` in config with prompt fallback**; validation refuses to
  publish a session/OAuth token as a credential (§12.2.5).
- Workflow ownership: **validate/recommend only** — the client manages GitHub-side settings
  (required checks, secrets, environments); CI YAML edits ship as reviewed commits (§12.2.7).
- Retire `bin/`: **delete after porting** into `tools/github/`, noting the move in
  `bin/README.md` history / a CHANGELOG (§12.2.9).

- Phase-3 (E) — **locked:** "enrich all" = **two jobs (dept-partitioned + unpartitioned drain)**
  (§12.3.4); custom-N = **per-run override + drain budget** (§12.3.5); beyond-departments =
  **deferred** (§12.3.6); partition refresh = **sensor + manual op**, sensor now manages **real
  department keys only** (§12.3.1); worklist = **keep CLI control table** (§12.3.2); concurrency cap
  = **rendered from `framework.yaml`** (§12.3.3); sensor lifecycle = **add-only bundle (retain +
  manual prune, config-derived name, safe no-op, default-off)** (§12.3.7).
- Phase-4 (F) — **locked:** source-decoupling = **conform per source, then union**
  (`int_<src>__<entity>_conformed` → `int_<entity>__unioned` → marts) (§12.4.6); isolation =
  **schema-based (one DB `ARTWORK_DB`, env-routed schemas via `generate_schema_name_for_env`)**
  (§12.4.1); Bronze = **shared `ARTWORK_DB.BRONZE` + dbt `var` override seam** (§12.4.2); enabled sources = **dbt `var` `enabled_sources` toggle + drift guard**
  (§12.4.3); promotion = **staging-auto + prod-on-tag, gated** (§12.4.4); naming =
  **`dbt_daniel` profile (rename to `artwork_pipeline` reversed 2026-07), `obt_` prefix, drop `cma` stub** (§12.4.5); env provisioning =
  **schema + grants + per-env warehouse, folded into Area F (no separate slice)** (§12.4.7).
- Consequences now firm: §12.2.4 publishes a **per-env target selector (`DBT_TARGET`)** — the DB is
  constant `ARTWORK_DB`, so **no per-env `DATABASE` variable**; §12.2.8 still scaffolds **`staging` +
  `prod`** Environments for **secrets + prod gating** (not separate DBs).

_Implementation status (2026-07, this session) — profile / targets / schema routing landed:_
- _**Profile name KEPT `dbt_daniel`** (§12.4.5, rename REVERSED this session): the earlier
  `dbt_daniel` → `artwork_pipeline` rename is withdrawn per maintainer preference.
  `artwork_pipeline/profiles.yml`, `profiles.yml.example`, and `artwork_pipeline/dbt_project.yml`
  are all consistent on `dbt_daniel`. (The profile name is a lookup key, not a schema; the
  per-developer landing schema stays `dbt_kalleward`.)_
- _**staging + prod targets ADDED NOW** (§12.4.1/§12.4.7/§12.2.8): maintainer chose "add
  staging+prod now" — this SUPERSEDES the earlier same-session "dev-only for now" note.
  `profiles.yml` now defines `dev` (local, key FILE via `private_key_path`), `staging` and `prod`
  (CI, INLINE PEM via `private_key`), all env-var-driven, one DB `ARTWORK_DB`, per-env warehouse
  via `DBT_STAGING_WAREHOUSE`/`DBT_PROD_WAREHOUSE`, target selected by `--target`/`DBT_TARGET`._
- _**Schema macro SWITCHED NOW** (§12.4.1): `macros/generate_schema_name.sql` reimplemented as the
  `generate_schema_name_for_env` pattern (prod ⇒ verbatim `SILVER`/`GOLD`; dev/staging/ci ⇒
  `<target.schema>_<CUSTOM>`). The fail-loud allowlist is RETAINED. Well-documented per maintainer._
- _**Example files synced**: `profiles.yml.example` and `.env.example` updated to match the current
  files (new inline-key / per-env-warehouse / `DBT_TARGET` / `DBT_SNOWFLAKE_SCHEMA` vars)._

_Remaining (per §12/§13 briefs — recorded DECIDED in their own sections; the list below previously
lagged in this rollup and is now reconciled):_
- _**Q5** (§12.3.7 sensor lifecycle) — **RATIFIED (Q4, 2026-07): confirm all** → DECIDED (A) locked._
- _**Q6** (§12.4.7 env provisioning) — **RATIFIED (Q4, 2026-07): confirm all** → DECIDED locked; the
  `staging`/`prod` **targets** portion is implemented, and the per-schema **grants** + distinct
  **warehouse** DDL are now **green-lit to draft (Q2)** in `infrastructure/`._
- _**Q7** (§13.1 H1–H9) — recorded **confirmed (adopt all)**; the `obt_` mart-rename sub-item is now
  **DECIDED (Q1): compatibility view for one release** (§13.3 #19 / §12.4.5)._
- _**Q8** (§12.3.3 concurrency cap) — **RATIFIED (Q4, 2026-07): confirm all** → DECIDED
  (doctor-check-first, render later) locked._

_Factual (not a decision): the live protected-branch set (§12.2.6 = Model A, protect `main` only) is now
**VERIFIED (Q3, 2026-07)** via the maintainer's authenticated `gh api repos/dckallos/artwork-db`
(`default_branch = main`; live branch list matches §12.2.6 exactly) — no longer blocked. All
Stage-1/iteration-1 and Q1–Q8 items are decided._

---

## 12. Decision briefs (explained before asked)

Per §0.1, each open decision is explained here — options, tradeoffs, recommendation — in
technical and plain-language terms. The question tool only confirms a choice from a brief.

### 12.1 Decided in iteration 1

Config path `config/github-client-config.yml`; standalone `tools/github/pyproject.toml`;
command `ghclient`; Python core + CLI + shell wrappers; Environment secrets (dbt-layer) v1.
See §11.

### 12.2 Open briefs

#### 12.2.1 CLI framework — DECIDED (reversible)

- *What's being decided:* the library that parses `ghclient` subcommands/flags.
- **argparse (stdlib).** *Technical:* zero third-party deps, matches the repo's stdlib-lean
  style; more boilerplate for nested subcommands and help text. *Layman:* uses only what ships
  with Python — nothing extra to install, but a little more code to write by hand.
- **click.** *Technical:* mature decorator API, ergonomic subcommands + rich `--help`; adds one
  dependency. *Layman:* a popular helper that makes the command polished, at the cost of
  installing one package.
- **typer.** *Technical:* type-hint-driven layer over click; least boilerplate; pulls in
  click + typer. *Layman:* newest and shortest to write, but installs two extra packages.
- **DECIDED:** **typer.** *Technical:* type-hint-driven CLI keeps the command surface terse and
  self-documenting, matching the "type everything on the hot path" house rule; accepts two added
  deps (click + typer) into the standalone `tools/github` package (isolated from orchestration).
  **Explicitly reversible:** if the implementation feels heavy or the deps are unwelcome, re-open
  and fall back to argparse/click. *Layman:* we picked the newest, shortest-to-write option, but
  we can swap it out cheaply if it turns out to be overkill.

#### 12.2.2 Mutation-safety default — DECIDED

- *What was being decided:* whether `ghclient` changes GitHub by default or previews first.
- **Decision:** **dry-run by default, and the dry-run prints a full preview of the exact
  planned change** (the branch-protection `PUT` body; the list of secret/variable *names* to
  be set — never values). An explicit `--apply` performs the mutation. *Layman:* by default it
  shows you precisely what it *would* do and changes nothing; you re-run with `--apply` to
  actually do it.
- **H1 fail-closed export/rollback — DECIDED (2026-07):** `audit export` distinguishes a **verified
  HTTP 404** (protection-not-found → snapshot `null`, a legitimate "no protection" state) from **every
  other failure** (auth/403/5xx/network/rate-limit/bad-repo → **write no snapshot + non-zero exit**).
  `rollback` may `DELETE` protection **only** from a `null` snapshot proven to come from a verified 404
  — never from a null produced by an error. *Layman:* the tool only records "there was no protection"
  when GitHub explicitly says so; any other hiccup makes it stop loudly rather than guess, so a
  transient error can never trick rollback into deleting your protection.
- **H9 ruleset awareness before mutation — DECIDED (2026-07):** before any classic-protection
  mutation, the read/audit path inventories **both** classic branch protection **and** active
  repo/org **rulesets** (§4.3 `audit`), and the preview **reports ruleset overlap**. v1 mutates
  **classic only**; it never silently fights a ruleset. *Layman:* the tool first checks for the newer
  "rulesets" that can also protect a branch and warns you if one overlaps, so it won't make a change
  that a ruleset quietly overrides.

#### 12.2.3 `exports/` snapshots — commit vs gitignore

- *What's being decided:* whether the before-state snapshots written prior to a
  branch-protection change are tracked in git.
- **Gitignored (transient).** *Technical:* snapshots are point-in-time before-state, not
  desired-state; keeping them out of VCS avoids stale JSON being mistaken for policy and keeps
  the repo clean; rollback still works from the local file within a session. *Layman:* the
  "undo" file lives only on your machine; the repo stays tidy.
- **Committed (audit trail).** *Technical:* every prior live protection state is reviewable in
  history/PRs and reproducible from any checkout; downside is snapshot files can drift and be
  confused with the desired-state `policy.<branch>.json`. *Layman:* keep a dated history of
  what protection looked like before each change, visible to the team — but more files that
  could be mistaken for the "real" rules.
- **DECIDED:** **gitignore `exports/`.** The committed source of truth is the
  desired-state `policy.<branch>.json`; GitHub's own audit log covers historical "what was
  live." Snapshots are an operational undo, not documentation. **Follow-on:** the user still
  wants a secure, private, version-controlled home for these snapshots — see **§12.2.10**.

#### 12.2.4 Secret publish behavior + Secrets vs Variables — DECIDED

- *What's being decided:* how `secrets publish` behaves, and where non-sensitive connection
  values land.
- **Overwrite silently.** *Technical:* idempotent `gh secret set` for every mapped field, no
  diff step. *Layman:* just re-sets everything each run — simple, but no heads-up.
- **Diff-and-confirm.** *Technical:* compare which secret/variable **names** will be created or
  changed (values can't be read back from GitHub, so only names/targets are diffed) and require
  confirm before writing. *Layman:* shows which settings will change and asks first.
- **Variables split.** *Technical:* route non-sensitive values (`ROLE`, `DATABASE`,
  `WAREHOUSE`, arguably `ACCOUNT`) to **GitHub Variables** (readable, referenced as
  `vars.X`) and reserve **Secrets** for true secrets (`DBT_SNOWFLAKE_PRIVATE_KEY`). *Layman:*
  keep the boring settings visible and only truly hide the private key.
- **DECIDED:** **diff-and-confirm + Variables split.** *Technical:* safest against wrong-target
  writes and cleanest for workflow authors — `secrets publish` diffs which secret/variable
  **names** will be created or changed and confirms before writing; non-sensitive connection
  metadata (`ROLE`/`DATABASE`/`WAREHOUSE`, and `ACCOUNT`) is routed to **GitHub Variables**
  (`vars.X`), while `DBT_SNOWFLAKE_PRIVATE_KEY` (and its passphrase) stay **Secrets**. *Layman:*
  it shows what will change and asks first; the boring settings stay readable, only the private
  key is truly hidden.
- **H8 precise semantics — DECIDED (2026-07):** because GitHub secret values are unreadable, the
  diff for **Secrets** shows only **name / existence / intended action** (create · overwrite ·
  delete) — **never a value diff**; **Variables** (readable) may show an optional **value diff**.
  Publish modes: **`--no-overwrite`** (skip names that already exist), **`--force`** (overwrite
  without per-name confirm), **`--delete-missing`** (remove managed names absent from the current
  mapping). Default remains diff-and-confirm with none of these flags.

#### 12.2.5 CI-credential private-key source

- *What's being decided:* the `connections.toml` `[default]` profile is OAuth/session
  (`token_file_path`, no key), which is **not** a CI credential; where does the key-pair
  `DBT_SNOWFLAKE_PRIVATE_KEY` come from for CI?
- **Verified (Snowflake docs, `user-guide/key-pair-auth`):** the earlier worry that a key pair
  can only be used in a limited number of *places* is a misconception. Snowflake associates **up
  to two public keys per user** (`RSA_PUBLIC_KEY` + `RSA_PUBLIC_KEY_2`) purely to enable
  **uninterrupted rotation**; it authenticates by verifying whichever public key matches the
  presented private key. There is **no cap on how many clients present the same private key** —
  local dev and CI can use one private key at the same time. *Layman:* one key file works from
  your laptop and from CI simultaneously; the "two keys" feature is only so you can swap keys
  without downtime, not a usage-location limit.
- **`from_file` path in config.** *Technical:* `github-client-config.yml` names a local `.p8`
  path; the client reads the file and sets the secret (the *path* is not sensitive, the key
  never prints). Automatable. *Layman:* tell the tool where your key file is and it uploads it.
- **Interactive prompt.** *Technical:* paste at publish time, nothing stored; most secret-safe,
  least automatable. *Layman:* it asks you for the key each time; nothing is saved.
- **Dedicated key-pair profile.** *Technical:* add a second `connections.toml` profile with
  `private_key_path` and map from it; reuses the profile model, but mixes CI concerns into the
  Snowflake CLI file. *Layman:* make a second connection entry that includes the key.
- **DECIDED:** **`from_file` in config, with prompt fallback**; validation **refuses to
  publish a session token** as a credential (guards against the OAuth-profile footgun).
- **H3 least-privilege CI identity — DECIDED (2026-07):** the CI dbt identity is the dedicated
  **`ARTWORK_TRANSFORMER_SVC`** service user (`TYPE=SERVICE`, key-pair only, provisioned by
  `infrastructure/`), with a **CI-only key distinct from any human/local key**. `secrets publish`
  **role allowlist = {`ARTWORK_TRANSFORMER`, `ARTWORK_LOADER`}**; it **rejects `ACCOUNTADMIN` and any
  non-allowlisted role** unless an explicit **`--allow-role`** override is passed. This is in addition
  to the session-token refusal above. *Layman:* CI logs in as a purpose-built robot account with the
  least privilege it needs, never as an admin, and the tool refuses to publish an admin credential by
  accident.

#### 12.2.6 Protected branch set (factual — needs your confirmation)

- *What's being decided:* which branches `ghclient` protects. The ported `bin/` scripts assume
  `donkey-kong-sandbox` + `main`, but that is another repo's convention.
- *Technical:* the real default/integration branch of `dckallos/artwork-db` should be read via
  `gh api repos/dckallos/artwork-db` at implementation; policy files are then named
  `policy.<branch>.json` per protected branch. *Layman:* I need to know which branches you
  actually protect here (this working branch is `feat/optimize-dagster-options`).
- **DECIDED (Model A — trunk-only):** protect **`main`** only (confirmed default branch = `main`).
  `feat/*`, `docs/*`, `copilot/*` branches are ephemeral and unprotected; `donkey-kong-sandbox`
  exists in this repo but is a **sandbox, not an integration branch** — not protected. `main`
  doubles as the integration branch: merge → staging build, tag `v*` → prod build (§12.4.4). Drop
  the ported `bin/` assumption of `donkey-kong-sandbox`+`main`. **Live branch list (2026-07):**
  `main` (default), `donkey-kong-sandbox`, `feat/enable-dagster`, `feat/enhancement-scripts`,
  `feat/optimize-dagster-options`, `docs/create-readme`, `copilot/remove-initial-file-contents`.
  Adding a protected branch later is a one-line config change. **VERIFIED (Q3, 2026-07):** the
  maintainer's authenticated `gh api repos/dckallos/artwork-db` confirms `default_branch = main` and
  the live `branches` list matches the set above exactly — so Model A is confirmed against live state
  and this item is no longer blocked. *(Side facts for Area C hygiene: `delete_branch_on_merge=false`,
  `allow_auto_merge=false`, and all three merge methods enabled — relevant to the squash-only/linear-history
  policy and auto-delete-head items, not acted on here.)*

#### 12.2.7 Workflow ownership — edit vs validate

- *What's being decided:* whether the runtime client rewrites `.github/workflows/*` or only
  checks them.
- **Edit.** *Technical:* client writes CI YAML (caching, concurrency, gates); powerful but
  couples the client to repo-specific workflow shape and can clobber hand edits. *Layman:* the
  tool rewrites your CI files.
- **Validate/recommend.** *Technical:* client lints and prints recommended diffs; humans commit
  the change; keeps CI authorship human and the client decoupled. *Layman:* the tool checks CI
  and suggests fixes; you apply them.
- **DECIDED:** **validate/recommend** for workflow *content*; the client directly manages
  only GitHub-side *settings* (required checks, secrets, environments). Actual CI YAML edits ship
  as normal reviewed commits (during Phase-1 slice 4).

#### 12.2.8 GitHub Environments to scaffold

- *What's being decided:* which Environments the client creates now.
- **`prod` only.** *Technical:* create the `prod` Environment (required reviewers +
  env-scoped dbt secrets) now; add others when needed. *Layman:* set up just production.
- **`dev`/`staging`/`prod`.** *Technical:* scaffold all three to seat the Phase-4 promotion
  story; some unused initially. *Layman:* set up all three stages up front.
- **DECIDED (consequence of §12.4.4 promotion + per-env secrets):** **scaffold `staging` + `prod`
  now**, each Environment holding its own dbt Secrets/Variables (per-env creds + a `DBT_TARGET`
  selector; the database is constant `ARTWORK_DB` under §12.4.1 schema isolation — **no per-env
  `DATABASE`**); `dev` stays local. Config lists environments so adding one later is a one-line
  change. *Rationale: staging/prod still need isolated credentials and prod gating even though they
  share one database.*

#### 12.2.9 Retire `bin/` — delete vs deprecated shim

- *What's being decided:* what happens to the ported `bin/` scripts.
- **Delete.** *Technical:* remove once `tools/github` covers them — single source of truth.
  *Layman:* delete the old scripts.
- **Deprecated shim.** *Technical:* leave `bin/*.sh` as thin wrappers that call `ghclient` and
  print a deprecation notice; smoother transition, more files. *Layman:* keep the old commands
  working but have them call the new tool and warn.
- **DECIDED:** **delete after porting** (solo-maintained repo; the new wrappers replace
  them), noting the move in `bin/README.md` history / a CHANGELOG.
- **H7 guard home — DECIDED (2026-07):** `bin/check_no_attribution.sh` moves to
  **`scripts/check_no_attribution.sh`** (alongside `scripts/orchestration/` and
  `scripts/normalize_docstrings.py`), **not** `tools/github/` — it is a repo-wide CI/pre-commit
  guard, not GitHub-client-specific. The `bin/` copy is deleted with the rest of `bin/`.

#### 12.2.10 Secure, private, version-controlled home for `exports/` snapshots (NEW)

- *What's being decided:* §12.2.3 keeps `exports/` **out of this repo**, but the before-state
  branch-protection snapshots still deserve a **secure, private, version-controlled** home for
  audit/undo across machines. Where do they live? (These JSON blobs are governance metadata, not
  Snowflake credentials, but should stay private.)
- **(a) Separate private repo** (e.g. `dckallos/artwork-db-ops`). *Technical:* the client pushes
  snapshots to a dedicated private repo; full git history, browsable diffs, clean separation from
  app code; costs one more repo + a push path (a token/`gh` with write scope). *Layman:* a small
  private "operations" repo that stores the undo files with full history.
- **(b) Private Gist synced by the client.** *Technical:* one private Gist per branch (or a
  multi-file Gist); versioned and cheap; less structure and weaker access control than a repo,
  API is per-file. *Layman:* a private scratchpad on GitHub that keeps versions.
- **(c) Encrypted-in-repo (SOPS+age or git-crypt).** *Technical:* snapshots live in the main repo
  but encrypted at rest; single source of truth, no extra repo; adds a key-management dependency
  and decrypt step, and re-introduces the "looks like policy" confusion §12.2.3 avoided. *Layman:*
  keep them here but scrambled so only you can read them.
- **(d) Protected private branch.** *Technical:* a dedicated `ops/exports` branch never merged to
  `main`; stays in one repo, but orphan-branch workflows are awkward and easy to clobber. *Layman:*
  a side branch that holds the files without touching main.
- **(e) GitHub Actions artifacts.** *Technical:* upload snapshots as workflow artifacts; browsable
  in the Actions UI with retention limits, but **not true VCS** (no diff/history beyond retention)
  and requires a workflow to produce them. *Layman:* attach them to CI runs — viewable, but they
  expire and aren't real version history.
- **DECIDED:** **(a) a separate private repo (`dckallos/artwork-db-ops`).** Best mix of
  secrecy (private), browsability, and real version history; keeps the main repo clean (honoring
  §12.2.3) with the smallest tooling cost — the client already shells out to `gh`, so a
  `git push`/`gh api` to a second private repo is a thin add. `(c)` SOPS+age is the documented
  upgrade path if a future snapshot ever needs to hold a sensitive value.

### 12.3 Phase-3 (Dagster enrichment) decision briefs

_Extracted from §5A; these were previously only "leanings" in the design section. Briefed here
to equal depth per §0.1 so Area E can move to implementation-ready._

#### 12.3.1 Dynamic-partition refresh mechanism (Option D)

- *What's being decided:* Option D (§5A.2a) discovers partition values from `MET_WORKLIST`
  instead of the hand-listed 19 departments. Something must populate/refresh Dagster's
  `DynamicPartitionsDefinition`; **when and where does that query run?** §5A.2c deferred this.
- **(a) At code-location load (import time).** *Technical:* query the worklist inside
  `build_definitions()` as the repo assembles. Simplest, no moving parts — but it runs a
  Snowflake query **at import**, which **violates the "no import-time side effects"
  non-negotiable** (`CODE_STANDARDS §3`), breaks bare-process/test import safety and the
  `ARTWORK_SKIP_DBT_PREPARE` ethos, and only updates on reload. *Layman:* read the list once at
  startup — simplest, but it phones the database on import and only refreshes on restart.
- **(b) Sensor.** *Technical:* a Dagster sensor periodically queries the worklist and calls
  `add_dynamic_partitions`/`delete_dynamic_partition`; keys stay live, **import stays
  side-effect-free**. Adds one running component + a cadence to tune; must be idempotent and
  cheap. *Layman:* a small background watcher keeps the list current automatically.
- **(c) Manual `refresh-partitions` op/CLI.** *Technical:* an explicit op (and CLI subcommand)
  the operator runs to sync keys; fully side-effect-free at import, deterministic, testable; the
  cost is it's manual — stale until run. *Layman:* press a button to refresh the list when you want.
- **DECIDED:** **(b) sensor as default + (c) manual op as escape hatch; never (a)** (it
  breaks a non-negotiable). Keep the sensor thin (list query → diff keys → add/remove) and
  **config-gated in `framework.yaml`** (enable flag + interval) so it's data, not code.
  *Cross-impact:* the sensor is a new component the doctor/CI (Area C) should import-check; the
  manual op reuses the CLI seam built in Area A/C.

#### 12.3.2 Worklist / eligibility ownership

- *What's being decided:* where "who is eligible to enrich" lives, and what Option D's discovery
  query reads (§5A.3).
- **(a) Keep CLI-owned `MET_WORKLIST` + `MET_ENRICHMENT_CONTROL` (today).** *Technical:*
  leasing/resumability already built; Option D reads `MET_WORKLIST` directly (display counters
  already do). Truth split across two Bronze tables + CLI, opaque to dbt/lineage. *Layman:* keep
  what works; the new partition list just reads the existing table.
- **(b) Expose worklist as a dbt view (`stg_met__worklist`).** *Technical:* declarative,
  testable, lineage-visible; but dbt can't own leasing, so the claim table still exists and
  partition discovery now depends on dbt having run. *Layman:* model the eligible-list as a
  proper view, at the cost of another dependency.
- **(c) Bronze query at materialization.** *Technical:* no new object; recomputes each run,
  racey without the lease. *Layman:* compute it on the fly each time — simplest to store,
  riskiest to run.
- **DECIDED:** **(a) keep the control table for leasing; Option D reads `MET_WORKLIST`
  directly** (smallest blast radius). Revisit (b) only if Phase-4 wants worklist lineage.
  *Cross-impact:* consistency with **F3** — if source enablement routes through dbt, a worklist
  view (b) gets cheaper to justify; keep the two answers aligned.

#### 12.3.3 Concurrency-cap fix — where the cap values live

- *What's being decided:* §5A.1 found the seeded `dagster.yaml.example` has `max_concurrent_runs:2`
  and **no `tag_concurrency_limits`**, so the per-museum cap the docs promise
  (`ADDING_A_SOURCE.md:32-34`) isn't enforced. Must fix before raising volume; the decision is
  *where the numbers live* to honor "config is data / one home for a fact."
- **(a) Hand-write in `dagster.yaml.example`.** *Technical:* add a `tag_concurrency_limits` block
  keyed on `artwork/rate_limited_api`; simplest, but a second literal that can drift from
  `framework.yaml`'s `concurrency`. *Layman:* type the cap into the Dagster config file.
- **(b) Render `dagster.yaml` from `framework.yaml` at bootstrap.** *Technical:*
  `bootstrap_dagster.sh` generates the block from the same `concurrency`/`rps_budget` source of
  truth; no drift, adds a render step. *Layman:* the cap is computed from the one place you set
  concurrency.
- **DECIDED (refined per review #15 — doctor-check-first):** ship **(a)** now — a hand-written
  `tag_concurrency_limits` block keyed on `artwork/rate_limited_api` in `dagster.yaml.example`, with a
  comment pointing at `framework.yaml` as the source of truth — **plus a deterministic doctor/CI check
  that asserts the seeded `dagster.yaml` values equal what `framework.yaml`'s `concurrency`/`rps_budget`
  imply** (fail loud on drift). Rendering `dagster.yaml` from `framework.yaml` at bootstrap **(b)** is a
  **later enhancement**, not v1: the check removes the drift risk cheaply and keeps `dagster.yaml` a
  human-ownable, generated-file-free artifact for now. *Clarification of the three cap knobs:*
  `max_concurrent_runs` (instance-wide run cap), `tag_concurrency_limits` (per-tag cap — the museum/API
  rate-limit slot we actually need), and executor concurrency (in-run step parallelism) are distinct;
  only `tag_concurrency_limits` enforces the per-source API budget. *Generated-file ownership:* under
  (a) `dagster.yaml` stays hand-owned (no generated file to gitignore); if (b) is adopted later, the
  rendered file becomes generated-and-excluded and the doctor check flips to verifying the render.
  *Cross-impact:* adds a doctor/CI (Area C) check that the seeded instance actually enforces the cap.

#### 12.3.4 "Enrich all" primitive — partition sentinel vs unpartitioned job (review #9, D1)

- *What's being decided:* §5A.2(a) currently models "enrich all" as an `include_all: true` sentinel
  that adds an `all` partition key returning `""` (omits `--department`, drains the worklist). Review
  #9: an `all` key **overlaps** every department partition, so it is **not a disjoint slice** —
  Dagster partition health, backfills, and materialization history go ambiguous (one "partition"
  materializes the union of the rest).
- **(1) Keep the `all` sentinel partition.** *Technical:* one asset/def, least wiring. *Con:*
  semantic overlap; the partition UI/health/backfill misreport. *Layman:* simplest, but the dashboard
  can't tell "all" apart from the sum of departments.
- **(2) Two primitives — department-partitioned job (disjoint) + a separate *unpartitioned*
  "enrich-all / drain" job.** *Technical:* partitions stay disjoint (real department slices);
  "enrich all" is its own unpartitioned job draining the worklist; the refresh sensor (§12.3.1) then
  manages only real department keys, never a fake `all`. Factory supports both a partitioned and an
  unpartitioned job per source, config-declared. *Layman:* one clean "run a specific department"
  control and one clean "run everything" button — no overlap.
- **(3) Unpartitioned-only (defer dynamic partitions).** *Technical:* drop department partitions for
  now; one drain-all job with department as an optional *run-config filter*. Matches "why am I picking
  a partition at all?" (#10). *Con:* loses per-department disjoint materialization/backfill in the
  partition UI. *Layman:* just a "run everything (optionally filter to a department)" job; no
  partition tracking.
- **Recommendation:** **(2)** if per-department completeness/backfill visibility has value (usually
  yes for a catalog); **(3)** if the department dimension is *purely* friction and partition tracking
  isn't wanted. Either way **stop modeling `all` as a partition key.** (2) also seats D3/#11 — the
  unpartitioned enrich-all job is the natural home for a typed per-run "run N now" override + safety
  budget (#12). *Cross-impact:* §5A.2(a), §12.3.1 (sensor scope), D3.
- **DECIDED:** **(2) two primitives — a department-partitioned job (disjoint slices) + a separate
  UNPARTITIONED enrich-all/drain job.** Stop modeling `all` as a partition key. The refresh sensor
  (§12.3.1) manages only real department keys; the unpartitioned job hosts the per-run override +
  drain safety budget (§12.3.5). *Folds review #9/#10; supersedes the `include_all` sentinel in
  §5A.2(a).*

#### 12.3.5 Run-level control — per-run launchpad override + drain safety budget (review #11/#12, D3; REOPENS §11 custom-N)

- *What's being decided:* §11 locked "custom-N = YAML/env only" (§5A.2b): operators set
  `BATCH_SIZE`/`MAX_BATCHES` in `framework.yaml` or env *before* launch. Review #11 argues this
  is not real operator control — you cannot stand at the Dagster launchpad and say "run 10,000
  now" without editing config and reloading; review #12 argues the implied drain recipe ("set
  `MAX_BATCHES` high") is unsafe because nothing bounds wall-time / rows / API spend.
- **(a) Typed per-run launchpad override, YAML-bounded, + explicit drain mode with a safety
  budget (RECOMMENDED).** *Technical:* the enrich job exposes a typed run-config schema (Dagster
  `Config`) whose fields default from `framework.yaml`; a per-run value is accepted **only if**
  YAML marks the knob overridable and is **clamped to a YAML `max_*` cap** (a launchpad typo can
  never exceed the museum's rate ceiling). Add a first-class `all_remaining`/drain mode that
  replaces "big `MAX_BATCHES`" with an explicit bounded loop governed by a **safety budget** —
  `max_wall_seconds`, `max_rows`, `max_api_calls`, concurrency cap, resumability (stops cleanly at
  the budget, leaves the worklist claimable for the next run). *Layman:* you can type "run N now"
  (or "drain everything") right in the launch box, but the tool won't let you exceed the safe
  ceilings you set once in config, and "drain" has stop-limits so it can't run away.
- **(b) Keep YAML/env-only (status quo §11).** *Technical:* no new run-config surface; edit
  `framework.yaml`/env and reload. Simplest, preserves "config is data" purity, keeps the exact
  pain the review names. *Layman:* keep editing the settings file before each big run.
- **(c) Per-run override but no drain safety budget.** *Technical:* accept a launchpad N but keep
  "drain = big N"; less to build than (a) but leaves #12 unaddressed (unbounded drains). *Layman:*
  let people type N, but "run everything" still has no brakes.
- **Recommendation:** **(a)** — the only option that satisfies both #11 (real launch-time control)
  and #12 (bounded drain) while staying config-governed: YAML still owns the *ceilings*
  (config-is-data), the launchpad only chooses within them. Pairs with §12.3.4(2): the
  unpartitioned enrich-all/drain job is the home for `all_remaining` + budget. *Cross-impact:*
  reopens the §11 lock; ties to §12.3.4 (D1) and §5A.2b; budget fields become new typed
  `framework.yaml` config (+ loader validation).
- **DECIDED:** **(a) typed per-run launchpad override, YAML-bounded, + explicit `all_remaining`
  drain mode with a safety budget.** Defaults from `framework.yaml`; per-run values accepted only
  when YAML marks a knob overridable and clamped to a YAML `max_*` cap; drain governed by
  `max_wall_seconds`/`max_rows`/`max_api_calls`/concurrency + resumability. **This supersedes the
  §11 "custom-N = YAML/env only" lock** (YAML now owns the *ceilings*, the launchpad chooses within
  them). Home: the unpartitioned enrich-all/drain job from §12.3.4.

#### 12.3.6 "Beyond-departments" selector contract (review #13, part of D4)

- *What's being decided:* §5A names a "beyond-departments" control but never defines it. Today
  `sources/met.yaml` only has `partition_by {cli_flag: --department, values: …}` over departments
  — i.e. *dynamic departments*, not a genuinely different slicing dimension. What does "slice by
  something other than department" mean, and where does that contract live?
- **(a) Named selectors/cohorts owned by the worklist/campaign control table (RECOMMENDED).**
  *Technical:* extend the already-kept `MET_ENRICHMENT_CONTROL`/worklist (§12.3.2) with an
  arbitrary named-cohort column (e.g. `selector`/`campaign`), so an operator can lease and drain
  "highlights", "recent-acquisitions", "has-image-no-tags", etc. The unpartitioned drain job
  (§12.3.4) takes an optional `selector` run-config value scoping the worklist query;
  leasing/resumability are reused verbatim; **zero museum literals in `.py`** (selectors are data
  rows). *Layman:* you define named batches in a control table ("the highlights campaign") and
  tell the job to run one — reusing the same claim/resume machinery departments already use.
- **(b) Defer beyond-departments; Phase-3 = all (unpartitioned) + department only.** *Technical:*
  ship nothing here now; drain-all + department filter cover the near-term need; add cohorts when a
  concrete one exists. *Layman:* skip it for now — "everything" and "one department" are enough.
- **(c) Generic CLI selector args mapped from YAML (`--filter key=value`).** *Technical:* the
  extractor CLI grows a generic predicate mapped from a YAML-declared allowlist of filterable
  columns; flexible, but pushes arbitrary predicate logic toward the CLI and risks
  unbounded/expensive scans without a curated cohort table. *Layman:* a general "filter by any
  field" flag — powerful but easy to misuse.
- **(d) A dbt/Snowflake view exposes named cohorts the job consumes.** *Technical:* cohorts are dbt
  models/views; declarative and lineage-visible, but adds a dbt dependency to selector discovery
  and can't own leasing. *Layman:* define the batches as dbt views; tidy, but couples enrichment to
  dbt having run.
- **Recommendation:** **(a)** — reuses the leasing table we already committed to keep (§12.3.2),
  keeps the contract honest and source-agnostic, defers no real need; revisit (d) only if Phase-4
  wants cohort lineage. If you'd rather build no cohort surface in Phase-3, **(b)** is the safe
  minimum. *Cross-impact:* §12.3.2 (control table), §12.3.4 (drain job hosts `selector`), §12.3.7
  (sensor manages department keys only — cohorts are run-config, not partitions).
- **DECIDED:** **(b) defer cohorts.** Phase-3 ships "enrich all" (§12.3.4) + department only. The
  recommended (a) adds *no recurring operator action* (it is fully opt-in), but the maintainer
  prefers not to build latent surface now. **Cheap-later guarantee:** because §12.3.4 already builds
  the unpartitioned drain job and §12.3.2 keeps the control table, adding cohorts later is one
  nullable `selector` column + one `WHERE` predicate + one run-config field — no rework. Revisit
  when a concrete named cohort exists.

#### 12.3.7 Dynamic-partition refresh sensor — lifecycle design (review #14, D4-part; depends on Q1 = two-jobs)

- *What's being decided:* Q1 kept a department-partitioned job whose keys are the live Met
  departments; §12.3.1 chose "sensor (default) + manual op" to keep those keys current. Review #14:
  the sensor's *lifecycle* is under-specified. This brief pins seven dimensions into one safe
  bundle.
- *Design dimensions & recommended values (the bundle):*
  1. **Action scope — add-only.** The sensor only *registers/retires partition keys*; it never
     launches enrichment runs (launch stays manual or a separate schedule). Cheap, no surprise
     API/credit spend, minimal interaction with the concurrency cap (§12.3.3). *Layman:* the sensor
     keeps the department list current; a human/schedule presses "go."
  2. **Stale keys — retain + manual prune.** When a department disappears from the source, the
     sensor **never auto-deletes** its key; the key + its materialization history are kept, and a
     separate manual `prune-partitions` op deletes on explicit request. Auto-deleting would silently
     destroy backfill/audit history. *Layman:* old departments stick around (with history) until you
     deliberately clean them up.
  3. **Historical materializations — preserve.** Follows from (2): never orphan history
     automatically; prune is the only (documented, destructive) path.
  4. **Partition-def name + migration — config-derived name, seed-from-current.** The name is
     derived from config (`<source_key>_<dimension>`, read from `sources/*.yaml`), **not hardcoded**
     (prime directive). On first load, seed the dynamic set from the current static 19 (or the live
     source list) so existing history maps over; ship a one-time migration note. *Layman:* the
     partition set gets a name built from config and is pre-filled with today's departments so
     nothing is lost.
  5. **Slug↔value persistence + collisions — persist the map, fail loud.** Keys are stable slugs;
     the slug→original-value map is persisted in Snowflake (control/dim table) because a value can't
     be reconstructed from a slug. If two values slugify to the same key, the refresh raises an
     actionable, file/field-scoped error (never silently merges). *Layman:* keep a lookup from the
     tidy key back to the real name, and stop with a clear error if two names would collide.
  6. **Snowflake-unavailable — safe no-op.** If the department query errors/times out, the sensor
     skips the tick (logs, no add, no delete) and never treats an errored/empty result as "all
     departments gone." *Layman:* if the database is unreachable, do nothing that tick rather than
     wrongly wiping the list.
  7. **Enabled-by-default per env — off by default, opt-in via config; on in staging/prod, off in
     dev.** Each env reads its own env-routed schema in the shared `ARTWORK_DB` (§12.4.1); dev usually doesn't want a background Snowflake
     poll. The manual refresh op (§12.3.1) is always available regardless. *Layman:* the automatic
     refresher is off unless you turn it on for an environment; you can always refresh by hand.
- *Testability (folds Area C / #20–21):* the sensor reads Snowflake through an injected reader
  `Protocol` (no import-time connection), so unit tests stub the department list and exercise the
  no-op-on-error and collision paths with **no network**.
- **(A) Adopt the bundle above (RECOMMENDED).** Safe, add-only, history-preserving, config-derived,
  test-seamed.
- **(B) Add-and-launch.** Sensor also kicks off enrichment when new departments appear. *Con:*
  surprise spend + concurrency-cap interaction; rejected unless you want fully hands-off ingestion.
- **(C) Auto-prune stale keys.** Sensor deletes departments that vanish. *Con:* destroys
  history/backfill audit; rejected as default.
- **Recommendation:** **(A)**. *Cross-impact:* §12.3.1 (this is the sensor it referenced), §12.3.3
  (add-only ⇒ minimal concurrency interaction), §12.4.1/§12.2.8 (per-env enable), Area C (Protocol
  seam + no-network test), doctor (validate the config-derived partition-def name).
- **DECIDED:** **(A) adopt the full bundle** — add-only; retain + manual `prune-partitions`;
  preserve history; config-derived def name seeded from the current 19; persisted slug↔value map
  with fail-loud collisions; safe no-op when Snowflake is unavailable; default-stopped, opt-in per
  env (on in staging/prod, off in dev). Closes Area E's design. *Implementation seam:* injected
  worklist reader `Protocol` (no import-time connection) so Area C unit-tests the add-only,
   no-op-on-error, and collision paths with no network.

### 12.4 Phase-4 (dbt hardening) decision briefs

_Extracted from §5B. F1 and F4 are **cross-cutting** — they reshape Area B (secrets/Variables)
and §12.2.8 (Environments), which is exactly why E/F are being fully specified before B/C are
frozen._

#### 12.4.1 Environment isolation model — schemas vs databases (CROSS-CUTTING)

- *What's being decided:* §5B.1 — isolation is schema-only today (`ARTWORK_DB` is constant;
  `generate_schema_name.sql:64` routes `prod`/`snowflake` → verbatim `SILVER`/`GOLD`, else a dev
  prefix; there is **no `prod` target**, so that branch is unreachable and a `staging` target
  would silently get a dev prefix). How do dev/staging/prod isolate?
- **(a) Separate schemas in one database (`ARTWORK_DB`).** *Technical:* cheapest; extend
  `generate_schema_name`/`allowed_schemas` and add real `staging`/`prod` targets. Weaker
  blast-radius isolation (shared DB + grants); a bad prod run shares the DB with dev. *Layman:*
  everything in one database, separated by folders.
- **(b) Separate databases `ARTWORK_DB_{DEV,STAGING,PROD}`.** *Technical:* strong isolation, clean
  per-env RBAC and cost attribution, mirrors the promotion story; costs three DBs, per-env grants,
  and per-env connection metadata. *Layman:* one database per stage — strongest separation, a bit
  more setup.
- **DECIDED (reversed 2026-07, review #18 + maintainer):** **(a) separate schemas in one database
  `ARTWORK_DB`** — the standard dbt pattern, and it removes the ACCOUNTADMIN DB-provisioning /
  RBAC / migration burden that (b) implied. Implement via the dbt-shipped
  **`generate_schema_name_for_env`** pattern (target schema in dev/CI, verbatim custom schema in
  prod) — replacing the current `generate_schema_name.sql:64` logic — plus **real `staging` and
  `prod` targets** (today only dev/`snowflake` exist, so the prod branch is unreachable). *Accepted
  trade-off:* weaker blast-radius/RBAC isolation than separate DBs; *mitigations:* per-schema
  grants, a distinct warehouse per env for cost attribution, and the `generate_schema_name_for_env`
  guard so dev/CI can never write prod schemas. **Cross-impact:** Area B / §12.2.4 now publishes a
  **per-env target/schema selector** (e.g. `DBT_TARGET`), **not** a per-env `DATABASE` (the DB is
  constant); §12.2.8 still scaffolds `staging` + `prod` Environments for **secrets + prod gating**
  (not for separate DBs); §12.4.7's separate-DB bootstrap slice is **superseded** (see there).
- **IMPLEMENTED (2026-07):** `macros/generate_schema_name.sql` now uses the `generate_schema_name_for_env`
  pattern (prod ⇒ verbatim custom schema; non-prod ⇒ `<target.schema>_<CUSTOM>`), replacing the old
  `:64` prod/`snowflake` branch; the fail-loud allowlist is retained. Real `dev`/`staging`/`prod`
  targets now exist in `artwork_pipeline/profiles.yml`, so the "no prod target / unreachable branch"
  finding above is resolved. Still pending: per-schema **grants** + distinct per-env **warehouses** in
  `infrastructure/` (§12.4.7).

#### 12.4.2 Bronze source-database parameterization — dbt `var` vs `env_var`

- *What's being decided:* §5B.1 — sources hardcode `ARTWORK_DB.BRONZE`
  (`_met__sources.yml:12-13`, `_aic__sources.yml:15-16`), so every env reads the same Bronze. How
  is the Bronze source DB made per-env?
- **(a) dbt `var`, defaulted per target.** *Technical:* `bronze_db` resolved per target in
  `dbt_project.yml`/invocation; explicit, visible in project config, testable; CI overrides via
  `--vars`. *Layman:* a project setting that changes with the target.
- **(b) `env_var('BRONZE_DB')`.** *Technical:* CI/shell injects it; flexible, but invisible in the
  project and the house/global dbt guidance discourages `env_var` for Snowflake-run dbt. *Layman:*
  an environment variable the CI sets.
- **DECIDED:** **(a) dbt `var`, defaulted per target**, CI overriding via `--vars` — keeps the
  fact in the project (config-is-data) and dodges the `env_var` caveat. *Cross-impact (updated for
  F1=(a) schema isolation):* Bronze is a **single shared raw home `ARTWORK_DB.BRONZE`** across all
  envs (one ingestion; dev/staging/prod transforms read the same Bronze and write env-routed
  `SILVER`/`GOLD` schemas). The `bronze_db`/`bronze_schema` `var` is **retained as the override
  seam** if a per-env Bronze is ever needed, but defaults to the shared Bronze — no
  `ARTWORK_DB_{ENV}` value.

#### 12.4.3 Enabled-source list — dbt-owned toggle (DECIDED)

- *What's being decided:* §5B.2's union macro is driven by a list of enabled sources. Orchestration
  already declares each source in `sources/*.yaml` (the "add a source = one YAML" promise). Where
  does dbt's enabled-source list live so two copies don't drift?
- **(a) dbt `var` list in `dbt_project.yml`.** *Technical:* simplest for dbt, but a **second home**
  for "which sources exist" that can drift from `orchestration/.../sources/*.yaml`. *Layman:* list
  the sources again in the dbt config.
- **(b) Derive from dbt's own graph/sources.** *Technical:* enumerate from `graph`/
  `_<src>__sources.yml` so the list is intrinsic to dbt; no hand list, macro logic is more
  advanced. *Layman:* dbt figures out the sources from what's already defined.
- **(c) Generate the dbt var from `sources/*.yaml` at build.** *Technical:* a small step writes the
  enabled list into a dbt var from the orchestration source keys — single upstream home; adds a
  generation step spanning two subsystems. *Layman:* the one source-of-truth (the YAMLs) feeds dbt
  automatically.
- **DECIDED:** **(a) dbt `var` list `enabled_sources` in `dbt_project.yml`.** *Rationale (user):*
  dbt may carry sources that are **defined but not yet finalized / not yet consumed by Dagster**, so
  an explicit on/off toggle is required — deriving from defined staging models (b) would auto-union
  works-in-progress into the marts. This is **intentional decoupling, not drift**: the dbt-enabled
  set and the orchestration set are legitimately different. **Drift guard:** (1) a dbt test asserts
  every `enabled_sources` entry has matching `stg_<source>__*` models (catches typos/missing
  staging); (2) the `accepted_values`/`source_system` test list derives from the *same* var; (3) a
  doctor/CI check may **report (not enforce)** divergence from orchestration `sources/*.yaml` for
  visibility. *Layman:* one clear list of the museums that are "on" for dbt, with a safety check
  that each really exists and a heads-up if dbt and Dagster disagree.

#### 12.4.4 Promotion CI triggers + prod gating (CROSS-CUTTING with Area C / §12.2.8)

- *What's being decided:* §5B.2 — when credentialed `dbt build`s run per env, and how prod is
  protected. Note today's `orchestration-tests` job is **offline** (`dbt parse` only) and `ci.yml`
  is **checks-only** (no `dbt build`, no dev/prod isolation), so this is net-new CI.
- **(a) staging on merge to integration branch; prod on release/tag; prod behind a GitHub
  Environment (required reviewers).** *Technical:* mirrors the promotion story; prod needs an
  approval; requires per-env secrets/vars (Area B) + Environments (§12.2.8). *Layman:* merges deploy
  to staging automatically; tagging a release deploys to prod after you approve.
- **(b) staging only for now; prod manual.** *Technical:* less CI to build; prod stays a manual
  `dbt build` until Phase-4 stabilizes. *Layman:* automate staging, run prod by hand for now.
- **DECIDED:** **(a), sequenced** — land staging automation first, add prod-on-tag once the
  `prod` Environment + secrets exist. *Cross-impact:* concrete consumer of §12.2.8 (needs
  `staging`+`prod`, per F1=(b)) and Area C's CI work; also the credentialed-build path the offline
  `orchestration-tests` job deliberately does not cover.

#### 12.4.5 Naming / cleanup ratifications (DECIDED)

- *What's being decided:* the §5B.1 naming smells — small, but lock them so Area F implements once.
- **DECIDED (profile rename REVERSED 2026-07, this session):** **keep the profile name
  `dbt_daniel`** (maintainer preference; avoids editing `dbt_project.yml`'s `profile:`). The earlier
  rename to `artwork_pipeline` is withdrawn — `profiles.yml`, `profiles.yml.example`, and
  `dbt_project.yml` all remain on `dbt_daniel`. Still DECIDED: move the per-dev schema
  (`DBT_DKALLEWARD` → now the `DBT_SNOWFLAKE_SCHEMA` env var, default `dbt_kalleward`) and
  `private_key_path` **out of the committed `profiles.yml` into env/target config** (portability +
  secret hygiene) — **DONE** (all targets now `env_var()`-driven); rename `openaccess_catalog` →
  **`obt_openaccess_catalog`**
  (one-big-table convention) **shipping a one-release compatibility view** (Q1 DECIDED 2026-07 —
  see §13.3 #19); drop the self-described no-op `cluster_by=['source_system']` on
  `fct_artwork_images`; and **drop `cma` everywhere** — `models/staging/cma/` (incl. its README),
  the committed `cma.yaml` source, and `extraction/cma/` — re-add Cleveland as one clean
  onboarding when it is actually built. *Layman:* tidy names, remove
  personal/machine-specific bits, and delete the half-there Cleveland stub until it's real.
- *Cross-impact:* the profile **name** (`dbt_daniel`) is the same one referenced by Area B's hand-off
  (§6); keep it identical in both places. Dropping `cma` spans three places — `models/staging/cma/`,
  `cma.yaml`, and `extraction/cma/` — removed together so config, models, and extraction stay
  symmetric (no half-onboarded source).
- **IMPLEMENTED (2026-07) — partial:** the profile name **stays `dbt_daniel`** (rename to
  `artwork_pipeline` REVERSED this session — see the DECIDED note above); `profiles.yml`,
  `profiles.yml.example`, and `dbt_project.yml` are all consistent on `dbt_daniel`. `private_key_path`
  + the per-dev schema are **out of the committed profile** (env-var-driven; `DBT_SNOWFLAKE_SCHEMA`
  default `dbt_kalleward`). **Still pending** from this brief: the `openaccess_catalog` →
  `obt_openaccess_catalog` rename (+ §13.3 #19 compat-view vs breaking), dropping the no-op
  `cluster_by` on `fct_artwork_images`, and dropping the `cma` stub (models + `cma.yaml` +
  `extraction/cma/`).

#### 12.4.6 Source-decoupled correctness — conform-then-union vs union-on-staging (review #17, D2)

- *What's being decided:* §5B.2 introduces an `int_` layer that unions per-source staging via a
  var-driven macro so a new source is "one var entry + its `stg_` models." Review #17 warns that
  unioning *directly on staging* silently papers over per-source semantic mismatch — differing
  identity/dedup rules, nullability, image/provenance semantics, unit/format — because the union
  just stacks columns that happen to share names. Marts then average apples and oranges with no
  per-source contract.
- **(a) Per-source CONFORMED intermediates, then union (RECOMMENDED).** *Technical:*
  `int_<src>__<entity>_conformed` normalizes each source to a shared contract (identity/dedup key,
  required-not-null set, canonical image/provenance columns, enum domains) with per-source tests;
  then `int_<entity>__unioned` unions the *conformed* models; marts `ref()` the unioned model. Each
  source has an explicit, tested boundary before shared logic; a new source must **satisfy the
  contract**, not just column-match. Costs one more model layer per entity. *Layman:* every
  museum's data is first translated into one common shape (with its own checks) before being
  combined — so the combined table is genuinely comparable.
- **(b) Union macro directly on staging + schema/nullability tests (status quo §5B.2).**
  *Technical:* fewer models; rely on schema/`dbt_utils` tests to catch mismatch after the union.
  Cheaper now, but tests catch *structural* drift, not *semantic* (a column present + non-null but
  meaning something different passes). *Layman:* combine staging directly and hope the tests
  notice — lighter, but blind to meaning-level differences.
- **(c) Hybrid — union-on-staging now, add the conformed layer when a 3rd source exposes a real
  mismatch.** *Technical:* least work today; defers the layer until pain is concrete. Risk:
  retrofitting conform after marts depend on the union is more churn than doing it once now, and
  the 2-source case can already hide mismatch. *Layman:* do the simple thing until a third museum
  forces it.
- **Recommendation:** **(a)** — the dbt-side embodiment of the prime directive ("add a source = a
  bounded, contract-checked unit"); the marginal cost (one `int_<src>__…_conformed` per
  source×entity) is small versus the correctness guarantee, and it makes `enabled_sources`
  (§12.4.3) meaningful — a source is "on" only once it conforms. Choose **(c)** only for the
  smallest Phase-4 diff, revisiting when Cleveland returns. *Cross-impact:* §5B.2, §12.4.3
  (conformance is what the drift-guard test checks against); the union macro consumes conformed
  models.
- **DECIDED:** **(a) conform per source, then union.** *Naming contract is deliberately narrow —
  exactly two patterns, and only for models that feed a **shared** mart:* the per-source conformed
  inputs (`int_<src>__<entity>_conformed`) and the unioned output (`int_<entity>__unioned`). *No
  other constraint:* per-source staging (`stg_<src>__*`), museum-specific intermediates, source-only
  marts, extra schemas, and any model *type* (seeds/snapshots/exposures/metrics/semantic models) are
  unconstrained and may differ per museum. Conform is the adapter where per-source differences
  normalize, so everything upstream of it has full breathing room (more than union-on-staging, which
  would force identical columns onto staging). A mart fed by only one source needs no conform layer.

#### 12.4.7 Environment provisioning under schema isolation (review #18, D5; SUPERSEDES the separate-DB slice)

- *What's being decided:* review #18 asked how the separate databases get created/migrated. Q6
  **reversed §12.4.1 to schema-based isolation**, so the heavy separate-DB bootstrap (three DBs,
  per-DB RBAC, cross-DB backfill) is **no longer needed**. What remains is a much smaller,
  mostly-dbt change.
- **DECIDED:** **a lightweight provisioning note folded into Area F (no separate slice).** Scope:
  (1) adopt/adjust `generate_schema_name_for_env` (replacing `generate_schema_name.sql:64`);
  (2) add real `staging`/`prod` **targets** in `profiles.yml`; (3) ensure the env-routed
  `SILVER`/`GOLD` (+ staging variants) schemas exist with **per-schema grants** to the transformer
  role (H3 CI identity); (4) one **distinct warehouse per env** for cost attribution; (5) **no
  backfill/migration** — all envs share the one `ARTWORK_DB` and the shared `BRONZE`, so existing
  data stays put. *Homes:* macro + targets in `artwork_pipeline/`; the small grant/warehouse DDL in
  `infrastructure/` / `git-setup/operator/` (ACCOUNTADMIN, but minimal, gated, never in offline
  CI). *Cross-impact:* §12.4.1 (isolation), §12.4.4 (staging automation needs the schema + grants,
   not a database), Area B/§12.2.8 (per-env secrets + `DBT_TARGET`, not per-env DB).
- **IMPLEMENTED (2026-07) — partial:** items (1) `generate_schema_name_for_env` and (2) real
  `staging`/`prod` **targets** are DONE in `artwork_pipeline/`. **Q2 DECIDED (2026-07): draft the
  remaining DDL now** (unblocks staging/prod dbt runs). **Still pending (now green-lit to draft):**
  (3) ensure the env-routed schemas exist with **per-schema grants** to the transformer role, (4) one
  **distinct warehouse per env** — the live `profiles.yml` already defaults
  `DBT_STAGING_WAREHOUSE`→`ARTWORK_WH_STAGING` and `DBT_PROD_WAREHOUSE`→`ARTWORK_WH_PROD`
  (`profiles.yml:60,75`), so the DDL must create **`ARTWORK_WH_STAGING`** and **`ARTWORK_WH_PROD`**
  (not `ARTWORK_WH`) plus schemas `STAGING_SILVER`, `STAGING_GOLD`, `SILVER`, `GOLD`, and each dev's
  `<prefix>_SILVER`/`_GOLD`. Home: small, gated ACCOUNTADMIN DDL in `infrastructure/` /
  `git-setup/operator/`, never in offline CI. (5) no backfill needed (shared DB/Bronze).

---

## 13. External review reconciliation (ChatGPT "pessimist" pass, 2026-07)

Source: `docs/chatgpt-pro-pessimist-implementation-review.md`. Triaged by the maintainer; the
scope-drift framing (#1, #2-as-reslice, #10, #12-as-reslice) is deliberately set aside. This section
records what we **accepted** (and where it lands), what remains **under design discussion**, and what
we **reviewed but already cover / decline** — so nothing from the review is lost.

### 13.1 Accepted hardening — fold now (DECIDED)

_Confirmed by the maintainer (2026-07): **adopt all H1–H9 as written** (Q7). These gate Areas
A/B/C/D and must be in place before any `ghclient --apply`._

- **H1 (review #3) — fail-closed branch-protection export.** Export must distinguish a **verified
  HTTP 404 "protection not found"** (→ snapshot `null`, legitimate) from **every other failure**
  (auth/403/5xx/network/rate-limit/bad-repo → **fail closed: write no snapshot, non-zero exit**).
  Rollback may only `DELETE` protection from a `null` snapshot that came from a verified 404.
  *Home:* §12.2.2 + Area-A branch-protection module. *Why:* today any `gh` blip → `null` → rollback
  deletes protection (destructive). *Layman:* never treat "couldn't reach GitHub" as "there were no
  rules."
- **H2 (review #4) — stable, always-emitting required check.** Do **not** require path-filtered job
  names directly. Introduce one aggregate gate — `ci-required` — that always runs (even for
  docs-only / `tools/github`-only PRs), depends on the path-specific jobs, and emits a single stable
  result; `ci reconcile` requires **that** context. *Home:* §7 + §12.2.6 ci-reconcile capability.
  *Why:* `orchestration-tests.yml` is path-filtered, so requiring `pytest` would deadlock docs-only
  PRs forever. *Layman:* one "did everything that needed to run pass?" light, always on.
- **H3 (review #7) — least-privilege CI identity; reject `ACCOUNTADMIN`.** Publish validation
  **rejects `ACCOUNTADMIN` and any non-allowlisted role by default** (override only with an explicit
  flag) and asserts a **dedicated CI Snowflake user/key** distinct from a human/local key. CI already
  targets `ARTWORK_TRANSFORMER`; the guard makes that a rule. *Home:* §12.2.4/§12.2.5. *Why:* the
  current session is `ACCOUNTADMIN`; the mapping could publish it. *Layman:* CI gets its own low-power
  login, never the master key.
- **H4 (review #20) — CI gate set.** Add `actionlint`, `shellcheck`, installed-package smoke for
  `tools/github`, explicit minimal Actions `permissions:`, concrete `concurrency:` group naming
  (per-workflow + ref, never a blanket group), and a hard rule that **no CI job runs
  `ghclient --apply`**. *Home:* §7.
- **H5 (review #21) — adversarial test matrix for `tools/github`.** Ship failure-mode tests, not just
  happy path: `gh` 404 vs 403 vs 500 vs timeout; malformed JSON; missing/unauthenticated `gh`;
  insufficient scopes; URL-encoded environment names; branch-not-found; partial apply;
  snapshot-push-succeeds-but-apply-fails **and** apply-succeeds-but-ops-repo-push-fails; **secret
  values never surface in exception text (redaction test)**; corrupt-snapshot rollback; required-check
  inference with matrix/skipped/duplicate jobs; ruleset conflicts. Unit tests marked **no-network**.
  *Home:* §8. *Why:* this is where the tool fails in real life; also validates H1.
- **H6 (review #22) — READMEs are current-state only.** Every README describes **what exists today**;
  anything planned is labelled "planned (§X)", never written as operational fact. Fix the §5.2 sample
  (it referenced the not-yet-built sensor as current). *Home:* §5.1/§5.2.
- **H7 (review #8) — authorship guard advisory-first.** `check_no_attribution.sh` starts **advisory
  (non-blocking)**; before gating: fix base-ref selection (drop the `origin/donkey-kong-sandbox`
  default), expand coverage beyond `py/sql/ipynb` to `md/yaml/sh/workflow`, require `fetch-depth: 0`,
  and add tests against a temp git repo. *Home:* §7.
- **H8 (review #6) — precise secret/variable semantics.** For **Secrets**: show name, existence,
  intended action — never claim a value diff (values are unreadable). For **Variables** (readable):
  optional value diff. Add explicit `--no-overwrite` / `--force` / `--delete-missing` modes. *Home:*
  §12.2.4 (refines the DECIDED diff-and-confirm).
- **H9 (review #5) — audit reads rulesets + classic protection.** The read/audit path inventories
  **both** classic branch protection **and** active repo/org **rulesets** before any mutation; v1
  mutates classic only but reports ruleset overlap. *Home:* §4.3 (promote from brainstorm) + §12.2.2.

### 13.2 Tier-2 design items — now folded (decisions recorded in §12)

All resolved — decisions recorded in §12 (walk-through order **#9 → #17 → #11 → #13/#14 → #18**;
full §12 briefs: D1→§12.3.4, D2→§12.4.6, D3→§12.3.5, D4→§12.3.6 [beyond-departments] +
§12.3.7 [sensor lifecycle], D5→§12.4.7):
- **D1 (#9)** model "enrich all" as a separate **unpartitioned job/op**, not an `all` partition key
  (partitions must be disjoint). Affects §5A.2.
- **D2 (#17)** **conform per source, then union**: `int_<src>__<entity>_conformed` →
  `int_<entity>__unioned` → marts. Affects §5B.2 + §12.4.3.
- **D3 (#11)** reopen the §11-locked "custom-N = YAML/env only" toward a **typed per-run launchpad
  override** (default from YAML, per-run override only if YAML allows, with max caps).
- **D4 (#13/#14)** define the **beyond-departments contract** (campaign/worklist selectors vs generic
  CLI selectors vs dbt cohort view vs explicit non-goal) and the **sensor refresh lifecycle**
  (add-only vs launch; stale-key handling; historical materializations; partition-def name +
  migration from the static 19; slug↔value persistence/collisions; Snowflake-down behavior;
  dev/prod enablement). **RESOLVED:** cohorts **deferred** (§12.3.6); sensor = **add-only bundle**
  (§12.3.7).
- **D5 (#18)** **RESOLVED by the Q6 reversal** — isolation is now **schema-based in one
  `ARTWORK_DB`** (§12.4.1) via `generate_schema_name_for_env`, so the separate-DB bootstrap slice is
  superseded by a lightweight schema/grants/per-env-warehouse note folded into Area F (§12.4.7); no
  cross-DB migration.

### 13.3 Reviewed — already covered or declined

- **#2 audit-only v1 — declined.** Superseded by §12.2.2 (dry-run default + full preview + explicit
  `--apply`); with H1+H2 fixed, gated mutation is safe. The review reacted to the raw `bin/` scripts,
  not our gated design.
- **#16 enabled_sources drift — covered.** §12.4.3 already records intentional decoupling + a drift
  guard (dbt test + informational doctor check); adding the framing "orchestration source
  *declaration* vs dbt mart *participation*."
- **#19 mart rename breaking — DECIDED (Q1, 2026-07): ship a compatibility view.**
  `obt_openaccess_catalog` becomes the real model; a thin view `openaccess_catalog`
  selects `*` from it for **one release**, then is dropped (deprecation tracked in
  `CHANGELOG`). Non-breaking for downstream readers. Mechanics folded into §12.4.5.
- **#1/#10/#12 re-slice — set aside** per maintainer (delivery order is the maintainer's call).


