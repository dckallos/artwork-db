# Separation Plan -- Progress Tracker

## Status: Plan Complete -- Model C (sibling repos) DECIDED

## Analysis Summary (2026-06-07)

### Files inventoried:
- scripts/snowflake_cli/ (15 files, ~2974 lines) -- GENERIC toolkit with 3 artwork defaults
- scripts/lib/ (5 files, ~1923 lines) -- Framework components (mostly generic)
- scripts/ root (12+ scripts) -- Mix of generic orchestration + artwork-specific
- infrastructure/ (29 SQL files) -- All artwork-specific DDL
- extraction/met/ (12+ files) -- artwork-specific Python loader
- artwork_pipeline/ (17 files) -- artwork-specific dbt project
- dbt_diagnostics/ (55+ files) -- Nearly independent Python package
- tests/ (6 files) -- Framework tests
- docs/ (35+ files) -- Context docs and framework docs

### Key coupling points identified:
1. `_lib.sh:46` -- `SNOW_LIB_DEFAULT_WAREHOUSE="ARTWORK_WH"` (env-overridable)
2. `06_setup_loader_keypair.sh:47-48` -- `ARTWORK_LOADER_SVC`/`ARTWORK_LOADER` (env-overridable)
3. `09_setup_transformer_keypair.sh:44-45` -- `ARTWORK_TRANSFORMER_SVC`/`ARTWORK_TRANSFORMER` (env-overridable)
4. `framework_integration_test.sh:207` -- hardcoded `ARTWORK_DB` check
5. `dbt_orchestrate.sh:21` -- hardcodes `artwork_pipeline` path
6. `bootstrap.py` -- hardcodes `ARTWORK_ADMIN` role name throughout
7. `scripts/manifest.txt` -- references `infrastructure/` and `git-setup/` paths
8. `dbt_diagnostics/config.yml` -- `dbt_project_dir: ../artwork_pipeline`
9. `Makefile` -- orchestrates all concerns
10. `.env.example` -- vars for all concerns combined
11. `dbt_orchestrate_modern.sh:44` -- DEFAULT_CONFIG references artwork_domain.yml
12. `inject_failures.py/sh` -- bridges dbt_diagnostics + artwork_pipeline

### Coupling assessment:
- Toolkit scripts (06/09) use artwork names but ALL are env-overridable already
- The only truly hardcoded artwork ref in lib/ is the framework_integration_test.sh line 207
- `bootstrap.py` is artwork-specific (parses ARTWORK_ADMIN grants) but serves as
  a pattern for any role name -- parameterization is straightforward
- `orchestrate.sh` is GENERIC (reads manifest.txt, shells out) -- the manifest content is project-specific
- `dbt_diagnostics` has zero Python import dependencies on artwork_pipeline

### Decision checkpoint: The 3 vs 4 repo question
- 3-repo: toolkit + artwork + dbt-diagnostics (inject_failures stays with artwork)
- 4-repo: toolkit + artwork-iac + artwork-pipeline + dbt-diagnostics (splits infra from app)
- Recommendation: 3-repo (artwork's DDL and pipeline are tightly coupled; same deploy lifecycle)

### Plan writing: COMPLETE (updated 2026-06-07)

Written to `docs/prompts/REPO_SEPARATION_PLAN.md` (1065 lines, 10 sections + 2 appendices).

### Key decision: Model C (sibling repos) -- LOCKED IN

artwork-db references snowflake-toolkit via `TOOLKIT_DIR` env var pointing at a
sibling directory. No embedding, no subtree, no submodule. Independent git
histories. Rationale: single developer, active development on both, clean logs.

### Self-review checklist:
- [x] Every file in repo assigned to exactly one target
- [x] Dependency graph is acyclic (toolkit <- artwork; dbt-diagnostics standalone)
- [x] git filter-repo commands provided for both extractions
- [x] Migration can proceed incrementally (Phases 0-4, rollback at each)
- [x] Each repo has validation commands
- [x] No artwork strings remain in toolkit (after refactoring prerequisites)
- [x] dbt-diagnostics pip-installable standalone (after pyproject.toml fix)
- [x] artwork-db references toolkit via TOOLKIT_DIR (sibling path)
- [x] Risk mitigations documented (10 risks, including toolkit-not-found for Model C)
- [x] Q1 decided (Model C); Q2-Q5 remain open with recommendations
- [x] SQL_FILE coupling documented (scripts 06/09 -> git-setup/operator/)
- [x] No vendor/ directory in artwork-db post-migration
- [x] Appendix B Makefile uses realpath sibling resolution + fail-fast
