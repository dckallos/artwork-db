# Repository Separation: Multi-Session Planning Prompt

Paste this entire file into a fresh Cortex Code context window.

---

## Your Role

You are a **Principal Software Engineer** (L7 Google / E7 Meta / L8 Amazon equivalent)
performing a high-stakes codebase decomposition. You have deep expertise in:

- Git history preservation (`git filter-repo`, subtree splits, merge strategies)
- Monorepo-to-polyrepo migration patterns (shared-library extraction, interface contracts)
- Snowflake CLI/IaC tooling and dbt project lifecycle
- Shell scripting best practices (POSIX compliance, library extraction, namespacing)
- Python packaging (`pyproject.toml`, editable installs, namespace packages)
- Dependency analysis (import graphs, source-to-source references, runtime coupling)

Your standards: no broken references after separation, no duplicated logic across
repos, no loss of git history for any file that has meaningful commit ancestry,
no circular dependencies between the separated repositories. Every separation
decision must be justified by a clear ownership boundary.

---

## CRITICAL: Connection Break Resilience Protocol

Your Cortex Code context can be lost at any time due to connection breaks. The ONLY
way to preserve progress is to execute a tool call. **You MUST make a tool call
after reviewing every three (3) files.** This is non-negotiable.

Acceptable checkpoint tool calls:
- `bash`: Run `wc -l <files>`, `grep -c`, `ls`, or `echo "checkpoint"`
- `web_search`: Search for relevant git/packaging documentation
- File write: Append findings to a progress file

**Rules:**
- Never review more than 3 files without a tool call between them.
- Before starting each analysis section, perform a web search relevant to that
  section's technical domain. This serves two purposes: (a) grounds decisions in
  current best practices, and (b) creates a checkpoint.
- When completing a major section of analysis, write your findings to
  `docs/prompts/SEPARATION_PROGRESS.md` immediately. This is your durable memory.
- If resumed after a break: read `docs/prompts/SEPARATION_PROGRESS.md` first to
  see what was already analyzed, then continue from where it left off.
- After every design decision, run a bash command (even `echo "decision checkpoint"`)
  to create a restoration point.

---

## Project Context

**Repository:** `artwork-db` (GitHub: `dckallos/artwork-db`)
**Branch:** `donkey-kong-sandbox`
**Account:** `OBANOYY-MK07348` (Snowflake, AWS US East 2)
**Current state:** Monolithic repo containing four distinct concerns that have
grown entangled over time. The owner wants clean separation into multiple
repositories with preserved git history.

---

## The Four Identified Concerns

### 1. Snowflake Infrastructure Toolkit (GENERIC)

Scripts that manage Snowflake CLI setup, connection bootstrapping, key-pair
generation, DDL orchestration, and IaC apply/rollback. These are
**domain-agnostic** -- they work with ANY Snowflake project, not just artwork.

**Files (primary):**
```
scripts/snowflake_cli/          # 15 files, ~2974 lines total
  _lib.sh                       # 748 lines -- core library (connection-aware)
  setup.sh                      # 349 lines -- multi-phase bootstrap runner
  init_profile.sh               # 198 lines -- seed connections.toml
  new_account.sh                # 151 lines -- new-account wizard
  00_install_snowflake_cli.sh   # 32 lines
  01_init_snowflake_home.sh     # 24 lines
  02_generate_admin_keypair.sh  # 45 lines
  03_lock_config_permissions.sh # 40 lines
  04_register_admin_public_key.sh # 116 lines
  05_verify_admin_jwt.sh        # 53 lines
  06_setup_loader_keypair.sh    # 113 lines
  07_test_loader_connection.sh  # 45 lines
  08_promote_admin_warehouse.sh # 155 lines
  09_setup_transformer_keypair.sh # 111 lines
  10_test_transformer_connection.sh # 46 lines
  README.md

scripts/lib/                    # Framework components
  connection_resolver.sh        # 423 lines -- universal connection resolution
  ddl_orchestrator.sh           # 65 lines -- DDL orchestration core
  dbt_orchestrator.sh           # 89 lines -- dbt orchestration core
  framework_integration_test.sh # 530 lines -- self-test harness
  legacy_comparison_test.sh     # 816 lines -- old-vs-new comparison

scripts/orchestrate.sh          # 391 lines -- IaC apply/rollback driver
scripts/orchestrate_modern.sh   # 403 lines -- modernized version (uses lib/)
scripts/apply_sql.sh            # 67 lines -- single-file apply via snow CLI
scripts/rollback_sql.sh         # 32 lines -- paired drop execution
scripts/bootstrap.py            # 283 lines -- privilege preflight (Python)
scripts/bootstrap_chmod.sh      # chmod policy
scripts/activate_mac.sh         # Multi-Mac key activation
scripts/check.sh                # Session checker
scripts/checkpoint.sh           # Run checkpoint writer
scripts/load_profile.sh         # Profile loader
scripts/unload_profile.sh       # Profile unloader
scripts/status_profile.sh       # Profile status

tests/framework/                # Tests for the generic framework
  unit/test_connection_resolver.sh
  unit/test_orchestrate_modern.sh
  unit/mocks/
tests/examples/basic_project_integration.sh
tests/integration/test_multi_account_deployment.sh
```

**Key observation:** `scripts/snowflake_cli/06_setup_loader_keypair.sh` and
`09_setup_transformer_keypair.sh` use role names (`ARTWORK_LOADER_SVC`,
`ARTWORK_TRANSFORMER_SVC`) that are artwork-specific. The rest of `_lib.sh` and
the framework are generic.

### 2. Artwork Project (DOMAIN-SPECIFIC)

DDL, dbt models, Python extraction code, and operational SQL specific to the
artwork/museum data pipeline.

**Files:**
```
infrastructure/                 # 29 SQL files (14 create/drop pairs + 1 refresh)
  create_*.sql / drop_*.sql     # All artwork-specific DDL
  CLAUDE.md

artwork_pipeline/               # dbt project
  dbt_project.yml
  profiles.yml
  packages.yml
  models/staging/met/           # 6+ model files
  macros/
  README.md

extraction/                     # Python Met Museum loader
  __init__.py
  met/
    run.py                      # CLI entry point
    config.py                   # Snowflake connection config
    csv_bootstrap.py            # CSV snapshot loader
    snapshot_loader.py          # Full snapshot into Bronze
    control_seeder.py           # Seed enrichment control
    control_enricher.py         # Drain worklist
    image_enricher.py           # Image URL enrichment
    db.py                       # SQLite helper
    snowflake_uploader.py       # Stage + COPY INTO
    sql/                        # SQL templates
    requirements.txt
    CLAUDE.md, README.md

operations/                     # Operational SQL
  met_seed_enrichment_control.sql

git-setup/                      # In-Snowflake Git mirror (artwork-specific bind)
  create_git_ops_db.sql
  create_api_integration.sql
  create_git_repository.sql
  drop_*.sql (3 paired drops)
  operator/
  README.md

analysis/
  met_snapshot_profile.sql

inject_failures.py              # Fixture generation (artwork + dbt_diagnostics)
inject_failures.sh              # E2E fixture runner

scripts/manifest.txt            # Ordered apply list (artwork-specific paths)
scripts/dbt_orchestrate.sh      # 171 lines -- artwork dbt lifecycle
scripts/sql/                    # Ad-hoc diagnostic SQL

Makefile                        # Targets: iac, infra, bootstrap, dbt-*, loader, etc.
.env.example                    # Artwork-specific env vars
profiles.yml.example            # dbt profile template
requirements.txt                # Combined Python deps
```

**Key observation:** `scripts/manifest.txt` references `infrastructure/` paths
and `git-setup/` paths. The `Makefile` orchestrates both IaC and dbt. The
`dbt_orchestrate.sh` script hardcodes `artwork_pipeline`.

### 3. dbt-diagnostics (INDEPENDENT PACKAGE)

A standalone Python CLI that reads dbt artifacts and provides diagnostics.
Already has its own `pyproject.toml` and is pip-installable.

**Files:**
```
dbt_diagnostics/                # Self-contained Python package
  pyproject.toml                # Independent packaging
  __init__.py, __main__.py, main.py
  models.py, renderer.py, colors.py, config.yml
  classifiers/                  # Error classification
  tracers/                      # DAG + column tracing
  enrichers/                    # Live Snowflake enrichment
  linters/                      # Static SQL checks
  templates/                    # Jinja2 report templates
  fixtures/                     # Real dbt artifact pairs (24 files)
  tests/                        # 202+ tests
  BUILD_PROMPT.md, LINEAGE_TRAIL_PLAN.md, HANDOFF_PROMPT*.md, CHANGELOG.md
```

**Key observation:** `config.yml` has `dbt_project_dir: ../artwork_pipeline` and
`profile_name: artwork_pipeline`. These are runtime configuration values, not
hard code dependencies. The fixtures contain `model.artwork_pipeline.*` unique IDs
but these are data strings, not import paths.

### 4. General Utilities (CLASSIFICATION TBD)

Files that could belong to either the toolkit or the artwork project, or might
be dead code:

```
scripts/git_mark_executable.sh  # chmod helper
scripts/executable_files.txt    # List of files to chmod
scripts/secret_bearing.txt      # List of files with secrets
setup-claude-code.sh            # Claude Code optimization kit setup
docs/                           # Context docs, prompts, journals
AGENTS.md, CLAUDE.md            # AI assistant instructions
LICENSE                         # Repo license
```

---

## Coupling Analysis (Pre-Computed for You)

### Cross-references FROM scripts TO domain code:
- `dbt_orchestrate.sh:21` -- hardcodes `artwork_pipeline` path
- `lib/dbt_orchestrator.sh:18,66` -- mentions `artwork_pipeline/` in comments
- `snowflake_cli/09_setup_transformer_keypair.sh` -- mentions artwork_pipeline in comments
- `activate_mac.sh:7,111` -- mentions "extraction, dbt" in usage text
- `scripts/lib/framework_integration_test.sh:207` -- hardcoded `ARTWORK_DB` check

### Cross-references FROM extraction TO infrastructure/scripts:
- `met/.env.example:15` -- mentions `scripts/snowflake_cli/06_*`
- `met/config.py:63,66` -- mentions `infrastructure/` and `scripts/snowflake_cli/06_*`
- `met/snowflake_uploader.py:125` -- mentions `scripts/snowflake_cli/06_*`

### Cross-references FROM artwork_pipeline TO other dirs:
- `README.md` -- mentions `infrastructure/`, `extraction`
- `macros/generate_schema_name.sql` -- mentions `infrastructure/` in comments
- `models/` -- references Bronze tables created by `infrastructure/`

### Cross-references FROM dbt_diagnostics TO domain code:
- `config.yml` -- `dbt_project_dir: ../artwork_pipeline`
- `fixtures/*.json` -- contain `model.artwork_pipeline.*` strings (data, not imports)
- `LINEAGE_TRAIL_PLAN.md` -- artwork_pipeline CLI examples

### Shared root files used by multiple concerns:
- `Makefile` -- targets for infra, dbt, extraction, diagnostics
- `requirements.txt` -- combined deps for extraction + dbt
- `.env.example` -- vars for all concerns
- `AGENTS.md` / `CLAUDE.md` -- AI context for the monorepo

---

## Git History Preservation: Technical Reference

The recommended tool is `git filter-repo` (successor to deprecated `git filter-branch`).

**Key commands for splitting:**

```bash
# Clone the source repo (work on a fresh clone -- filter-repo is destructive)
git clone artwork-db artwork-db-toolkit
cd artwork-db-toolkit

# Keep only specific paths (preserves full commit history for those paths)
git filter-repo --path scripts/snowflake_cli/ \
                --path scripts/lib/ \
                --path scripts/orchestrate.sh \
                --path scripts/orchestrate_modern.sh \
                --path scripts/apply_sql.sh \
                --path scripts/rollback_sql.sh \
                --path scripts/bootstrap.py \
                --path tests/framework/ \
                --path tests/examples/

# Optionally rename paths to become the repo root:
git filter-repo --path-rename scripts/snowflake_cli/:snowflake_cli/ \
                --path-rename scripts/lib/:lib/
```

**For multiple non-contiguous paths in one new repo:**
```bash
git filter-repo --path dir1/ --path dir2/file.py --path dir3/
```

**Important caveats:**
1. `git filter-repo` rewrites ALL commit hashes (new SHAs). Cross-repo
   references to old commits will break.
2. Files that moved between directories during their history may need
   `--path-rename` mappings to capture the full history chain.
3. Commits that touched files in MULTIPLE repos will appear in ALL resulting
   repos (with the irrelevant file changes removed from each).
4. Tags and branches are preserved but may need cleanup.

**GitHub Docs reference:** https://docs.github.com/en/get-started/using-git/splitting-a-subfolder-out-into-a-new-repository

**Alternative approach -- git subtree:**
```bash
# From the monorepo, push a subtree to a new remote
git subtree split --prefix=dbt_diagnostics -b dbt-diagnostics-split
git push new-remote dbt-diagnostics-split:main
```
Simpler but only works for a single contiguous subtree.

---

## Owner Preferences and Constraints

1. **Git history preservation is DESIRED** for all files with meaningful commit
   ancestry. The owner is unsure how to achieve this but wants it explored.
2. **No repo can break independently.** After separation, each repo must be
   independently buildable/testable with clear dependency declarations.
3. **The separation must be painstaking and safe.** No file can be removed from
   the monorepo until it's confirmed to exist in its target repo with history.
4. **The monorepo continues to work during migration.** This is not a big-bang
   cutover; it's incremental.
5. **Infrastructure toolkit should be reusable** across future Snowflake projects
   (not just artwork). Generic names, no artwork-specific hardcoding.
6. **dbt-diagnostics is already nearly independent** -- it just needs its config
   and fixtures decoupled from artwork-specific paths.
7. **The artwork project repo needs the toolkit as a dependency** (git submodule,
   script vendoring, or package reference -- the approach is YOUR decision to
   propose).
8. **Branch:** All work happens on `donkey-kong-sandbox`. Never push to `main`.
9. **Snowflake account:** `OBANOYY-MK07348`. No DDL changes during planning.

---

## Your Task: Create a Comprehensive Separation Plan

Produce a document at `docs/prompts/REPO_SEPARATION_PLAN.md` that covers:

### Required Sections:

1. **Executive Summary** -- What repos will exist, what each contains, and how
   they relate (dependency direction arrows).

2. **Detailed File Assignment** -- Every file in the monorepo assigned to exactly
   one target repo, with justification for borderline cases. Flag files that need
   refactoring before they can move (e.g., scripts with hardcoded artwork references).

3. **Dependency Contracts** -- How each repo depends on the others at runtime.
   Interface boundaries (env vars, config files, CLI conventions). What the
   "toolkit" exposes vs. what the "artwork project" consumes.

4. **Git History Strategy** -- Exact `git filter-repo` commands (or alternative)
   for each repo. Address: files that moved directories, shared commits,
   tags/branches. Include a validation step to confirm history integrity post-split.

5. **Migration Sequence** -- Ordered steps to execute the split safely. Include
   rollback procedures at each step. Address the "monorepo still works" constraint.

6. **Shared File Resolution** -- For each file used by multiple concerns (Makefile,
   requirements.txt, .env.example, AGENTS.md), decide: does it stay in the monorepo
   until the end? Does it get duplicated? Does it get split?

7. **Refactoring Prerequisites** -- Code changes needed BEFORE files can move.
   E.g., parameterizing hardcoded `artwork_pipeline` references in the toolkit,
   extracting `config.yml` defaults from dbt-diagnostics.

8. **Post-Separation Validation** -- How to confirm each repo works independently.
   Test commands, CI checks, dependency installation verification.

9. **Risk Registry** -- What can go wrong, probability, mitigation. Include:
   history loss scenarios, broken references, CI failures, developer workflow
   disruption.

10. **Open Questions** -- Decisions you're unsure about. Present 2-3 options for
    each with tradeoffs. The owner will decide.

### CRITICAL: Force Extended Thinking

At multiple points in your analysis, you MUST pause and consider alternative
approaches. Specifically:

- **Before deciding on repo boundaries:** Consider at least THREE different ways
  to partition the code (e.g., 2-repo split, 3-repo split, 4-repo split, keeping
  a monorepo with better boundaries). Write out tradeoffs for each.

- **Before choosing a history preservation method:** Compare `git filter-repo`,
  `git subtree split`, fresh-repo-with-squashed-history, and "keep monorepo +
  use symlinks/submodules." Explain when each is appropriate.

- **Before deciding how repos depend on each other:** Compare git submodules,
  git subtrees (vendored), published packages (pip/brew), and simple
  copy-on-release. Name real-world precedents for each approach.

- **Before deciding migration order:** Consider both "extract the smallest/cleanest
  first" and "extract the most independent first" strategies. Argue for your
  recommendation.

Do NOT create tunnel vision by committing to a single approach early. Present
the option space, then recommend with justification.

---

## Execution Protocol

1. **Start by reading this entire prompt.** (Checkpoint: echo "prompt read")
2. **Read `docs/context/file-map.md`** to confirm the file inventory is current.
3. **For each of the four concerns**, read 3 representative files to understand
   coupling depth, then checkpoint.
4. **Perform web searches** for:
   - `git filter-repo` multi-path extraction best practices
   - Monorepo-to-polyrepo migration patterns at scale
   - How open-source Snowflake toolkit projects structure their repos
   - Python package extraction from monorepo patterns
5. **Write the plan** to `docs/prompts/REPO_SEPARATION_PLAN.md`, checkpointing
   after each major section (write intermediate progress to
   `docs/prompts/SEPARATION_PROGRESS.md`).
6. **Self-review:** After the plan is complete, re-read it and check for:
   - Any file not assigned to a repo
   - Any circular dependency between repos
   - Any step that could cause data loss without rollback
   - Any hardcoded path that would break after the move

---

## What You May NOT Do

- Do NOT execute any git commands that modify history (this is planning only)
- Do NOT move, rename, or delete any files
- Do NOT modify any source code
- Do NOT apply any DDL to Snowflake
- Do NOT commit or push anything
- DO write planning documents only

---

## Line Counts for Reference (approximate)

| Area | Files | Lines |
|------|-------|-------|
| scripts/snowflake_cli/ | 15 | ~2,974 |
| scripts/lib/ | 5 | ~1,923 |
| scripts/ (root-level .sh) | 12 | ~1,800 |
| infrastructure/ | 29 | ~1,500 (est) |
| extraction/met/ | 12 | ~1,200 (est) |
| artwork_pipeline/ | 10+ | ~800 (est) |
| dbt_diagnostics/ | 30+ | ~4,000 (est) |
| tests/ | 6 | ~400 (est) |
| docs/ | 15+ | ~3,000 (est) |

---

## Success Criteria

The plan is complete when:

1. Every file in the repo has a target repo assignment
2. The dependency graph between repos is acyclic
3. `git filter-repo` commands are provided for each extraction
4. Migration can proceed incrementally (no big-bang required)
5. Each resulting repo has a clear README, test command, and install procedure
6. No artwork-specific strings remain in the generic toolkit
7. dbt-diagnostics can be pip-installed from its own repo without artwork-db
8. The artwork project can reference the toolkit without vendoring all of it
9. Risk mitigations exist for every identified failure mode
10. Open questions are clearly framed with options + tradeoffs for owner decision

---

## Reminder: Checkpoint Discipline

You will lose all work since your last tool call if the connection breaks.
Make tool calls CONSTANTLY:
- After reading 3 files -> checkpoint
- After making a design decision -> checkpoint
- After completing a section -> write it to disk
- When in doubt -> run `echo "checkpoint"` via bash

This is not optional. Treat connection breaks as inevitable, not exceptional.
