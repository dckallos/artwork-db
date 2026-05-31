# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session-open ritual

1. ALWAYS read AGENTS.md first -- it's the cheapest read and tells you exactly how much more to read
2. Check docs/context/STATUS.md for volatile state if mentioned in AGENTS.md
3. Read ONLY the relevant Tier-1 domain doc for your task from docs/context/
4. Stop reading once you know enough to act

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

# Extraction
python -m extraction.met.run --phase all  # Run Met extraction
python -m extraction.met.run --phase bootstrap  # Download CSV only
python -m extraction.met.run --phase enrich     # API enrichment
python -m extraction.met.run --phase upload     # Upload to Bronze

# Ad-hoc checks (safe)
scripts/check.sh  # Show active sessions
scripts/check.sh scripts/sql/show_pipeline_status.sql
scripts/checkpoint.sh <run_id> <step> [status] [note]  # Write checkpoint

# dbt (when artwork_pipeline/ exists)
make dbt-deps
make dbt-run
make dbt-test
```

## Architecture

**Medallion architecture**: Bronze (raw) -> Silver (cleaned) -> Gold (business-ready)

**Key components**:
- infrastructure/ -- Snowflake DDL (11 create/drop pairs)
- scripts/ -- Orchestration layer (manifest.txt defines apply order)
- extraction/met/ -- Met Museum OpenAccess loader (SQLite intermediate, Bronze target)
- artwork_pipeline/ -- dbt project (not yet created)
- git-setup/ -- Optional in-Snowflake Git mirror (runs LAST)

**Snowflake objects**:
- Account: pa37992 (trial)
- Database: ARTWORK_DB with BRONZE/SILVER/GOLD schemas
- Roles: ARTWORK_ADMIN (owner), ARTWORK_LOADER, ARTWORK_TRANSFORMER
- Service user: ARTWORK_LOADER_SVC (key-pair auth)
- Git repo: ARTWORK_OPS.GIT.ARTWORK_DB

**Connection flow**: scripts/orchestrate.sh -> apply_sql.sh -> snow sql --filename

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