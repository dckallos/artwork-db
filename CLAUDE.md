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

## Working style

- Small, reviewable changes sliced along the issue #6 phases. Don't refactor unrelated code.
- Never commit unless explicitly asked; never commit secrets.
- When intent is ambiguous or two designs conflict, ask a focused question rather than guess.
