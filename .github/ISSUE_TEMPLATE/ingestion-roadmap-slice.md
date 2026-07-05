# Roadmap Slice: <title>

## Purpose

Describe the concrete outcome of this slice and why it comes now.

## Architectural direction to preserve

- Source-decoupled Dagster framework.
- Typed, composable Python.
- Inert imports.
- Raw Bronze payload preservation.
- dbt-owned semantic conformance.
- Local-first execution.

## Prerequisites and related issues

- List prerequisite issue numbers.
- Say whether overlap with #6 exists.

## Files to review before editing

- `AGENTS.md`
- `CODE_STANDARDS.md`
- Add all relevant source/dbt/DDL/Dagster/script/doc files.

## Files likely authored or modified

- List expected files and directories.

## Required design

- Describe the intended implementation shape.
- Distinguish source-specific code from reusable common code.
- Identify typed models/protocols/services expected.

## Implementation guidance

- Include repo-specific style and safety guidance.
- State what must not be done.

## Uncertainties to resolve

- List decisions the implementer must answer before or during implementation.

## Acceptance criteria

- List concrete completion checks.

## Validation commands

- `python -m py_compile ...`
- `pytest ...`
- `ARTWORK_SKIP_DBT_PREPARE=1 pytest orchestration/tests`
- `dbt parse`/`dbt compile` where relevant.
- Grep gate where framework Python is touched.

## Out of scope

- List related but deferred work.

## Rollback notes

- Explain how to revert safely or disable the new behavior.
