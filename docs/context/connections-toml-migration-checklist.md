# connections.toml Migration — Live Checklist

**Task:** Migrate Snowflake connection definitions from `config.toml` to
`connections.toml` so the VS Code Snowflake extension (and the Python connector)
can authenticate, while keeping `snow` CLI and dbt working.

**Branch:** `donkey-kong-sandbox` | **Account:** `OBANOYY-MK07348` (admin
`PORCHFLAKE` / `ACCOUNTADMIN`) | **Started:** 2026-06-06 | **solo=1 (verified)**

## Dual-FS status (update as state changes)
- **applied-to-account:** NO (no SQL run; config files are local to each Mac)
- **pushed-to-Mac:** NO (all edits are workspace-only until owner syncs)

> Workspace edits are NOT on the Mac until the owner syncs. No `make`/`python`/
> `dbt`/`snow` is run from the workspace; the owner runs the verification gates
> on Mac #2 (the guinea pig).

## DUAL-INSTANCE INCIDENT (2026-06-06 ~16:30-16:32 UTC)
A SECOND Cortex instance executed this same plan concurrently. It authored
Phase 3 (06, 09) and Phase 4 (08) and rewrote parts of this checklist. Detected
at ~16:32 via: (a) my Phase 2 checklist edit failing ("string not found"), and
(b) `06/09/08` carrying edits + mtimes (16:30-16:32) I never made. SQL solo-check
stayed 1 (file edits don't hit QUERY_HISTORY). Owner chose **"kill the other, I
continue"**; CORTEX_FORK_INCIDENTS write declined (applied-to-account stays NO).
Other instance confirmed quiescent (no edits after 16:32:06). Its 06/09/08 work
was reviewed: design-consistent with this plan and `bash -n` clean — KEPT.
**Gap found:** the fork did NOT fix `04_register_admin_public_key.sh` (preflights
config.toml but now resolves from connections.toml) — added to Phase 7 below.

## Decisions locked (2026-06-06)
- **D1 = 1b:** Remove `[connections.*]` blocks from `config.toml` AFTER a verified
  cutover. config.toml keeps a single source of truth out of the loop.
- **D2:** `config.toml` STAYS as the settings file — it keeps
  `default_connection_name` + `[cli]` + any FUTURE non-connection config. Only
  connection *definitions* move to `connections.toml`.
- **D3:** Key field written as **`private_key_path`** in `connections.toml`.
  - Rationale: only value satisfying VS Code ext + snow CLI + Python connector.
  - **FALLBACK (if Mac #2 `snow --version` is too old to accept
    `private_key_path` in connections.toml):** revert the field token to
    `private_key_file` at the 4 write call sites (init_profile, 06, 09 — 08 writes
    `warehouse`, not the key). One-token change per site.

## Section-name transform (the core mechanical change)
```
config.toml      [connections.<name>]   -->   connections.toml   [<name>]
default_connection_name + [cli.*]        -->   STAY in config.toml
```

## Regression matrix (which client reads which file)
| Client | Connections from | default_connection_name | Key field |
|---|---|---|---|
| snow CLI | connections.toml if present (else config.toml) | config.toml | private_key_path or _file |
| VS Code ext | connections.toml ONLY | n/a | private_key_path |
| Python connector | connections.toml (~/.snowflake) | n/a | private_key_path |
| dbt | profiles.yml (env_var) — UNAFFECTED | n/a | private_key_path (own namespace) |

> NOT in scope (do NOT edit): `extraction/met/config.py` env var
> `SNOWFLAKE_PRIVATE_KEY_FILE`; `artwork_pipeline/profiles.yml` field
> `private_key_path`. These are separate namespaces from the snow CLI TOML key.

---

## RESUME PROTOCOL (fresh window / after a connection break)
1. Read this whole file. Find the first unchecked `[ ]` item below.
2. Re-confirm dual-FS status + the verification gate for the last `[x]` phase.
3. `git diff` on `donkey-kong-sandbox` shows what has already been applied to the
   workspace (edits are revertable via git). Continue from the first `[ ]`.
4. After completing each item, FLIP its box to `[x]` here and note the result.

---

## Verification gates (owner runs on Mac #2 — NOT from workspace)
After Phase 5 and again after Phase 6:
```
snow connection test -c mk07348
snow connection test -c mk07348_loader
snow connection test -c mk07348_transformer
```

---

## Phase 0 — bootstrap
- [x] Write this checklist file. (2026-06-06)
- [ ] Owner confirms Mac #2 `snow --version` accepts `private_key_path`
      (finalizes D3; else apply the fallback above).

## Phase 1 — `scripts/snowflake_cli/_lib.sh`
- [x] Add `SNOW_LIB_CONNECTIONS_TOML` const (after line 35).
- [x] `list_connections`: reads connections.toml; matches bare `[name]`
      headers; default still read from config.toml.
- [x] `set_default_connection`: existence check reads bare `${name}` from
      connections.toml; `default_connection_name` upsert stays in config.toml.
- [x] `resolve_admin_account`: parse bare `${ADMIN_CONN}` from connections.toml.
- [x] `resolve_admin_user`: same.
- [x] `resolve_admin_warehouse`: same.
- [x] Add `remove_toml_section <section> <file>` helper (backup/atomic-mv/chmod
      600; no-op if absent). `bash -n` clean.

## Phase 2 — `scripts/snowflake_cli/init_profile.sh`
- [x] Add `CONNECTIONS_TOML` var; create connections.toml + chmod 600 if missing.
- [x] Inverted the shadow guard: connections.toml is now the PRIMARY write target
      (error path removed; header comment + existing-profile guard read it).
- [x] `ADMIN_SECTION` = bare `${ADMIN_CONN}`.
- [x] Seed block targets connections.toml, key `private_key_path`.
- [x] `default_connection_name` UNCHANGED (stays config.toml).
- [x] Closing echo + header wording updated. `bash -n` clean.

## Phase 3 — `06_setup_loader_keypair.sh` + `09_setup_transformer_keypair.sh`
- [x] 06: CONNECTIONS_TOML var; upserts target it, bare `${SNOW_LIB_LOADER_CONN}`,
      key `private_key_path`. (by fork; reviewed + `bash -n` clean)
- [x] 09: same for `${SNOW_LIB_TRANSFORMER_CONN}`. (by fork; reviewed + `bash -n` clean)

## Phase 4 — `08_promote_admin_warehouse.sh`
- [x] CONNECTIONS_TOML var + file-existence guard.
- [x] `replace_toml_value_in_section` warehouse write: bare `[admin]`, connections.toml.
- [x] parse-back read of warehouse: bare section, connections.toml.
      (by fork; reviewed consistent with `_lib.sh` helpers + `bash -n` clean)

## Phase 5 — `03_lock_config_permissions.sh`
- [x] Added `lock "${SNOW_LIB_CONNECTIONS_TOML}"`; header + final `ls` updated.
      `bash -n` clean.
- [ ] GATE: owner runs the 3 `snow connection test` commands on Mac #2.

## Phase 6 — Transactional cutover (config.toml block removal) — GATED
- [ ] ONLY after Phase 5 gate is green: call `remove_toml_section` for each
      `[connections.*]` in config.toml (`.bak` first). Leaves
      `default_connection_name` + `[cli]`.
- [ ] GATE: re-run the 3 `snow connection test` commands.

## Phase 7 — test / auxiliary scripts
- [x] `04_register_admin_public_key.sh`: preflight now checks connections.toml;
      resolution-order comment updated. `bash -n` clean. **(fork gap closed)**
- [x] `05_verify_admin_jwt.sh`: warehouse echo reads bare `[admin]` from
      connections.toml; header comments updated. `bash -n` clean.
- [x] `07` / `10`: NO change needed (use `snow connection test -c`). Confirmed.

## Phase 8 — `setup.sh`
- [x] Header phases, multi-account block, `usage()`, phase-function comments,
      and the `--phase all` "Next steps" echo: `[connections.X]` -> `[X]`,
      config.toml -> connections.toml for connection storage. `default_connection_name`
      references kept as config.toml. No logic change. `bash -n` clean.

## Phase 9 — docs
- [x] `docs/context/cli-connection.md` (fork did most; I fixed 2 stale
      `[connections.*]` refs it missed — Known-gaps + Multi-account/list_connections).
- [x] `docs/context/file-map.md` (fork updated init_profile/03/06/08/09; I completed
      the rows it missed: `_lib.sh`, `04`, `05`, `setup.sh` — all 2026-06-06).
- [x] `AGENTS.md` status row (fork appended; reviewed pessimistically — accurate).
- [x] `docs/context/session-3-progress-log.md` — single `End of this window
      (2026-06-06)` entry (no duplicate); verified + corrected to Phases 1-10.

## Phase 10 — README refresh (Task 2; independent of Phases 1-9)
- [x] `scripts/snowflake_cli/README.md` (fork; reviewed: one-command lead, phases
      table, `private_key_path`, file layout — sound. 191→78 lines).
- [x] `git-setup/README.md` (fork; reviewed: condensed, B/V prefix mismatch flagged,
      PAT safety in `<details>` — sound. 113→73 lines).
- [x] `scripts/README.md` — does NOT exist; skipped (owner did not request a new one).

## Cosmetic comment cleanup (post-fork, by me)
- [x] `07`/`10`/`02` header comments + `cli-connection.md`: stale `[connections.X]`
      / `private_key_file` / `config.toml` references corrected. No logic change.

## Final verification (single-writer, 2026-06-06)
- [x] All 14 `scripts/snowflake_cli/*.sh` pass `bash -n`.
- [x] No functional `[connections.X]` writes or `private_key_file` writes remain in
      any active code path (grep-audited; remaining hits are illustrative comments).
- [x] Solo-check re-confirmed = 1 (PORCHFLAKE) before final edits.

---

## Rollback
- Every mutating helper writes `~/.snowflake/{config,connections}.toml.bak.<ts>`.
- Workspace file edits are revertable via `git checkout` on `donkey-kong-sandbox`.
- Phase 6 is the only hard-to-reverse step; it is gated behind green tests and
  takes a `.bak` first.
