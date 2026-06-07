# Phase 3 Switchover Progress

## Commit 1: Wire Makefile to sibling toolkit
- [x] Item 1: transformer target -- already wired to $(TOOLKIT_DIR)
- [x] Item 2: rollback/down/down-from -- already wired to $(TOOLKIT_DIR)
- [x] Item 3: run_bootstrap define -- already wired to $(TOOLKIT_DIR)
- [ ] Item 4: Verify dry-run (make -n) -- REQUIRES MAC (see phase3_mac_script.sh)
- [ ] Item 5: Verify fail-fast guard -- REQUIRES MAC (see phase3_mac_script.sh)

## Commit 2: Remove extracted files
- [ ] Item 6: git rm toolkit files -- REQUIRES MAC (see phase3_mac_script.sh)
- [ ] Item 7: git rm dbt-diagnostics files -- REQUIRES MAC (see phase3_mac_script.sh)
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
- [ ] Item 10: Final validation -- REQUIRES MAC (see phase3_mac_script.sh)

## Summary

All workspace-possible work is DONE. The remaining items (4-7, 10) require
git and the sibling toolkit on disk -- run `docs/prompts/phase3_mac_script.sh`
from ~/dev/artwork-db on the Mac.

Files edited in this workspace session:
- docs/context/cli-connection.md
- docs/context/ddl-infrastructure.md
- docs/context/file-map.md
- docs/context/connection-resilience.md
- docs/context/track-d-checklist.md
- docs/context/track-d-resumable-agents.md
- docs/prompts/phase3_mac_script.sh (NEW -- Mac execution script)
- docs/prompts/PHASE3_PROGRESS.md (this file)
