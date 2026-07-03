# CODE_STANDARDS.md

The engineering bar for **artwork-db**, with a focus on the orchestration layer
(`orchestration/artwork_orchestration/`). These standards exist to keep the system
**YAML-driven, loosely coupled, typed, and testable** as it scales to many data sources.

If a rule here conflicts with a quick hack, the rule wins. If a rule blocks correct
behavior, change the rule in a PR — don't silently violate it.

---

## 1. Core philosophy

1. **Config is data; code is mechanism.** Sources and knobs are declared in
   `framework.yaml` / `sources/*.yaml` and parsed into a typed model. Framework `.py`
   contains *generic mechanism only* — it never names a specific source.
2. **Decouple at seams, not everywhere.** Introduce an abstraction only where two concerns
   genuinely need to vary independently (config parsing ↔ Dagster assembly ↔ dbt ↔
   Snowflake connectivity). Do not abstract a single call site.
3. **Composition over inheritance.** Build behavior by assembling small objects and
   injecting collaborators. Inheritance is reserved for true is-a relationships (framework
   base classes, `Enum`).
4. **Make illegal states unrepresentable.** Validate at the boundary (load time), then pass
   typed objects inward so downstream code cannot receive a malformed shape.
5. **Least surprise, least coupling.** A module imports the minimum it needs; import-time
   behavior is inert (no network, no dbt shell-out, no credential reads).

---

## 2. Typing & the domain model

- **Public functions are fully annotated.** Parameters and return types, no bare `Any` on
  the hot path. Use `from __future__ import annotations`.
- **Parsed config → `@dataclass(frozen=True)`.** Immutable, hashable, self-documenting.
  Replace ad-hoc dicts (e.g. the profile dict in `_connection.py`) with dataclasses
  (`ProfileConfig`). Replace bare `int`/`dict` check results with typed result objects.
- **Closed sets → `Enum`.** `severity`, `backoff`, `jitter`, step `kind`, `mode` are
  `Enum`s, parsed and validated at load time — never compared as raw string literals in
  factories.
- **Seams → `typing.Protocol`.** For things you inject or stub (dbt assets, the Snowflake
  connection provider, a source registry), define a `Protocol` so callers depend on a
  contract, not a concrete class. Structural typing keeps coupling low without an
  inheritance tree.
- **Collections → typed wrappers when they carry behavior.** The source registry is a
  `SourceRegistry` with `keys()`, `get(key)`, `__iter__`, `__len__` — not a bare tuple
  passed around with helper functions living elsewhere.

```python
# Good: typed, immutable, validated once at the edge.
class Severity(str, Enum):
    ERROR = "error"
    WARN = "warn"

@dataclass(frozen=True)
class ProduceSpec:
    table: str
    severity: Severity
    check_nonempty: bool = False
```

---

## 3. Coupling & dependency direction

- **Dependencies point inward toward config, never sideways between features.**
  `config.py` depends on `loader.py`; factories depend on the model; nothing in the
  framework depends on a specific source package.
- **Inject dependencies; default at the edge.** Functions that need a collaborator take it
  as a parameter with a sensible default resolved at the outermost layer (as
  `build_definitions(dbt_assets=None, dbt_resource_obj=None)` already does). This is what
  makes the code testable with stubs.
- **No import-time side effects.** Module import must not open connections, run dbt, or
  read secrets. Expensive/side-effecting work goes behind a function call
  (`build_definitions()`), an env gate (`ARTWORK_SKIP_DBT_PREPARE`), or lazy import
  (`import snowflake.connector` inside `connect()`).
- **One home for a fact.** A value (repo root, project dir, DB/schema) is defined once and
  imported. No parallel definitions that can drift.
- **Narrow public surfaces.** Prefix internal helpers with `_`. `__init__.py` is
  import-only — no logic, no re-export gymnastics.

---

## 4. Modularization

- **One responsibility per module.** `loader.py` is being split into: `${ENV:default}`
  interpolation, JSON-Schema validation, and semantic validation — each independently
  testable. A module you can't unit-test in isolation is doing too much.
- **Factories are pure functions of the model.** `build_source_assets(spec)`,
  `build_source_checks(spec)`, `build_jobs(registry)`, etc. take typed input and return
  Dagster objects with no hidden global reads. Purity = trivially testable.
- **A single assembly entry point.** `build_definitions(...)` is the only place the code
  location is composed; the module-level `defs` is a thin call to it. Tests assemble
  against fixtures through the same path production uses.

---

## 5. Error handling

- **Fail at the boundary with context.** Config errors raise a dedicated `ConfigError`
  scoped to file + field: `sources/cma.yaml: steps[0].produces.table: required`. Never let
  a bare `KeyError`/`IndexError` escape the loader.
- **Reject the unknown.** Unknown YAML keys are errors, not silently ignored — this catches
  typos before they become "why isn't my config taking effect".
- **Best-effort paths degrade, they don't crash.** Metadata/verification queries
  (`_snowflake`, `_connection`) swallow connectivity failures and report "could not
  verify" so a dev shell without credentials still loads.
- **No silent excepts.** `except Exception: pass` is banned except where explicitly
  documented as best-effort, and even then narrow the exception and add a comment.

---

## 6. dbt & Dagster specifics

- **Derive, don't hand-maintain.** Model facts (e.g. the Gold-mart freshness list) come
  from the compiled dbt **manifest** (`dbt_manifest.py`, models tagged `marts`), not a list
  someone must remember to edit. `framework.yaml` may hold a fallback only.
- **Build the manifest once, in the parent.** Run-worker subprocesses must not each run
  `dbt deps` (races under dbt-fusion → `IoError dbt1001`). The launcher runs `dbt parse`
  once; `resources.py` prepares only when the manifest is missing and only when
  `ARTWORK_SKIP_DBT_PREPARE` is unset.
- **Connect via the dbt profile, not a bespoke identity.** The orchestration layer opens
  Snowflake using the same `profiles.yml` profile/target the transform layer uses — one
  connection identity for the whole project.
- **Translator keys sources to assets.** dbt sources are keyed (via
  `ArtworkDbtTranslator`) to match extraction asset keys so lineage is automatic — keep
  that mapping generic.
- **Version-stable introspection.** Prefer counting the module-level lists
  (`extraction_assets`, `jobs`, `asset_checks`) over Dagster internal-graph APIs that shift
  between releases (see `doctor_orchestration.sh`).

---

## 7. Testing

- **Tests ship with the change.** New behavior → unit test; new wiring → integration test.
- **Layout:** `orchestration/tests/{unit,integration}/` with `conftest.py` fixtures.
- **Unit tests:** no live Snowflake, minimal/no Dagster runtime. Cover loader rules,
  `dbt_manifest.gold_mart_names()` against a fixture `manifest.json`, `_connection` profile
  resolution + `env_var(...)` rendering from a fixture `profiles.yml`, and policy/model
  derivations from a fixture `framework.yaml`.
- **Integration tests:** real Dagster with stubbed `assets_dbt`/`resources` (and a fixture
  `manifest.json`). Assert definitions-load parity (asset keys, group names, partition
  count, checks, jobs, tags, schedules) and an **acceptance test**: drop a fixture source
  YAML into a temp `sources/` dir and assert the generated assets/checks/jobs — proving a
  new source needs **zero framework `.py` edits**.
- **Data-driven, not literal-driven.** Expected values come from fixtures. Do not scatter
  `met`/`aic`/`cma` literals through assertions; museum names are allowed *in tests* but
  the grep gate keeps them out of framework `.py`.
- **A grep-gate test** asserts 0 museum-identifier hits across framework `.py`.
- **Determinism & isolation.** Use `loader.reset_framework_cache()` in a fixture so cached
  config from one test never leaks into another. Tests must pass with `PYTHONPATH` cleared
  and `ARTWORK_SKIP_DBT_PREPARE=1`.
- **Run:** `ARTWORK_SKIP_DBT_PREPARE=1 pytest orchestration/tests`.

---

## 8. Style & hygiene

- **Naming:** `snake_case` funcs/vars, `PascalCase` classes/enums, `UPPER_SNAKE` module
  constants, `_leading_underscore` for internal. Names read as intent, not abbreviations.
- **Docstrings** on modules and public functions explain *why* and note coupling/side
  effects; skip narrating obvious lines. One-line inline comments only where logic isn't
  self-evident.
- **Triple quotes get their own lines.** Every triple-quoted docstring (and any standalone
  triple-quoted string statement) opens with `"""` alone on its line and closes with `"""`
  alone on its line — even one-line docstrings. Never glue the first line of prose to the
  opening quotes, and never leave the whole docstring on a single line. `scripts/normalize_docstrings.py`
  checks and auto-fixes this (`--check` to report, `--write` to apply); it is AST-based, so it
  only rewrites docstrings/statement strings and never touches triple-quoted string *values*.
  It is wired as an **opt-in** `manual` pre-commit hook (`pre-commit run --hook-stage manual
  normalize-docstrings --all-files`) while the existing tree is normalized incrementally — it
  is not yet a hard CI gate, so run it on any file you touch before you push.
- **Imports:** stdlib, third-party, local — grouped and ordered. Lazy-import heavy/optional
  deps at first use.
- **No dead code, no speculative abstractions, no backwards-compat shims.** Delete unused
  code; don't design for hypothetical sources that don't exist yet.
- **Small, focused PRs** sliced along the issue #6 phases; each independently green in CI.

```python
# Canonical: opening and closing triple quotes each on their own line.
def f():
    """
    One-line summaries still get their own opening/closing quote lines.
    """

def g():
    """
    Summary line.

    Longer explanation across multiple lines. The closing quotes sit alone
    on the final line.
    """

# Malformed (auto-fixed by scripts/normalize_docstrings.py):
def bad_one():
    """First line glued to the opening quotes.
    """

def bad_two():
    """Whole docstring squeezed onto a single line."""
```

---

## 9. Definition of done

- [ ] Behavior configured in YAML + typed model + loader validation (no new literals in `.py`).
- [ ] Loose dicts/strings on the hot path replaced by dataclasses/enums, validated at load.
- [ ] No new import-time side effects; seams injectable/stubbable.
- [ ] Unit and/or integration tests added; `pytest orchestration/tests` green locally and in CI.
- [ ] Grep gate returns **0** hits in framework `.py`.
- [ ] Errors are file/field-scoped and actionable.
- [ ] `doctor_orchestration.sh` passes; `py_compile` clean.
