# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session-open ritual

1. ALWAYS read AGENTS.md first -- it's the cheapest read and tells you exactly how much more to read
2. Check docs/context/STATUS.md for volatile state if mentioned in AGENTS.md
3. Read ONLY the relevant Tier-1 domain doc for your task from docs/context/
4. Stop reading once you know enough to act

## Session-close ritual

Before signing off, every window MUST produce two artifacts (see AGENTS.md "Session-close ritual" for the full spec):

1. A final dated entry appended to `docs/context/session-3-progress-log.md` that supersedes any prior `End of this window` markers in the same date. Required sections: what changed this turn (workspace stage; applied-to-account yes/no; pushed-to-Mac yes/no), cumulative workspace state vs Mac, solo-session check result, first-action options for the next window, read-only verification queries, decision tree, deferred patches in priority order, MUST-NOT-DO foot-guns, the hand-off prompt block, and an explicit `End of this window` marker.
2. A paste-ready hand-off prompt as the last code block in that entry, fenced so the owner can copy it verbatim. The prompt MUST contain: reading order (AGENTS.md -> latest log entry only); solo-session SQL; dual-FS reminder; the gating rule (state the plan, wait for proceed + date); one-line project-context recap; and a closing instruction telling the new window to quote the latest `End of this window` header back to the owner before proposing its first action. Keep it under ~50 lines.

The hand-off prompt is tailored to where the project is at session-close, not boilerplate. Copy the prior session's prompt and edit only the parts that have changed.

## Core conventions (NEVER violate)

- ASCII-only everywhere (no smart quotes, em dashes, arrows)
- SQL in files only, UPPERCASE Snowflake identifiers
- Idempotency: IF NOT EXISTS for stateful, OR REPLACE for stateless
- Every create_*.sql has a paired drop_*.sql
- Apply order from scripts/manifest.txt only (no numeric prefixes)
- Key-pair auth only, no passwords
- Never push to main, never run destructive ops without sign-off
- One logical commit per unit of work

## Common commands

```bash
# IaC operations (safe)
make iac          # Apply all infrastructure + git-setup
make infra        # Apply infrastructure only
make bootstrap    # Apply git-setup only (requires infra first)
make rollback FILE=infrastructure/create_stages.sql  # Rollback one file

# Destructive operations (require sign-off)
make down         # Full teardown
make down FROM=create_stages  # Partial teardown

# Extraction (Met CLI takes SUBCOMMANDS, not --phase/--source)
# Current Snowflake-authoritative path (Option B):
python -m extraction.met.run snapshot       # Load full CSV into BRONZE.MET_CSV_SNAPSHOT
python -m extraction.met.run seed-control    # Seed bounded slice into MET_ENRICHMENT_CONTROL
python -m extraction.met.run enrich-met      # Drain worklist: fetch images, assemble Bronze
# Legacy SQLite path (superseded; kept in CLI only):
#   python -m extraction.met.run bootstrap|enrich|upload|all|status

# Ad-hoc checks (safe -- these live in the sibling snowflake-toolkit repo)
# Resolve via TOOLKIT_DIR (defaults to ../snowflake-toolkit)
bash ../snowflake-toolkit/check.sh  # Show active sessions
bash ../snowflake-toolkit/check.sh scripts/sql/show_pipeline_status.sql
bash ../snowflake-toolkit/checkpoint.sh <run_id> <step> [status] [note]  # Write checkpoint

# dbt (when artwork_pipeline/ exists)
make dbt-deps
make dbt-run
make dbt-test
```

## Architecture

**Medallion architecture**: Bronze (raw) -> Silver (cleaned) -> Gold (business-ready)

**Key components**:
- infrastructure/ -- Snowflake DDL (11 create/drop pairs)
- scripts/ -- Project-specific orchestration (manifest.txt, dbt_orchestrate.sh)
- extraction/met/ -- Met Museum OpenAccess loader (SQLite intermediate, Bronze target)
- artwork_pipeline/ -- dbt project (scaffolded; staging model stg_met__artworks exists)
- git-setup/ -- Optional in-Snowflake Git mirror (runs LAST)
- ../snowflake-toolkit/ -- Sibling repo: generic Snowflake CLI/IaC framework (TOOLKIT_DIR)

**Snowflake objects**:
- Account: OBANOYY-MK07348 (locator EP21559, AWS_US_EAST_2); admin PORCHFLAKE/ACCOUNTADMIN. Earlier trials pa37992 / HXCNOII-RS05429 (user PORCHANALYTICS) are RETIRED.
- Database: ARTWORK_DB with BRONZE/SILVER/GOLD schemas
- Roles: ARTWORK_ADMIN (owner), ARTWORK_LOADER, ARTWORK_TRANSFORMER (dbt runs as ARTWORK_TRANSFORMER_SVC assuming ARTWORK_TRANSFORMER)
- Service users (key-pair auth, TYPE=SERVICE): ARTWORK_LOADER_SVC (extraction -> Bronze), ARTWORK_TRANSFORMER_SVC (dbt -> Silver/Gold). Keys minted by `make loader|transformer CONN=<conn>`.
- Git repo: ARTWORK_OPS.GIT.ARTWORK_DB

**Connection flow**: make iac -> $(TOOLKIT_DIR)/orchestrate_modern.sh -> apply_sql.sh -> snow sql --filename

## Your role

Act as senior Data/Platform engineer mentor. Explain the why and tradeoffs, propose next learning steps, but owner decides and you honor it.

## Before making changes

1. Verify paths exist with LS tool
2. Read file with Read tool before editing
3. Check git status/branch
4. For SQL changes, ensure manifest.txt includes the file
5. For new files, update scripts/manifest.txt if it's DDL

## Active work

See AGENTS.md Status table and docs/context/met-deepdive.md for current state.
Branch: donkey-kong-sandbox (active design branch)