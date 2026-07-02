# Tier 1 — Workflow 1: CLI connection / auth bootstrap

Self-contained summary. You should be able to act on auth/connection tasks from
this doc alone. Escalate to source only via the triggers at the bottom.

## Entry point & shape

- **`$(TOOLKIT_DIR)/snowflake_cli/setup.sh`** (sibling `snowflake-toolkit` repo)
  — single entry point, `--phase` flag:
  `prereq | admin | loader | promote | all`. It chmods child scripts, then runs
  the numbered `00`–`10` scripts in order. Phases map to trust boundaries:
  `prereq` (local only) → `admin` (Snowflake-side, one password use) →
  `make iac` (creates objects) → `promote` → `loader` → `transformer`.
- **`$(TOOLKIT_DIR)/snowflake_cli/_lib.sh`** — shared helpers. **Sourced, not executed.**
  Relies on `${VAR:-}` for `set -u` safety. Key helpers:
  `resolve_admin_account/user/warehouse`, `parse_toml_value`,
  `replace_toml_value_in_section` (atomic connections.toml edit),
  `verify_admin_jwt_full` (3-step JWT check), `resolve_admin_password_interactive`.
- Numbered scripts each set `set -euo pipefail`.

## Auth model (the core idea)

- **Password auth is used exactly once** — `04_register_admin_public_key.sh`, with
  `--temporary-connection` + `--authenticator snowflake`, to register the admin
  RSA public key. The `--temporary-connection` (`-x`) flag builds the connection
  purely from CLI flags so the CLI doesn't reject the password path because
  `[admin]` (in connections.toml) already references a `private_key_path`.
- **Everything afterward is SNOWFLAKE_JWT key-pair auth** via `-c admin`.
- Admin password is **never written to disk** — env var → else interactive
  `read -rs`. Needed 1–3×/year (bootstrap + rotations).
- Non-secrets (account, user, warehouse) are parsed from
  `~/.snowflake/connections.toml` with env-var override ("zero-export" design).
  (`default_connection_name` + `[cli.*]` remain in `config.toml`.)
- **Loader** (`ARTWORK_LOADER_SVC`) uses a rotated password persisted to `.env`,
  consumed by BOTH the extractor and the snow `loader` connection via env-var
  precedence — deliberately at-rest because two consumers share it.

## Numbered-script map

| # | Script | Role |
|---|---|---|
| 00 | install_snowflake_cli | brew/pipx install; idempotent skip if `snow` present |
| 01 | init_snowflake_home | `~/.snowflake/{keys,logs}`, dirs chmod 700 |
| 02 | generate_admin_keypair | PKCS#8 unencrypted `.p8` (600) + `.pub` (644); refuse overwrite unless `OVERWRITE_ADMIN_KEY=1` |
| 03 | lock_config_permissions | chmod 600 config.toml + connections.toml + private key |
| 04 | register_admin_public_key | **only password-auth call**; `ALTER USER … SET RSA_PUBLIC_KEY` |
| 05 | verify_admin_jwt | `verify_admin_jwt_full` against current admin warehouse |
| 06 | setup_loader_keypair | generate loader key-pair (lazy) → register pubkey via admin JWT → upsert `[loader]` (connections.toml) to SNOWFLAKE_JWT |
| 07 | test_loader_connection | `snow connection test -c loader` (key-pair; no `.env`/password) |
| 08 | promote_admin_warehouse | verify ARTWORK_WH exists → rewrite connections.toml warehouse → re-verify JWT |

## Conventions to carry forward

- Heavy header banners: purpose, zero-export resolution order, idempotency note,
  paired rollback, optional env. `==>` progress echoes.
- `snow sql --filename <f> --variable k=v --enhanced-exit-codes`; SQL templates use
  `<% var %>` substitution (the current CLI syntax; migrated 2026-06-01 from the
  deprecated `&{ var }`). **Credentials only via runtime `--variable`, never
  literals in `.sql`.**
- Strict perms: `~/.snowflake` & `keys` → 700; `config.toml`, `connections.toml` & `.p8` → 600; `.pub` → 644.
- Atomic config edits: timestamped `.bak`, temp file same dir, `mv`, re-chmod 600,
  section-scoped (other connections untouched).
- DRY: `verify_admin_jwt_full` reused by both `05` and `08`.
- Exit codes follow sysexits: 64 usage, 66 missing file, 70 internal, 78 config.

## Known gaps (fix candidates)

1. **Loader auth → KEY-PAIR + `TYPE = SERVICE` (APPLIED + VERIFIED 2026-05-31 via
   `make iac`, branch `donkey-kong-sandbox`).** The old empty `rotate_loader_password.sql`
   + `06_rotate_loader_password.sh` are **deleted**. `ARTWORK_LOADER_SVC` is now
   `TYPE = SERVICE` with `PASSWORD = null` (confirmed by `DESCRIBE USER`): password auth
   is dead, key-pair is the only way in. `06_setup_loader_keypair.sh` mints the
   loader key, registers it via the admin JWT connection
   (`git-setup/operator/register_loader_public_key.sql`), and upserts
   `[loader]` (in connections.toml) to SNOWFLAKE_JWT; `snow connection test -c loader` = OK.
   Python + `.env.example` moved to `SNOWFLAKE_PRIVATE_KEY_FILE`.
   **Learning note:** `CREATE USER IF NOT EXISTS` could not convert the pre-existing
   PERSON user, so the file appends idempotent `ALTER USER … SET TYPE = SERVICE; UNSET
   PASSWORD` to *converge*. See `met-deepdive.md` `AUTH-01`.
2. **`profiles.yml.example` uses `env_var()`** — valid for local dbt, but
   **incompatible with Snowflake-native dbt projects** (no env vars inside
   Snowflake). Matters when designing the CLI-driven production version.

## Multi-account (added 2026-06-01)

The suite manages a **connection pair** (admin + loader) per Snowflake account.
By default that pair is named `admin` / `loader` (unchanged), but both names are
parameterized so a SECOND account can be onboarded without collisions.

- **Selectors on `setup.sh`:** `--profile LABEL` (sugar → admin conn `LABEL`,
  loader conn `LABEL_loader`) or explicit `--admin-conn NAME` / `--loader-conn NAME`.
  No flags = `admin` / `loader`.
- **Key files derive from the connection name** (`_lib.sh` `admin_key_path` /
  `loader_key_path`): default → historical `admin_rsa_key.p8` / `loader_rsa_key.p8`;
  `--profile clientb` → `clientb_rsa_key.p8` / `clientb_loader_rsa_key.p8`. Two
  accounts never share a key.
- **`_lib.sh` is connection-name-aware:** `SNOW_LIB_ADMIN_CONN` / `SNOW_LIB_LOADER_CONN`
  (exported by `setup.sh`) drive `resolve_admin_*`, `verify_admin_jwt_full`, and the
  loader/promote scripts; `validate_conn_name` restricts names to `[A-Za-z0-9_-]+`
  (safe as a TOML bare key and `snow -c` arg).
- **Inspect / switch (local-only, no account writes):**
  - `setup.sh --phase list` → `list_connections`: prints every connection in
    connections.toml and marks `default_connection_name` (read from config.toml).
  - `setup.sh --profile LABEL --phase switch` → `set_default_connection`: repoints
    `default_connection_name` (timestamped backup, chmod 600).
- **Onboard a 2nd account end-to-end:**
  `setup.sh --profile clientb --phase all`, then (targeting that account)
  `make iac CONN=clientb` (Makefile threads `CONN` into the sibling toolkit `--connection`
  through `iac`/`infra`/`bootstrap`/`down`/`down-from`/`rollback`; default `admin`),
  then `--profile clientb --phase promote` / `--phase loader`.

## When to escalate to full source

- Editing a script's logic → open that one file.
- Need exact awk/TOML-rewrite implementation → open `_lib.sh`.
- Reproducing/debugging the private-repo bind chain → open
  `git-setup/create_api_integration.sql` (+ `create_git_ops_db.sql`,
  `create_git_repository.sql`).
- Anything else → trust this summary.
