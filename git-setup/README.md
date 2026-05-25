# Git setup scripts

These SQL files are the *only* scripts in this repo that depend on something
outside of Snowflake's view of the repo (you, with ACCOUNTADMIN credentials
and a local clone). They are applied with the Snowflake CLI (`snow sql`)
via the same `scripts/apply_sql.sh` wrapper as everything else, just driven
by `make bootstrap` (or `make iac`) instead of `make infra`.

## Why aren't these V### migration scripts?

The pipeline's normal migrations live in `infrastructure/` and are named
`V001__create_*.sql`, `V002__create_*.sql`, etc. Long-term, the goal is to
apply them from inside Snowflake via the `GIT REPOSITORY` object using
`EXECUTE IMMEDIATE FROM '@...'`.

But that requires the `GIT REPOSITORY` object to already exist, which in turn
requires an `API INTEGRATION` and a host database/schema, which in turn must
be created by something *outside* Snowflake (because Snowflake cannot see
this repo yet). That is the chicken-and-egg these scripts solve.

## Naming convention

| Prefix             | Meaning                                                         |
|--------------------|-----------------------------------------------------------------|
| `B###__create_*`   | Git-setup forward. Manual, one-time, ACCOUNTADMIN-only.         |
| `B###__drop_*`     | Git-setup rollback. Idempotent; safe pre-create.                |
| `V###__create_*`   | Versioned forward migration; run by `make infra` or `make iac`. |
| `V###__drop_*`     | Versioned rollback; run by `make rollback` or `make down`.      |
| `R###__*`          | Repeatable. Safe to re-run anytime. No paired drop.             |

## Execution order

Driven by `python scripts/bootstrap.py` (which shells out to
`scripts/apply_sql.sh`), in numeric order:

1. `B001__create_api_integration.sql`
2. `B002__create_git_ops_db.sql`
3. `B003__create_git_repository.sql`

After all three succeed, you can either:

- Continue applying migrations from your laptop via `make infra` (current
  default), or
- Apply them from inside Snowflake by `EXECUTE IMMEDIATE FROM
  '@ARTWORK_OPS.GIT.artwork_medallion_pipeline/branches/main/infrastructure/V###__*.sql'`.

## Private repo?

If `artwork-medallion-pipeline` is a **private** GitHub repo, you must also
create a `SECRET` holding a GitHub PAT (or fine-grained token with
`Contents: Read`) before running `B001`. The PRIVATE REPO ONLY block in
`B001` documents exactly how. Leave it commented out for a public repo.