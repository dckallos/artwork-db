# Tier 1 — Workflow 1: CLI connection / auth bootstrap

Self-contained summary. You should be able to act on auth/connection tasks from
this doc alone. Escalate to source only via the triggers at the bottom.

## Entry point & shape

- **`scripts/snowflake_cli/setup.sh`** — single entry point, `--phase` flag:
  `prereq | admin | loader | promote | all`. It chmods child scripts, then runs
  the numbered `00`–`08` scripts in order. Phases map to trust boundaries:
  `prereq` (local only) → `admin` (Snowflake-side, one password use) →
  `make iac` (creates objects) → `promote` → `loader`.
- **`scripts/snowflake_cli/_lib.sh`** — shared helpers. **Sourced, not executed.**
  Relies on `${VAR:-}` for `set -u` safety. Key helpers:
  `resolve_admin_account/user/warehouse`, `parse_toml_value`,
  `replace_toml_value_in_section` (atomic config.toml edit),
  `verify_admin_jwt_full` (3-step JWT check), `resolve_admin_password_interactive`.
- Numbered scripts each set `set -euo pipefail`.

## Auth model (the core idea)

- **Password auth is used exactly once** — `04_register_admin_public_key.sh`, with
  `--temporary-connection` + `--authenticator snowflake`, to register the admin
  RSA public key. The `--temporary-connection` (`-x`) flag builds the connection
  purely from CLI flags so the CLI doesn't reject the password path because
  `[connections.admin]` already references a `private_key_file`.
- **Everything afterward is SNOWFLAKE_JWT key-pair auth** via `-c admin`.
- Admin password is **never written to disk** — env var → else interactive
  `read -rs`. Needed 1–3×/year (bootstrap + rotations).
- Non-secrets (account, user, warehouse) are parsed from
  `~/.snowflake/config.toml` with env-var override ("zero-export" design).
- **Loader** (`ARTWORK_LOADER_SVC`) uses a rotated password persisted to `.env`,
  consumed by BOTH the extractor and the snow `loader` connection via env-var
  precedence — deliberately at-rest because two consumers share it.

## Numbered-script map

| # | Script | Role |
|---|---|---|
| 00 | install_snowflake_cli | brew/pipx install; idempotent skip if `snow` present |
| 01 | init_snowflake_home | `~/.snowflake/{keys,logs}`, dirs chmod 700 |
| 02 | generate_admin_keypair | PKCS#8 unencrypted `.p8` (600) + `.pub` (644); refuse overwrite unless `OVERWRITE_ADMIN_KEY=1` |
| 03 | lock_config_permissions | chmod 600 config.toml + private key |
| 04 | register_admin_public_key | **only password-auth call**; `ALTER USER … SET RSA_PUBLIC_KEY` |
| 05 | verify_admin_jwt | `verify_admin_jwt_full` against current admin warehouse |
| 06 | setup_loader_keypair | generate loader key-pair (lazy) → register pubkey via admin JWT → upsert `[connections.loader]` to SNOWFLAKE_JWT |
| 07 | test_loader_connection | `snow connection test -c loader` (key-pair; no `.env`/password) |
| 08 | promote_admin_warehouse | verify ARTWORK_WH exists → rewrite config.toml warehouse → re-verify JWT |

## Conventions to carry forward

- Heavy header banners: purpose, zero-export resolution order, idempotency note,
  paired rollback, optional env. `==>` progress echoes.
- `snow sql --filename <f> --variable k=v --enhanced-exit-codes`; SQL templates use
  `&{ var }` substitution. **Credentials only via runtime `--variable`, never
  literals in `.sql`.**
- Strict perms: `~/.snowflake` & `keys` → 700; `config.toml` & `.p8` → 600; `.pub` → 644.
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
   `[connections.loader]` to SNOWFLAKE_JWT; `snow connection test -c loader` = OK.
   Python + `.env.example` moved to `SNOWFLAKE_PRIVATE_KEY_FILE`.
   **Learning note:** `CREATE USER IF NOT EXISTS` could not convert the pre-existing
   PERSON user, so the file appends idempotent `ALTER USER … SET TYPE = SERVICE; UNSET
   PASSWORD` to *converge*. See `met-deepdive.md` `AUTH-01`.
2. **`profiles.yml.example` uses `env_var()`** — valid for local dbt, but
   **incompatible with Snowflake-native dbt projects** (no env vars inside
   Snowflake). Matters when designing the CLI-driven production version.

## When to escalate to full source

- Editing a script's logic → open that one file.
- Need exact awk/TOML-rewrite implementation → open `_lib.sh`.
- Reproducing/debugging the private-repo bind chain → open
  `git-setup/create_api_integration.sql` (+ `create_git_ops_db.sql`,
  `create_git_repository.sql`).
- Anything else → trust this summary.
