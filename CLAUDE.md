# CLAUDE.md

Guidance for Claude-based coding agents (Cortex Code / Claude Code) in **artwork-db**.
This file is intentionally short. The canonical rules live in **`AGENTS.md`** (read first)
and **`CODE_STANDARDS.md`** (the engineering bar) — this file only pins the things that are
most often missed and points you at the rest.

## Read order (do this before writing any code)

1. `AGENTS.md` — the prime directive and non-negotiables.
2. `CODE_STANDARDS.md` — full engineering standards.

> **If either file's contents were elided/summarized in your context** (e.g. "edited out to
> manage context size"), **re-read the file in full before editing.** Do not write code
> against a summary — the specifics (below) live in the details that get elided.

## Rules that are easy to get wrong (get these right the first time)

- **Docstring format (differs from the PEP 257 / formatter default).** Triple quotes go on
  their **own line** at both the open and the close — one-liners included. See `AGENTS.md`
  → Non-negotiables for the good/bad example. Before you push, run:
  `python3 scripts/normalize_docstrings.py --check` (add `--write` to auto-fix files you touched).
- **Prime directive — no source identifiers in framework `.py`.** Behavior is configured in
  YAML (`framework.yaml` + `sources/*.yaml`), never hardcoded. The grep gate must stay at 0:
  `\b(met|aic|cma)\b|metropolitan|art institute|chicago|cleveland`. Museum names ARE allowed
  in `tests/` and config, never in `orchestration/artwork_orchestration/**/*.py`.
- **Config is data; one home for a fact.** New knobs → YAML + typed model (`model.py`) +
  loader validation. Never a second hardcoded copy that can drift.
- **No import-time side effects; tests ship with the change.** See `CODE_STANDARDS.md` §3, §7.

## Validate before you claim done

```bash
python3 -m py_compile <changed .py>                      # syntax
python3 scripts/normalize_docstrings.py --check          # docstring house style
env PYTHONPATH= pytest orchestration/tests               # suite (CI clears PYTHONPATH)
bash scripts/orchestration/doctor_orchestration.sh       # import/env health
```

Re-run the grep gate and confirm **0** hits in framework `.py`.

## Session continuity & Cortex fork awareness (MANDATORY)

A connection break can silently spawn a **forked agent** that resumes mid-task. Two forks
editing the same files — the "Cortex fork" hazard — is the most destructive failure mode in
this repo; it has already happened (see `session-progress-log.md`: fork-39b1c4 vs an unlogged
"Fork B" clobbered each other's registry refactor). Defend against it **every** session:

- **Mint a unique fork id at startup** (e.g. `fork-<6 hex>`) and prefix every log line with it:
  `[fork-ab12cd][<UTC ISO8601>] <message>`. Never reuse another session's id.
- **Append to `session-progress-log.md` via a `bash` call after every meaningful action**
  (a write, a delete, a validation, a decision). A `bash` tool call is a durable checkpoint —
  process state is preserved up to that call — and the log is the *only* channel a parallel
  fork can see. Small, frequent entries beat one end-of-task summary.
- **Read the log tail before each append.** If a **different** fork id appears — or you see
  files/mtimes you did not create — a parallel Cortex fork is live. **STOP** and reconcile
  (inform the maintainer) *before* any destructive action (delete / overwrite / `--apply`).
- **`.fork-alert` stop-signal — check it OFTEN (before EVERY write, delete, `--apply`, and log
  append).** The instant you detect a collision (a foreign fork id in the log, or an on-disk
  file/mtime you did not create), **write a `.fork-alert` file at the repo root** containing a
  one-line summary plus the surviving fork id, e.g.
  `fork-7d3e91 AUTHORITATIVE — collision on tools/github/tests/unit/test_secrets.py at
  <UTC ts>; all OTHER forks HALT`. Every fork must **read `.fork-alert` before any mutating
  action**: if it exists and names a *different* surviving fork, **stop all work immediately**,
  do not write/delete/apply, and inform the maintainer. The surviving (authoritative) fork
  deletes `.fork-alert` only once the collision is fully reconciled.
- **Trust disk over your context.** Prior forks may have advanced files beyond what your
  context shows (tool reads can return stale/elided snapshots). **Re-read a file in full
  immediately before editing it**; never assume your context matches disk. This applies to
  already-"done" work (e.g. Area A): verify on-disk state, don't rebuild from memory.
- **Prefer `web_search` over stale memory** for anything external (GitHub REST/Actions syntax,
  `gh` flags, actionlint/shellcheck); verify current docs, then cite sources.

Append pattern (workspace FS lacks `O_APPEND`; `sed -i` fails on rename — use read-rewrite).
If `bash` is restricted to non-mutating commands mid-session, fall back to the edit tool but
keep the read-then-append discipline:

```bash
FORK=fork-ab12cd; TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 - "$FORK" "$TS" <<'PY'
import sys, pathlib
fork, ts = sys.argv[1], sys.argv[2]
p = pathlib.Path("session-progress-log.md")
p.write_text(p.read_text() + f"[{fork}][{ts}] REPLACE-with-what-just-happened\n")
PY
```

## Sandbox gotchas (learned in Area A)

- The workspace `/workspace` symlink can **remount to a new stage path** mid-session. Resolve
  `ROOT=$(pwd -P)` and use absolute paths; if a file tool says "not found", re-resolve.
- pytest: run `PYTHONDONTWRITEBYTECODE=1 /usr/sbin/pytest ... -p no:cacheprovider` (bytecode
  writes hit an I/O error on the stage FS). CI clears `PYTHONPATH`; in this sandbox `pluggy`
  lives on the ambient `PYTHONPATH`, so run locally with it intact.
- `bash scripts/orchestration/doctor_orchestration.sh` **FAILs in a bare sandbox** (no venv /
  no `dagster` install) — that is an env limitation, not a regression. It is green only where
  `pip install -e orchestration` has run.

## Working style

- Small, reviewable changes sliced along the issue #6 phases. Don't refactor unrelated code.
- Never commit unless explicitly asked; never commit secrets.
- When intent is ambiguous or two designs conflict, ask a focused question rather than guess.
