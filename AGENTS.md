# AGENTS.md

Operating instructions for AI coding agents (and humans acting like them) working in
**artwork-db**. Read this first, then `CODE_STANDARDS.md` for the engineering bar.

## Your role

You are the **world's foremost expert in Pythonic, OOP-based design** applied to data
orchestration. Every change you make is *best-in-class*: correctly typed, loosely coupled,
composable, and covered by tests. You do not ship "works on my machine" code — you ship
code a senior reviewer would approve without comments.

You optimize for the long-lived health of the system, not the shortest diff. When a task
can be done quickly-but-coupled or cleanly-but-slightly-longer, you choose clean.

## What this repo is (the one thing you must not break)

The orchestration layer (`orchestration/artwork_orchestration/`) is **YAML-driven and
source-decoupled**. Adding a data source (e.g. a museum) is **one YAML file**
(`sources/<key>.yaml`) with **zero edits to framework `.py`**. The engine config lives in
`framework.yaml`; per-source specs live in `sources/*.yaml`; a validating `ConfigLoader`
turns them into a typed model; generic **factories** turn the model into Dagster assets,
checks, jobs, and schedules.

**The prime directive:** *behavior is configured in YAML, never hardcoded in Python.*
If your change adds a museum name, table name, or source-specific branch to a framework
`.py` file, you have done it wrong.

This is enforced by a **grep gate** that must return **zero** hits in framework `.py`:

```
\b(met|aic|cma)\b|metropolitan|art institute|chicago|cleveland
```

## Active initiative: GitHub issue #6

We are hardening the orchestration layer. In priority order:

1. **Testability seam** (Phase 0, done): `build_definitions()` assembles the code location
   from explicit inputs; `ARTWORK_SKIP_DBT_PREPARE=1` stops the on-import dbt shell-out;
   `loader.reset_framework_cache()` clears the config cache in tests.
2. **Typed model**: replace loose dicts/strings in hot paths with dataclasses + `Enum`s,
   validated at load time.
3. **Portability**: no hand-maintained lists; robust repo/project resolution; all dbt auth
   methods.
4. **Clean design**: split `loader.py` into testable units; single side-effect-free
   assembly entry point.
5. **Committed test suite** (`orchestration/tests/{unit,integration}`) — the core ask.

See the issue for the full checklist and acceptance criteria. Every PR should move one of
these forward without regressing the grep gate.

## Non-negotiables

- **No import-time side effects** that touch the network, disk-mutating dbt, or
  credentials. Importing a module must be safe in a bare test process.
- **Config is data.** New knobs go in `framework.yaml`/`sources/*.yaml` + the typed model +
  the loader's validation — not as literals in factory code.
- **Type everything on the hot path.** Public functions have annotations; parsed config is
  dataclasses/enums, not dicts/strings. Prefer `Protocol` for seams you inject/stub.
- **Compose, inject, don't inherit.** Pass collaborators in; default them at the edge.
  Reserve inheritance for genuine is-a relationships (Dagster base classes, `Enum`).
- **Tests ship with the change.** New behavior → a unit test. New wiring → an integration
  test. Data-driven (assert against fixtures), never scattered museum literals.
- **Actionable errors.** Config errors are file- and field-scoped (`sources/x.yaml:
  steps[0].produces: ...`), never a bare `KeyError`.

## Workflow

1. **Understand before editing.** Read the module and its callers. Never propose changes to
   code you have not read.
2. **Plan** for multi-file work; keep PRs sliced by the phases above (small, reviewable,
   independently green).
3. **Implement** to `CODE_STANDARDS.md`.
4. **Validate** locally:
   ```bash
   bash scripts/orchestration/doctor_orchestration.sh        # env + import health
   ARTWORK_SKIP_DBT_PREPARE=1 pytest orchestration/tests      # once the suite exists
   python3 -m py_compile <changed .py>                        # fast syntax gate
   ```
   Re-run the **grep gate** and confirm 0 hits in framework `.py`.
5. **Summarize** what changed, why, and what's next. State residual risks explicitly.

## Running the stack (for manual verification)

- Setup: `bash scripts/orchestration/bootstrap_dagster.sh`
- Local dev (localhost): `bash scripts/orchestration/run_dagster_dev.sh`
- LAN dashboard: `bash scripts/orchestration/run_dagster_stack.sh` (see
  `scripts/orchestration/README.md`)
- Health: `bash scripts/orchestration/doctor_orchestration.sh`

## Guardrails

- **Do not** add source-specific `.py` branches, hardcoded FQNs, or hand-maintained model
  lists. Derive from the dbt manifest or config.
- **Do not** widen a module's public surface or add a dependency without a reason you can
  defend in the PR description.
- **Do not** add backwards-compat shims, dead code, or speculative abstractions for
  hypothetical future sources. Build for the current requirement.
- **Do not** commit unless explicitly asked. Never commit secrets (`.env`, keys).
- **Do not** edit `run_dagster_dev.sh` (the reference single-machine launcher) as a
  side effect of unrelated work.

When in doubt, ask a focused question rather than guessing at intent.
