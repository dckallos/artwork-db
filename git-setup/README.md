# Git setup scripts

ACCOUNTADMIN-only, one-time setup of the **optional** in-Snowflake Git mirror
(a `GIT REPOSITORY` object for `EXECUTE IMMEDIATE FROM '@...'`). These are the
only scripts that depend on something outside Snowflake's view of the repo (you,
with ACCOUNTADMIN creds + a local clone). Applied via `snow sql` through the same
`scripts/apply_sql.sh` wrapper as everything else, driven by `make bootstrap`.

> **Naming note (flag, not yet fixed):** this doc still uses `B###__`/`V###__`/
> `R###__` prefixes, but the on-disk files are unprefixed (`create_*.sql` /
> `drop_*.sql`). Reconciling the prefixes is the separately-gated V/R/B reword —
> out of scope here.

## Zero -> working

All three secrets the git-setup SQL templates need -- `github_pat`,
`github_oauth_client_id`, `github_oauth_client_secret` -- now come from your
**root `.env`** automatically. You do NOT pass `VARS=` by hand anymore; the
Makefile reads them (exported env wins, else straight from `.env`) and injects
only the keys that have a value.

```bash
cp .env.example .env                 # then fill GITHUB_PAT + GITHUB_OAUTH_CLIENT_ID/SECRET
make iac CONN=gn33397                 # runs infra (V->R) THEN git-setup (B); creds auto-injected
```

That is the whole flow. The two optional `source` steps below only matter for
*other* tooling (extraction / dbt), not for git-setup creds:

```bash
# (optional) export the Snowflake/dbt connection vars for extraction + dbt:
source ../snowflake-toolkit/load_profile.sh .env
# (optional, alternative) export EVERYTHING in .env into the shell:
set -a; source .env; set +a
```

> **Why `source load_profile.sh` is NOT enough on its own for git-setup:** the
> toolkit's `load_profile.sh` exports only a hard-coded list of 9 `SNOWFLAKE_*`
> / `DBT_SNOWFLAKE_*` vars -- it deliberately does **not** carry the GitHub PAT
> or OAuth creds. Relying on it alone left `OAUTH_CLIENT_ID`/`SECRET` empty and
> produced an inert MCP integration. The Makefile's `.env` auto-read (above)
> closes that gap, so `make iac` works whether or not you sourced anything.

**Credential precedence** (highest first): explicit `make ... VARS="..."`
(full override) > exported environment variable > value in `.env` (`ENV_FILE`).
An empty/unset key is omitted entirely -- empty creds are never injected.

Prereq: run `make infra` (or the all-in-one `make iac`) **first** -- the Git phase
runs LAST and grants READ on the repo to `ARTWORK_ADMIN`, which `create_roles.sql`
creates. Setup is single-pass: all forward scripts succeed in one run.

## Forward scripts (run in numeric order, LAST in `make iac`)

| Order | Script | Creates |
|---|---|---|
| 1 | `create_git_ops_db.sql` | `ARTWORK_OPS.GIT` DB/schema + `github_pat_artwork_db` SECRET (PAT via `<% github_pat %>`) |
| 2 | `create_api_integration.sql` | API integration; whitelists the secret (`ALLOWED_AUTHENTICATION_SECRETS`) |
| 3 | `create_git_repository.sql` | 3 `GIT REPOSITORY` objects -- `artwork_db`, `dbt_diagnostics`, `snowflake_toolkit` (all reuse the same integration + secret), FETCH, `GRANT READ … TO ROLE ARTWORK_ADMIN` |
| 4 | `create_mcp_integration.sql` | `GITHUB_MCP_INTEGRATION` API integration (OAuth via `<% github_oauth_client_id/secret %>`) + `GITHUB_MCP_SERVER` EXTERNAL MCP SERVER for Cortex Agents |

After these succeed, apply migrations either from your laptop (`make infra`,
current default) or from inside Snowflake:
`EXECUTE IMMEDIATE FROM '@ARTWORK_OPS.GIT.artwork_db/branches/main/infrastructure/V###__*.sql'`.

## Naming convention

| Prefix | Meaning |
|---|---|
| `B###__create_*` | Git-setup forward. Manual, one-time, ACCOUNTADMIN-only. OPTIONAL Git-mirror layer — runs LAST, after V/R. |
| `B###__drop_*` | Git-setup rollback. Idempotent; dropped FIRST in teardown (before V###). |
| `V###__create_*` / `V###__drop_*` | Versioned forward / rollback migration (`make infra` / `make rollback`). |
| `R###__*` | Repeatable; safe to re-run anytime; no paired drop. |

Why not V### migrations? GitHub already version-controls every file, so the
`GIT REPOSITORY` object is a convenience, not a change-tracking mechanism — hence
it is applied LAST and kept separate from `infrastructure/`.

<details>
<summary>Private-repo PAT handling &amp; secret-echo safety</summary>

`dckallos/artwork-db` is **private**, so the SECRET path is the default. The bind
chain is split across the three forward scripts: the SECRET (`create_git_ops_db`)
→ whitelist (`create_api_integration`, `ALLOWED_AUTHENTICATION_SECRETS`) → bind
(`create_git_repository`, `GIT_CREDENTIALS`).

- **No PAT in git.** The fine-grained token (Contents: Read) lives only in
  gitignored `git-setup/.env`, injected at apply time via `-D "github_pat=…"`.
  Only `git-setup/.env.example` (blank `GITHUB_PAT=`) is committed.
- **Rotate:** edit `git-setup/.env`, re-run `make iac` (no `ALTER SECRET` step).
- **Echo suppression:** the rendered `CREATE OR REPLACE SECRET` would print the
  PAT to stdout, so `scripts/bootstrap.py` flags secret-bearing scripts and
  `scripts/apply_sql.sh` discards their stdout (`SNOW_SUPPRESS_STDOUT=1`) while
  keeping stderr. **If a PAT was ever printed, treat it as compromised:** revoke
  + reissue on GitHub, update `git-setup/.env`, re-run `make iac`.
- For a public repo you could drop the SECRET wiring; the default assumes private.

snow sql templating:
<https://docs.snowflake.com/en/developer-guide/snowflake-cli/command-reference/sql-commands/sql>
</details>
