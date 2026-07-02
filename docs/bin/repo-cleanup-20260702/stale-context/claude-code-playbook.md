# Claude Code Playbook

Quick reference for optimal Claude Code usage in artwork-db.

## Model and context strategy

- **Model**: Use Opus for complex work, Haiku for simple queries
- **Context window**: Start fresh sessions for new domains (extraction vs DDL)
- **Token efficiency**: Follow AGENTS.md reading protocol religiously
- **/reset** when switching between major tasks to avoid context pollution

## Prompting patterns for this repo

```bash
# Good: Specific, references conventions
"Add a new Bronze table for Cleveland Museum data following our idempotency split"

# Better: Includes acceptance criteria
"Add Bronze table for CMA data. Must: 1) IF NOT EXISTS, 2) paired drop script, 3) update manifest"

# Best: Contextual with next steps
"Following the Met pattern, add CMA Bronze tables. Check met-deepdive.md IMG-02 decision first"
```

## When to use plan mode

Use `/plan` for:
- Multi-file changes (>3 files)
- New data source integration
- Architecture decisions
- Complex refactoring

Skip plan mode for:
- Single file edits
- Simple SQL additions
- Documentation updates
- Bug fixes

## Git and PR discipline

1. **Always work on branches**: donkey-kong-sandbox or feature branches
2. **Commit messages**: One logical unit, reference the why
3. **PR workflow**: Use `/apply-iac --check` first, then create PR with gh CLI
4. **Never direct push**: Always PR, even for trivial changes

## Cost awareness

- **Expensive operations**: Full directory reads, repeated file parsing
- **Cheap operations**: AGENTS.md reads, focused grep/glob, SQL execution
- **Cache awareness**: Claude Code caches files for 15 minutes
- **Session hygiene**: Close sessions when done, don't leave idle

## Daily ritual checklist

Start of session:
- [ ] Read AGENTS.md fully
- [ ] Check current branch: `git status`
- [ ] Review Status table for your domain
- [ ] Run `$(TOOLKIT_DIR)/check.sh` for system state

During work:
- [ ] Update STATUS.md after completing items
- [ ] Run `make infra` after DDL changes
- [ ] Check manifest.txt updated for new SQL
- [ ] Commit with meaningful messages

End of session:
- [ ] Update AGENTS.md Status if needed
- [ ] Document decisions in met-deepdive.md
- [ ] Note any blocked items
- [ ] `/checkpoint` for resumable work