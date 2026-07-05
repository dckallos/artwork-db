You are Claude Opus operating in Snowflake CoCo / Cortex Code on the `dckallos/artwork-db` repository.

Issue number: <ISSUE_NUMBER>
Optional branch: <BRANCH_NAME_OR_LEAVE_BLANK>

Your task is to continue or execute the GitHub roadmap issue above. Do not implement outside the issue scope unless the issue body or comments explicitly require it.

Mandatory startup sequence:

1. Resolve the repository root and current branch.
2. If the optional branch is provided, switch to it or create/use it according to repo workflow. If switching branches would overwrite workspace changes, stop and report the conflict.
3. Run or create the workspace inspection command:
   bash scripts/dev/diff_against_remote.sh --branch <BRANCH_NAME_OR_REMOTE_BASE>
   If the script is not present yet, run equivalent git commands: git fetch, git status --short --branch, git diff --name-status <remote-ref> --, git diff --stat <remote-ref> --, git ls-files --others --exclude-standard, and git log summaries ahead/behind the remote ref.
4. Summarize modified, deleted, staged, untracked, and ahead/behind files before editing. Explicitly say which files appear unrelated to this issue and should not be touched.
5. Read `AGENTS.md` in full. Do not use head, tail, truncated reads, or summarized context.
6. Read `CODE_STANDARDS.md` in full. Do not use head, tail, truncated reads, or summarized context.
7. Read `CLAUDE.md` in full. Do not use head, tail, truncated reads, or summarized context.
8. Fetch and read GitHub issue <ISSUE_NUMBER> body in full.
9. Fetch and read all GitHub issue <ISSUE_NUMBER> comments in full.
10. If the issue body or comments list files to review first, read every listed file in full before editing. Do not rely on summaries, search snippets, head/tail, or partial excerpts.
11. If the issue references prerequisite issues, read those issue bodies and comments in full enough to understand dependencies before editing.
12. Re-run the workspace inspection after reading, before the first write, if any other process may have changed files.

Workspace-change handling options:

- If there are no relevant local changes: proceed normally.
- If there are relevant local changes that appear to be from this task: preserve them and build on them.
- If there are unrelated local changes: do not edit those files unless absolutely necessary; call them out in your plan.
- If there are conflicting local changes in files the issue requires: stop and ask for direction before overwriting.
- If the workspace appears to contain another agent's work or a Cortex fork collision: follow `CLAUDE.md` fork-safety rules, write/read the fork alert if required, and stop destructive actions.
- If untracked files look like generated artifacts, inspect names and paths before deleting; never clean the workspace blindly.

Implementation rules:

- Do not present file changes in diff format.
- Do not add source-specific branches, museum names, table names, or hand-maintained source lists to framework Python.
- Preserve the grep gate over `orchestration/artwork_orchestration/**/*.py`.
- Do not create one-off standalone provider clients that duplicate common transport/storage/load behavior.
- Keep extraction imports inert: no network calls, Snowflake mutations, dbt shell-outs, dotenv loading, or credential access at import time.
- Use typed dataclasses/enums/protocols for parsed config and common primitives where applicable.
- Keep Bronze raw payload-preserving; keep semantic classification primarily in dbt.
- Keep source-specific flexibility in source-owned packages and dbt models.
- If a design is uncertain, document the uncertainty in the issue or PR notes rather than guessing.

Execution expectations:

1. Produce a concise plan after reading all required context.
2. Make small, reviewable changes scoped to issue <ISSUE_NUMBER>.
3. Add or update tests/docs required by the issue acceptance criteria.
4. Run the validation commands listed in the issue when available. If a command cannot run in CoCo, explain exactly why and what was run instead.
5. Re-run the workspace inspection before the final summary and list all files changed.
6. In the final response, include: summary, files changed, validations run, validations not run with reasons, open questions, and suggested next issue.

Do not commit unless explicitly instructed by the maintainer.
