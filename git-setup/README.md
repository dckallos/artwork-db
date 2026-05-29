# Git setup scripts

These SQL files are the *only* scripts in this repo that depend on something
outside of Snowflake's view of the repo (you, with ACCOUNTADMIN credentials
and a local clone). They are applied with the Snowflake CLI (`snow sql`)
via the same `scripts/apply_sql.sh` wrapper as everything else, just driven
by `make bootstrap` (or `make iac`) instead of `make infra`.

## Why aren't these V### migration scripts?

The pipeline's normal migrations live in `infrastructure/` and are named
`V001__create_*.sql`, `V002__create_*.sql`, etc. These `B###` scripts are kept
separate because they are a one-time, ACCOUNTADMIN-only setup of the *optional*
in-Snowflake execution convenience: the `GIT REPOSITORY` object that lets you
run migrations from inside Snowflake via `EXECUTE IMMEDIATE FROM '@...'`.

Source version control (GitHub) already tracks every file independently of
Snowflake, so the `GIT REPOSITORY` object is NOT a change-tracking mechanism --
it is a convenience only, and the pipeline applies everything from the laptop
via `snow sql --filename` today. Per the 2026-05-29 design decision ("IaC Phase
Ordering + Role Model: Git mirror runs last") this Git-mirror layer is applied
LAST, AFTER core infrastructure (V then R). That ordering also resolves a
dependency: `B003__create_git_repository.sql` ends with
`GRANT READ ON GIT REPOSITORY artwork_db TO ROLE ARTWORK_ADMIN;`, and
`ARTWORK_ADMIN` is created by `infrastructure/V001__create_roles.sql`, so infra
must run first.

## Naming convention

| Prefix             | Meaning                                                         |
|--------------------|-----------------------------------------------------------------|
| `B###__create_*`   | Git-setup forward. Manual, one-time, ACCOUNTADMIN-only. OPTIONAL trailing Git-mirror layer -- runs LAST, AFTER V/R (not first). |
| `B###__drop_*`     | Git-setup rollback. Idempotent; safe pre-create. Dropped FIRST in teardown (before V###). |
| `V###__create_*`   | Versioned forward migration; run by `make infra` or `make iac`. |
| `V###__drop_*`     | Versioned rollback; run by `make rollback` or `make down`.      |
| `R###__*`          | Repeatable. Safe to re-run anytime. No paired drop.             |

## Execution order

Within this directory the three forward scripts always run in numeric order:

1. `B001__create_git_ops_db.sql`
2. `B002__create_api_integration.sql`
3. `B003__create_git_repository.sql`

But the git-setup (`B`) phase as a whole runs LAST in `make iac`, AFTER
infrastructure (`V` then `R`). `python scripts/bootstrap.py --phase all`
applies infra first, then git-setup, so the role hierarchy exists before
`B003` grants READ on the GIT REPOSITORY to `ARTWORK_ADMIN`.

### Prerequisite for standalone `make bootstrap`

`make bootstrap` (== `--phase bootstrap`) applies ONLY the `B` scripts and
presumes the role hierarchy already exists. `B003` grants READ on the GIT
REPOSITORY to `ARTWORK_ADMIN`, which is created by
`infrastructure/V001__create_roles.sql`. On a fresh account, run `make infra`
(or the all-in-one `make iac`) BEFORE `make bootstrap`, or `B003` fails with
`Role 'ARTWORK_ADMIN' does not exist or not authorized`. The standalone target
intentionally does NOT trigger infra so it stays a narrow, composable step;
`make iac` is the canonical fresh-account path.

After all three succeed, you can either:

- Continue applying migrations from your laptop via `make infra` (current
  default), or
- Apply them from inside Snowflake by `EXECUTE IMMEDIATE FROM
  '@ARTWORK_OPS.GIT.artwork_db/branches/main/infrastructure/V###__*.sql'`.

## Private repo?

`dckallos/artwork-db` is a **private** GitHub repo, so the SECRET path is the
default rather than an opt-in. The bind chain is split across the three
forward scripts:

1. `B001__create_git_ops_db.sql` creates `ARTWORK_OPS.GIT` and the
   `github_pat_artwork_db` SECRET. Its `PASSWORD` is the snow sql templating
   placeholder `<% github_pat %>`, substituted at apply time (see below).
2. `B002__create_api_integration.sql` whitelists that secret via
   `ALLOWED_AUTHENTICATION_SECRETS = (ARTWORK_OPS.GIT.github_pat_artwork_db)`.
3. `B003__create_git_repository.sql` binds it via
   `GIT_CREDENTIALS = ARTWORK_OPS.GIT.github_pat_artwork_db`.

No PAT is ever committed. The real fine-grained token (Contents: Read on
`dckallos/artwork-db`) lives only in a gitignored env file and is injected at
apply time via snow sql templating (`-D "github_pat=${GITHUB_PAT}"`). Setup is
single-pass: B001, B002, and B003 all succeed in one `make iac` run.

    cp git-setup/.env.example git-setup/.env
    # edit git-setup/.env and set GITHUB_PAT=<your fine-grained PAT>
    set -a; source git-setup/.env; set +a
    make iac

`git-setup/.env` is covered by the `.env` entry in `.gitignore`; only
`git-setup/.env.example` (committed with a blank `GITHUB_PAT=`) lives in git.
To rotate the PAT, update `git-setup/.env` and re-run `make iac` -- there is no
`ALTER SECRET` step. For a public repo you could drop the SECRET wiring, but the
default chain assumes private.

### Secret echo suppression (PAT safety)

`B001__create_git_ops_db.sql` renders the PAT into a `CREATE OR REPLACE SECRET`
statement at apply time. The Snowflake CLI echoes each rendered statement to
stdout, so an unguarded apply prints the PAT in cleartext (this happened on a
prior failed run, leaking the token to the terminal and chat scrollback). To
prevent recurrence, `scripts/bootstrap.py` flags any secret-bearing script and
`scripts/apply_sql.sh` discards its stdout (`SNOW_SUPPRESS_STDOUT=1`) while
preserving stderr for genuine errors. If a PAT was ever printed, treat it as
compromised: revoke and reissue the fine-grained token on GitHub (Contents:
Read on `dckallos/artwork-db`), update `git-setup/.env`, then re-run `make iac`.

snow sql templating reference:
[https://docs.snowflake.com/en/developer-guide/snowflake-cli/command-reference/sql-commands/sql](https://docs.snowflake.com/en/developer-guide/snowflake-cli/command-reference/sql-commands/sql)
