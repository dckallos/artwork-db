# Ingestion Platform Roadmap

This roadmap is tracked by GitHub issues #10 through #23.

## Foundation

1. #10 — Consolidate ingestion architecture docs and anti-patterns.
2. #11 — Build offline extraction and orchestration test harness foundation.
3. #23 — Resolve CMA placeholder/stub before source-contract validation if needed.

## Common ingestion core

4. #12 — Create typed `extraction/artwork_ingestion` P0 primitives.
5. #13 — Introduce shared Snowflake loader and ingestion manifests.
6. #14 — Extract reusable bulk download, cache, archive, and streaming primitives.
7. #15 — Extract reusable HTTP, auth, retry, and rate-limit primitives.

## Contracts and orchestration hardening

8. #16 — Add DDL, dbt source, and Dagster `produces` validation gates.
9. #17 — Improve Dagster source YAML schema, operator UX, and rate-limit configuration.
10. #18 — Harden dbt conformed layer and remove mart source hand-edits.

## Operations and proof sources

11. #19 — Expand CI and local doctor checks for local-first operations.
12. #20 — Add first new bulk-provider proof of concept using common primitives.
13. #21 — Implement Smithsonian S3-first source as a design stress test.

## Tracker

#22 is the roadmap index/tracker issue.

## Recommended implementation policy

Implement small, reviewable PRs. A slice can be split further if acceptance criteria are too broad for one PR.

Every PR should include:

- Summary.
- Current facts changed.
- Tests run.
- Risks and rollback.
- Confirmation that framework Python source-decoupling is preserved.
- Confirmation that no import-time side effects were introduced.

Do not present file changes in diff format in AI output.
