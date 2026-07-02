# Phase 3 Switchover Progress

## Commit 1: Wire Makefile to sibling toolkit
- [x] Item 1: transformer target -- already wired to $(TOOLKIT_DIR)
- [x] Item 2: rollback/down/down-from -- already wired to $(TOOLKIT_DIR)
- [x] Item 3: run_bootstrap define -- already wired to $(TOOLKIT_DIR)
- [x] Item 4: Verify dry-run (make -n) -- PASSED on Mac 2026-06-07
- [x] Item 5: Verify fail-fast guard -- PASSED on Mac 2026-06-07

## Commit 2: Remove extracted files
- [x] Item 6: git rm toolkit files (168 files removed)
- [x] Item 7: git rm dbt-diagnostics files
- [x] Item 8: Update .env.example if needed -- ALREADY CORRECT (no changes needed)
- [x] Item 9: Update remaining references (docs/context/*.md)
  - [x] cli-connection.md: scripts/snowflake_cli/ -> $(TOOLKIT_DIR)/snowflake_cli/
  - [x] ddl-infrastructure.md: apply_sql.sh, rollback_sql.sh, bootstrap.py, bootstrap_chmod.sh, check.sh
  - [x] file-map.md: section header + check.sh/checkpoint.sh + scripts/ table rewritten
  - [x] connection-resilience.md: check.sh, checkpoint.sh, sql/show_*.sql refs
  - [x] track-d-checklist.md: check.sh, checkpoint.sh
  - [x] track-d-resumable-agents.md: check.sh, checkpoint.sh
  - [x] claude-code-playbook.md: already updated (prior session or workspace state)
  - [x] CLAUDE.md: already correct (references ../snowflake-toolkit/)
- [x] Item 10: Final validation -- PASSED on Mac 2026-06-07

## Phase 4 cleanup (2026-06-07)
- [x] AGENTS.md: added repo-separation note to Roadmap, fixed setup.sh reference,
      updated orchestration-internals line, fixed apply_sql.sh:38 gated item
- [x] CLAUDE.md: added ../dbt-diagnostics/ to Architecture key-components
- [x] requirements.txt: updated dbt-diagnostics install comment to point at sibling
- [x] file-map.md: fixed stale show_active_sessions brace expansion (line 18)

## Status: COMPLETE
Both commits landed on donkey-kong-sandbox on Mac. Phase 4 doc updates done in workspace.
