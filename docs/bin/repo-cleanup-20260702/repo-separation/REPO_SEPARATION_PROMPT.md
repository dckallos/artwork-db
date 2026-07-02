# Repository Separation: Design & Planning Prompt

Paste this entire file into a fresh Cortex Code or Claude context window.

---

## Your Role

You are a **Principal Software Engineer** (L7 Google / E7 Meta / L8 Amazon equivalent)
with deep expertise in repository architecture, build systems, and infrastructure-as-code
decomposition. You have shipped multi-repository extractions at scale for organizations
with interleaved infrastructure, application, and tooling code. Your standards:

- Clean ownership boundaries between repositories
- Zero broken imports/references after extraction
- Commit history preservation where feasible (via `git filter-repo`)
- Idempotent, scriptable extraction (someone else can reproduce it)
- No shared-file duplication without explicit interface contracts
- YAGNI: extract what exists, don't pre-architect what doesn't

You are making DESIGN DECISIONS in this session. The owner expects you to propose
multiple approaches with tradeoffs, force yourself to consider alternatives, and
justify your recommendations. The owner will approve or redirect before any execution.

---

## CRITICAL: Connection Break Resilience Protocol

Your context can be lost at any time due to Cortex Code connection breaks. The ONLY
way to preserve progress is to execute a tool call (bash command, file write, web
search). **YOU MUST execute a tool call after reviewing every 3 files.** This creates
a restoration checkpoint.

**Rules:**
- After reading 3 files, IMMEDIATELY run a trivial bash command (e.g.,
  `echo "checkpoint: reviewed X, Y, Z"` or `wc -l <next-file>`) BEFORE continuing.
- After completing each major section of analysis, write your findings to a progress
  file: `docs/context/repo-separation-progress.md`
- When making design decisions, write them IMMEDIATELY to the progress file before
  continuing to the next decision.
- Periodically run `ls` or `grep` commands even while reading -- these create
  restoration points.
- If resumed after a break, read `docs/context/repo-separation-progress.md` first
  to understand what was already decided, then continue from where it left off.
- A connection break with no tool call since the last checkpoint means ALL analysis
  since that checkpoint is LOST. Prevent this by never going more than 3 file reads
  without a tool call.

**Checkpoint pattern:**
```
Read file A -> Read file B -> Read file C -> TOOL CALL (checkpoint) -> continue
```

---

## Project Context (read this, do NOT re-read these files)

**Repository:** `artwork-db` (branch `donkey-kong-sandbox`, GitHub: dckallos/artwork-db)
**Account:** Snowflake `OBANOYY-MK07348` (locator EP21559, AWS_US_EAST_2)
**Purpose:** Learning project for Snowflake + dbt depth via a Medallion architecture
over museum artwork data (Met, planned: Cleveland, Art Institute of Chicago, Smithsonian).

The repo has grown organically and now contains FOUR distinct concerns entangled in one
Git repository:

1. **Snowflake IaC / CLI Framework** (domain-agnostic orchestration tooling)
2. **Artwork Project** (DDL + dbt + extraction -- artwork-specific)
3. **General Utilities** (scripts that could serve any Snowflake project)
4. **dbt-diagnostics** (independent Python CLI package, already self-contained)

The goal: separate these into individual repositories with clean ownership, preserving
commit history where possible, without breaking the working system.

---

## Current Directory Layout (authoritative -- do not re-scan)

```
artwork-db/                          # CURRENT MONOREPO ROOT
  AGENTS.md                          # Cortex Code instructions (artwork-specific)
  CLAUDE.md                          # Claude Code instructions (artwork-specific)
  LICENSE                            # Repo license
  Makefile                           # Orchestration targets (mixed concerns)
  .env.example                       # Artwork-specific env vars
  .gitignore                         # Mixed concerns
  requirements.txt                   # Artwork Python deps (references dbt_diagnostics)
  profiles.yml.example               # dbt profiles template (artwork-specific)
  setup-claude-code.sh               # Claude Code setup (artwork-specific)
  inject_failures.py                 # Test utility for dbt_diagnostics
  inject_failures.sh                 # Test utility for dbt_diagnostics
  
  infrastructure/                    # Snowflake DDL -- 14 create/drop pairs + refresh
    CLAUDE.md                        # Infrastructure-specific Claude instructions
    create_*.sql / drop_*.sql        # Artwork-specific Snowflake objects
    refresh_grants.sql
    
  scripts/                           # MIXED: framework + artwork-specific + utilities
    manifest.txt                     # Apply order (artwork-specific DDL list)
    orchestrate.sh                   # Legacy DDL orchestrator (artwork-bound paths)
    orchestrate_modern.sh            # Modernized DDL orchestrator (domain-agnostic)
    apply_sql.sh                     # Generic: runs `snow sql --filename`
    rollback_sql.sh                  # Generic: runs paired drop
    bootstrap.py                     # Privilege preflight (artwork role names)
    dbt_orchestrate.sh               # dbt lifecycle (artwork-bound)
    dbt_orchestrate_modern.sh        # dbt lifecycle modernized (domain-agnostic intent)
    check.sh                         # Generic utility: run read-only SQL
    checkpoint.sh                    # Generic utility: write pipeline checkpoint
    bootstrap_chmod.sh               # Generic utility: set +x permissions
    load_profile.sh                  # Profile loader (generic)
    status_profile.sh                # Profile status (generic)
    unload_profile.sh                # Profile unloader (generic)
    activate_mac.sh                  # Mac-specific activation (artwork-bound)
    executable_files.txt             # Chmod manifest (artwork-specific file list)
    secret_bearing.txt               # Secret-bearing file list (artwork-specific)
    git_mark_executable.sh           # Generic git utility
    lib/                             # FRAMEWORK (domain-agnostic)
      connection_resolver.sh         # 423 lines -- universal connection resolution
      dbt_orchestrator.sh            # 89 lines -- dbt orchestration framework
      ddl_orchestrator.sh            # 65 lines -- DDL orchestration framework
      framework_integration_test.sh  # 530 lines -- framework self-test
      legacy_comparison_test.sh      # 816 lines -- legacy vs modern comparison
    sql/                             # Ad-hoc check scripts (artwork-specific)
      checkpoint.sql
      show_active_sessions.sql
      show_admin_account_grants.sql
      show_pipeline_status.sql
      show_run_control.sql
    snowflake_cli/                   # CLI SETUP FRAMEWORK (partially generic)
      _lib.sh                        # 748 lines -- shared library (multi-account)
      setup.sh                       # 349 lines -- phased setup runner
      init_profile.sh                # 198 lines -- profile initialization
      new_account.sh                 # 151 lines -- new account bootstrap
      00_install_snowflake_cli.sh    # Generic
      01_init_snowflake_home.sh      # Generic
      02_generate_admin_keypair.sh   # Generic
      03_lock_config_permissions.sh  # Generic
      04_register_admin_public_key.sh # Generic (uses snow CLI)
      05_verify_admin_jwt.sh         # Generic
      06_setup_loader_keypair.sh     # Artwork-specific role names inside
      07_test_loader_connection.sh   # Artwork-specific connection name
      08_promote_admin_warehouse.sh  # Artwork-specific warehouse name
      09_setup_transformer_keypair.sh # Artwork-specific role names inside
      10_test_transformer_connection.sh # Artwork-specific connection name
      README.md
      
  extraction/                        # ARTWORK-SPECIFIC (Met Museum loader)
    __init__.py
    met/
      __init__.py
      CLAUDE.md
      README.md
      config.py                      # References artwork Snowflake objects
      run.py                         # CLI entry point
      csv_bootstrap.py
      snapshot_loader.py
      control_seeder.py
      control_enricher.py
      image_enricher.py
      db.py
      snowflake_uploader.py
      requirements.txt
      sql/                           # Met-specific SQL templates
      
  artwork_pipeline/                  # ARTWORK-SPECIFIC (dbt project)
    dbt_project.yml
    profiles.yml
    packages.yml
    README.md
    macros/
    models/
      staging/met/                   # stg_met__artworks, stg_met__artists, etc.
      
  git-setup/                         # ARTWORK-SPECIFIC (in-Snowflake Git mirror)
    README.md
    create_git_ops_db.sql
    create_api_integration.sql
    create_git_repository.sql
    drop_git_ops_db.sql
    drop_api_integration.sql
    drop_git_repository.sql
    operator/
    .env.example
    
  dbt_diagnostics/                   # INDEPENDENT PACKAGE (already self-contained)
    pyproject.toml                   # v0.5.0, installable
    __init__.py / __main__.py / main.py
    models.py / renderer.py / colors.py
    classifiers/ / tracers/ / enrichers/ / linters/
    templates/ / fixtures/ / tests/
    config.yml
    BUILD_PROMPT.md / LINEAGE_TRAIL_PLAN.md
    CHANGELOG.md / HANDOFF_PROMPT.md / HANDOFF_PROMPT_2.md
    
  operations/                        # ARTWORK-SPECIFIC (ad-hoc ops SQL)
    met_seed_enrichment_control.sql
    
  analysis/                          # ARTWORK-SPECIFIC (ad-hoc analysis SQL)
    met_snapshot_profile.sql
    
  tests/                             # MIXED: framework tests + integration tests
    __init__.py
    framework/
      unit/
        mocks/
        test_connection_resolver.sh
        test_orchestrate_modern.sh
    integration/
      test_multi_account_deployment.sh
    examples/
      basic_project_integration.sh
      
  docs/                              # MOSTLY ARTWORK-SPECIFIC
    context/                         # Session state, learning docs, playbooks
      session-3-progress-log.md
      cli-connection.md
      ddl-infrastructure.md
      extraction.md
      file-map.md
      engineering-playbook.md
      dbt-plan.md
      dbt-curriculum.md
      met-deepdive.md
      cortex-ai-agents-playbook.md
      connection-resilience.md
      track-d-resumable-agents.md
      track-d-checklist.md
      
  .claude/                           # Claude Code config (artwork-specific)
    settings.json
    commands/ (5 .md files)
    agents/ (3 .md files)
    hooks/
```

---

## Key Cross-Cutting Dependencies (CRITICAL -- review before deciding)

These are the entanglement points that make naive directory-based splitting dangerous:

### 1. Makefile references
The root `Makefile` calls into `scripts/orchestrate_modern.sh`, `scripts/snowflake_cli/setup.sh`,
`scripts/dbt_orchestrate.sh`, and `scripts/bootstrap_chmod.sh`. It passes `infrastructure/`
and `scripts/manifest.txt` as arguments. The Makefile itself is artwork-specific in its
targets but invokes domain-agnostic framework scripts.

### 2. scripts/lib/ framework vs scripts/snowflake_cli/
`orchestrate_modern.sh` sources `scripts/lib/connection_resolver.sh`. The snowflake_cli
scripts use their own `_lib.sh`. These are two different abstraction levels that both
relate to "Snowflake CLI operations" but don't share code.

### 3. .env consumption chain
`.env` is sourced by `scripts/orchestrate.sh` (for `GITHUB_PAT`), by
`scripts/dbt_orchestrate.sh` (for `DBT_*` vars), and by `extraction/met/config.py`
(via python-dotenv). Each consumer needs different vars but they read from the same file.

### 4. bootstrap.py (privilege preflight)
`scripts/bootstrap.py` (283 lines) reads `infrastructure/create_roles.sql` and
`infrastructure/create_grants.sql` to validate the privilege contract. It imports no
external deps (stdlib JSON + re only), but its logic is artwork-role-specific.

### 5. tests/framework/ vs tests/integration/
Framework tests (`test_connection_resolver.sh`, `test_orchestrate_modern.sh`) test the
domain-agnostic lib. Integration tests (`test_multi_account_deployment.sh`) test the
full artwork deployment. These belong in different repos.

### 6. dbt_diagnostics coupling
`dbt_diagnostics/` is already self-contained with its own `pyproject.toml`. The only
coupling points are: (a) `requirements.txt` in root mentions it, (b) `inject_failures.py`
and `inject_failures.sh` at root are test utilities for it, (c) it reads dbt artifacts
from `artwork_pipeline/target/` during development.

### 7. snowflake_cli scripts: generic vs artwork-specific
Scripts 00-05 are generic (install CLI, generate keys, verify JWT). Scripts 06-10
contain hardcoded artwork-specific role/connection names (ARTWORK_LOADER_SVC, etc.)
but the PATTERN is generic -- only the names are project-specific.

### 8. manifest.txt
`scripts/manifest.txt` lists artwork-specific DDL file paths. The CONCEPT of a manifest
is generic (and `orchestrate_modern.sh` accepts `--manifest` as a parameter), but this
specific file is artwork-bound.

---

## Candidate Repository Taxonomy (evaluate and refine)

This is a STARTING POINT for your analysis, not a prescription. You may merge, split,
rename, or restructure these as your analysis dictates.

| # | Candidate Repo Name | Primary Contents | Notes |
|---|---|---|---|
| 1 | `snowflake-iac-framework` | `scripts/lib/`, `scripts/orchestrate_modern.sh`, `scripts/apply_sql.sh`, `scripts/rollback_sql.sh`, `scripts/check.sh`, `scripts/checkpoint.sh`, `scripts/bootstrap_chmod.sh`, generic snowflake_cli scripts (00-05), `tests/framework/` | Domain-agnostic. Other projects consume it. |
| 2 | `artwork-db` (slimmed) | `infrastructure/`, `artwork_pipeline/`, `extraction/`, `git-setup/`, `operations/`, `analysis/`, `docs/`, `Makefile`, `.env.example`, artwork-specific snowflake_cli scripts (06-10), `scripts/manifest.txt`, `scripts/dbt_orchestrate.sh`, `scripts/bootstrap.py`, `scripts/sql/`, `AGENTS.md`, `CLAUDE.md`, `.claude/` | The artwork project. Depends on repo #1. |
| 3 | `dbt-diagnostics` | `dbt_diagnostics/` entire directory, `inject_failures.py`, `inject_failures.sh` | Already self-contained. |
| 4 | (maybe) `snowflake-cli-bootstrap` | `scripts/snowflake_cli/` entire directory | CLI setup suite. Could be part of #1 or standalone. |

---

## Open Questions You Must Resolve (with tradeoffs)

These are the design decisions this session must produce. For each, consider AT LEAST
two approaches and document the tradeoff before recommending one.

### Q1: How do downstream repos consume the framework?
Options to evaluate:
- **Git submodule** (pinned SHA, explicit update)
- **Git subtree** (merged history, no separate clone needed)
- **Package manager** (pip for Python bits, ???  for bash)
- **Template/scaffold** (copy once, diverge freely)
- **Monorepo with path-based CI** (don't actually split -- just enforce boundaries)

### Q2: How much history to preserve?
Options to evaluate:
- **Full history via `git filter-repo --path`** (each new repo gets only commits
  touching its files, but ALL of them)
- **Squash to a single "extraction" commit** (clean start, lose granular blame)
- **Hybrid** (preserve for high-churn files like _lib.sh, squash for trivial ones)
- Relevant tool: `git filter-repo` (successor to `git filter-branch`, vastly faster)
  - `git filter-repo --path scripts/lib/ --path scripts/orchestrate_modern.sh`
  - `git filter-repo --path-rename scripts/lib/:lib/` (restructure paths)
  - Reference: https://github.com/newren/git-filter-repo

### Q3: What is the interface contract between framework and project repos?
The artwork project currently hardcodes paths (`infrastructure/`, `scripts/manifest.txt`).
After separation, how does it reference the framework?
- Does the framework ship an executable entry point that takes `--ddl-dir` and `--manifest`?
- Does the project vendor the framework at a known relative path?
- Does the Makefile become the glue layer that knows both paths?

### Q4: Where do snowflake_cli scripts 06-10 live?
They are PATTERN-generic but VALUE-specific. Options:
- Keep in artwork repo with a dependency on `_lib.sh` from the framework
- Templatize them (framework ships a generator, project fills in role names)
- Split: `_lib.sh` + 00-05 in framework, 06-10 in project (with `source` path config)

### Q5: What about the .claude/ and AGENTS.md / CLAUDE.md files?
These are AI-assistant configuration. After split:
- Each repo gets its own CLAUDE.md tailored to its scope
- .claude/ settings stay with the artwork repo (or each repo gets one)
- AGENTS.md (session state) stays with artwork repo only

### Q6: Ordering -- what gets extracted first?
`dbt-diagnostics` is the obvious first extraction (already self-contained). But what
order for the others? Framework first (so artwork can immediately reference it)? Or
artwork cleanup first (identify exactly what's framework vs project)?

---

## Technical References for Implementation

### git filter-repo (the recommended tool)
- GitHub: https://github.com/newren/git-filter-repo
- Install: `pip install git-filter-repo` or `brew install git-filter-repo`
- Key commands:
  ```bash
  # Extract specific paths into a new repo (preserves commits touching those paths)
  git clone artwork-db artwork-db-framework
  cd artwork-db-framework
  git filter-repo --path scripts/lib/ --path scripts/orchestrate_modern.sh \
                  --path scripts/apply_sql.sh --path scripts/rollback_sql.sh \
                  --path tests/framework/
  
  # Rename paths during extraction (e.g., scripts/lib/ -> lib/)
  git filter-repo --path scripts/lib/ --path-rename scripts/lib/:lib/
  
  # Multiple --path flags = keep all matching paths
  # --path-rename can restructure the directory layout
  # Operates on a FRESH CLONE (refuses to run on original to prevent accidents)
  ```

### Snowflake documentation on multi-project CLI setup
- Connections: https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-connections
- Config files: connections defined in `~/.snowflake/connections.toml`, defaults in `config.toml`
- Multiple projects sharing one Snowflake CLI install: each project can specify
  `--connection NAME` at invocation; no global state collision.

### Owner Preferences (observed from codebase conventions)
- **ASCII-only** in all files (no smart quotes, em dashes, arrows)
- **UPPERCASE** Snowflake identifiers
- **Key-pair auth only** (no passwords anywhere)
- **Idempotent DDL**: `IF NOT EXISTS` for stateful, `OR REPLACE` for stateless
- **Manifest-driven apply order** (no numeric filename prefixes)
- **Paired create/drop** for every DDL file
- **Branch:** `donkey-kong-sandbox` (active design work), never push to `main` without sign-off
- **IaC principle:** every Snowflake object reproduced from scripts (no ClickOps)
- **Learning-first:** the build teaches concepts; over-engineering is discouraged
- **Explicit sign-off** required before any write or execution
- **make targets** are the primary user interface (not raw script invocations)
- **Dual filesystem:** workspace edits are NOT on Mac until owner syncs

---

## Deliverable: The Plan Document

Your output for this session is a comprehensive plan document written to:
`docs/context/REPO_SEPARATION_PLAN.md`

The plan must include:

1. **Resolved answers to Q1-Q6** with documented tradeoffs and recommendations
2. **Exact file-to-repo mapping** (every file in the current repo assigned to exactly
   one target repo, with justification for contested files)
3. **Extraction order** (which repo gets created first, second, etc.)
4. **Per-repo extraction script outline** (the `git filter-repo` commands + post-extraction
   fixups needed)
5. **Interface contracts** (how repo #2 references repo #1 after split)
6. **Migration checklist** (ordered steps, each independently verifiable)
7. **Risk register** (what could break, and how to detect/fix it)
8. **Files that MUST be duplicated** (with justification) vs files that must NOT be
9. **Post-extraction validation** (how to confirm nothing broke)

---

## Extended Thinking Triggers

At each of these points, STOP and force yourself to consider alternatives before
proceeding. Do NOT tunnel-vision on the first approach that seems reasonable:

- **Before assigning any file to a repo:** Ask "could this reasonably live in TWO
  repos? If so, which one OWNS it and which one CONSUMES it?"
- **Before recommending git submodules:** Consider the cognitive overhead for a solo
  developer on a learning project. Is the ceremony worth it?
- **Before splitting snowflake_cli/:** Consider whether the 00-10 numbered scripts
  are even the right abstraction post-split, or whether `setup.sh --phase` already
  provides the right entry point.
- **Before creating 4 repos:** Ask "would 2 repos (diagnostics + everything-else) be
  simpler and still achieve the separation goals?" What is ACTUALLY gained by
  extracting the framework separately when there is currently ONE consumer?
- **Before preserving all history:** Consider that a solo-developer learning project
  may not NEED granular blame on year-old commits. What is the actual cost of losing
  history vs the complexity of preserving it?

---

## Execution Protocol

1. **Read `docs/context/REPO_SEPARATION_PROMPT.md`** (this file) -- you're doing that now.
2. **Create `docs/context/repo-separation-progress.md`** immediately as your working
   scratchpad. Write initial timestamp + "starting analysis."
3. **Phase 1: Dependency Analysis** (read files in groups of 3, checkpoint after each group)
   - Group A: Makefile, orchestrate.sh, orchestrate_modern.sh
   - Group B: scripts/lib/connection_resolver.sh, scripts/lib/ddl_orchestrator.sh, scripts/lib/dbt_orchestrator.sh
   - Group C: scripts/snowflake_cli/_lib.sh, scripts/snowflake_cli/setup.sh, scripts/snowflake_cli/init_profile.sh
   - Group D: scripts/dbt_orchestrate.sh, scripts/dbt_orchestrate_modern.sh, scripts/bootstrap.py
   - Group E: extraction/met/config.py, extraction/met/run.py, dbt_diagnostics/pyproject.toml
   - **CHECKPOINT after each group** (write findings to progress file)
4. **Phase 2: Design Decisions** (answer Q1-Q6 with tradeoffs in progress file)
5. **Phase 3: Write the Plan** (consolidate into `REPO_SEPARATION_PLAN.md`)
6. **Phase 4: Self-Review** (re-read the plan, check for contradictions, missing files,
   broken references)

---

## Anti-Patterns to Avoid

- **Don't create a repo per directory.** Directories are an implementation detail;
  repos should map to deployment/ownership boundaries.
- **Don't duplicate shared code.** If two repos need `_lib.sh`, one owns it and the
  other consumes it -- never copy.
- **Don't break working `make` targets.** The plan must include a Makefile migration
  strategy that keeps `make iac` working throughout the transition.
- **Don't over-engineer the framework repo** for hypothetical future consumers. Today
  there is ONE consumer (artwork-db). Design for that, with a door open to grow.
- **Don't underestimate .env coupling.** The `.env` file is consumed by 3+ scripts
  and Python. After split, each repo needs to document WHICH vars it requires.
- **Don't forget the docs/context/ directory.** These are session-state files for
  AI assistants working on the artwork project -- they stay with artwork.

---

## Success Criteria

When the plan is complete, an engineer should be able to:
1. Read `REPO_SEPARATION_PLAN.md` and understand every file's destination
2. Execute the extraction in the documented order without ambiguity
3. Run `make iac` in the artwork repo after extraction and have it succeed
4. Run `pytest dbt_diagnostics/tests/ -v` in the diagnostics repo and have it succeed
5. Run framework tests in the framework repo and have them succeed
6. Understand how to add a NEW Snowflake project using the framework without touching
   the artwork repo
