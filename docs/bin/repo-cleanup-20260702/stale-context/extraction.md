# Tier 1 — Workflow 3: Extraction (Met OpenAccess → Bronze)

> **COMPLETE** (reviewed 2026-05-30, branch `donkey-kong-sandbox`). Self-contained
> summary of the `extraction/met/*` Phase-1A extractor plus the root-level files
> that support runtime (`.env.example`, `profiles.yml.example`, `requirements.txt`,
> `rename_and_update.py`). Trust this before opening source; update if stale.

## What this workflow is

A standalone Python package (`extraction/met/`) that loads the Metropolitan
Museum of Art Open Access collection into `ARTWORK_DB.BRONZE.raw_met_objects`.
It is **runtime ETL**, not IaC — it consumes the objects that Workflow 2 creates
(`ARTWORK_DB`, `BRONZE`, `raw_met_objects`, `bronze_load_stage`, role
`ARTWORK_LOADER`, warehouse `ARTWORK_WH`). It runs as the service identity
`ARTWORK_LOADER_SVC` and authenticates with password (not the admin key pair).

Three resumable phases, driven by a CLI (`python -m extraction.met.run <cmd>`):

1. **bootstrap** — stream `MetObjects.csv` from GitHub, upsert every row into a
   local SQLite DB (`enrichment_status='pending'`). ~2–5 min.
2. **enrich** — async-call the Met API once per object for image URLs; mark
   `done` / `no_image` / `error`. ~6–7 h at default 20 rps over ~471k rows.
3. **upload** — stream `done && not-yet-uploaded` rows, build nested JSON, write
   gzipped NDJSON chunks, `PUT` to the stage, `COPY INTO raw_met_objects`. ~10–30
   min for a full first load.

`status` prints dashboards; `all` runs bootstrap→enrich→upload back to back.

## Architecture (per-file, one line each)

| File | Lines | Role |
|---|---|---|
| `run.py` | 120 | argparse CLI; subcommands bootstrap/enrich/upload/status/all; `status` reads SQLite directly |
| `config.py` | 71 | `Config` dataclass; all settings from env w/ defaults; `MET_*` + `SNOWFLAKE_*`; `ensure_paths()` |
| `db.py` | 43 | `load_sql()` (reads `sql/*.sql` via `importlib.resources`), `initialize_database()`, `connect()` ctx mgr |
| `csv_bootstrap.py` | 223 | download CSV (streamed), `_map_row` CSV→params, batched UPSERT, run logging |
| `image_enricher.py` | 280 | async aiohttp fetch; token-bucket `_RateLimiter` + semaphore; backoff w/ jitter; serialized SQLite writes |
| `snowflake_uploader.py` | 289 | NDJSON chunking, PUT + COPY INTO, marks `bronze_uploaded_at`; the only Snowflake-touching module |
| `sql/schema.sql` | 97 | SQLite DDL: `met_artworks` (1 row/object) + `extraction_runs` (1 row/phase) + 2 indexes |
| `sql/upsert_artwork.sql` | 79 | `INSERT … ON CONFLICT(object_id) DO UPDATE`; image/bronze cols deliberately excluded from UPDATE |
| `sql/update_enrichment_done.sql` | 9 | mark a row `done` with image URLs |
| `sql/copy_into_bronze.sql` | 18 | `COPY INTO … (object_id, raw_payload, _batch_id)`; `str.format`-templated; `PURGE=TRUE` |
| `sql/__init__.py` | 3 | package marker so `importlib.resources` can find the `.sql` files |
| `__init__.py` | 5 | package docstring only |
| `requirements.txt` | 5 | `snowflake-connector-python`, `requests`, `aiohttp`, `python-dotenv` (pinned `>=`) |
| `.env.example` | 25 | Met-specific env template (see Env section) |
| `README.md` | 207 | full operator runbook: phases, recovery, tuning knobs, Snowflake verification SQL |

## Conventions & patterns (observed — authoritative)

- **SQL lives in files, never inline.** Every non-trivial statement is a
  `sql/*.sql` file loaded once at import via `db.load_sql()`. (Two small inline
  UPDATEs — `UPDATE_NO_IMAGE_SQL`, `UPDATE_ERROR_SQL` — are the only exceptions,
  in `image_enricher.py`.) Mirrors the IaC repo's "Python authors no SQL" ethos.
- **Idempotent + resumable everywhere.** bootstrap UPSERTs and preserves
  enrichment/upload state; enrich re-queries only `pending`/`error`; upload skips
  rows with `bronze_uploaded_at` set. Safe to re-run any phase.
- **Observability table.** Every phase writes a `running`→`success`/`failed` row
  to `extraction_runs` with counts and JSON notes.
- **Two-tier state in SQLite.** `met_artworks` holds CSV fields + API image URLs +
  pipeline state (`enrichment_status`, `bronze_batch_id`, `bronze_uploaded_at`).
  Local SQLite is intermediate-only; Snowflake Bronze is the destination.
- **Config from env with sane defaults.** All knobs are `MET_*` (API/paths/chunk)
  or `SNOWFLAKE_*` (connection). `dotenv.load_dotenv()` reads `.env` from CWD.
- **Bronze JSON shape** (built in `snowflake_uploader._build_payload`):
  `{ object_id, csv:{…47 descriptive cols…}, api_images:{primary_image,
  primary_image_small, additional_images[]}, _meta:{source_system, csv_loaded_at,
  enriched_at, batch_id} }`. `_extracted_at` / `_source_system` default at the
  table level; the loader supplies `object_id`, `raw_payload`, `_batch_id`.
- **Bulk-load via stage + COPY INTO**, deliberately avoiding `write_pandas`/VARIANT
  pitfalls. PUT uses `AUTO_COMPRESS=FALSE` (file already gzipped) + `OVERWRITE=TRUE`;
  COPY uses `ON_ERROR='ABORT_STATEMENT'` + `PURGE=TRUE`. `rows_loaded` parsed from
  COPY result column index 3.
- **Rate limiting (enrich).** Min-interval `_RateLimiter` caps total rps; bounded
  `asyncio.Semaphore` caps concurrency; exponential backoff + jitter (cap 60 s) on
  429/5xx and transport errors. 404 → `no_image`; missing `primaryImage` →
  `no_image`. Commits every 500 rows.

## Relationship to Workflow 2 (DDL/infra)

- Targets the BRONZE objects from `infrastructure/create_*.sql`. The `csv` payload
  block's 47 columns map 1:1 to `met_artworks` CSV columns (and to the Met CSV
  headers via `_map_row`).
- Uses role `ARTWORK_LOADER` + user `ARTWORK_LOADER_SVC` (created by
  `create_service_user.sql`) — the loader credential rotated by Workflow 1.
- Writes only to `BRONZE`; SILVER/GOLD are left for the dbt transformer layer
  (see `profiles.yml.example`).

## Env / config files (root + extraction)

Two **separate** `.env.example` files with different variable sets — do not
conflate them:

- **`extraction/met/.env.example`** (Met-specific): `MET_*` knobs
  (`MET_SQLITE_PATH`, `MET_CSV_LOCAL_PATH`, `MET_API_CONCURRENCY`/`RPS`/
  `MAX_RETRIES`/`TIMEOUT`/`USER_AGENT`, `MET_UPLOAD_CHUNK`) + the `SNOWFLAKE_*`
  connection block. Defaults match `config.py`.
- **`/.env.example`** (root, "Phase 1A" runtime): `SNOWFLAKE_*` for
  `ARTWORK_LOADER_SVC`, a note that the same `SNOWFLAKE_PASSWORD` is consumed by
  the `snow` CLI `loader` connection (one credential to rotate), plus a
  `SMITHSONIAN_API_KEY` and optional `EXTRACTION_*` overrides.
- **`/profiles.yml.example`** — dbt-snowflake profile (`artwork_pipeline`, dev→SILVER
  / prod→GOLD), **key-pair auth** via `private_key_path`, all values via
  `env_var()`. This is for **external dbt-core**, role `ARTWORK_TRANSFORMER`.
- **`/requirements.txt`** — root pin set (NOT yet read line-by-line in this pass
  beyond confirming it exists; see file-map trigger).

## Gaps / TODOs / risks (flagged, not fixed)

- **`profiles.yml.example` vs Snowflake-native dbt.** It relies on `env_var()` and
  `private_key_path`. Per repo policy for **dbt Projects on Snowflake**,
  `env_var()` and on-disk auth are NOT usable (dbt runs inside Snowflake). This
  example targets external dbt-core only; a native-dbt profile is a documentation/
  setup gap if the project moves to Snowflake-managed dbt.
- **`rename_and_update.py` is a spent one-shot migration.** It `git mv`s the old
  `V###__`/`R###__` prefixed filenames to the prefix-free names and rewrites
  internal references. The rename is already done (current tree is prefix-free),
  so this script is **historical/dead** and is itself a dense source of `V###`/
  `R###` strings (by design — it is the rename map). Candidate for removal; do not
  treat its prefixes as "stale comments to reword."
- **Hardcoded sample account in `extraction/met/.env.example:14`**
  (`SNOWFLAKE_ACCOUNT=HXCNOII-RS05429`). Cosmetic, but a real-looking identifier in
  a committed example; consider a placeholder. Password is correctly `[omitted]`.
- **`SMITHSONIAN_API_KEY` in root `.env.example`** has no consumer in
  `extraction/met/*` (Met-only). Either dead config or a placeholder for a future
  Smithsonian extractor (Bronze already has `raw_smithsonian_objects`).
- **~500 MB CSV / 1–2 GB SQLite** created under `extraction/met/data/`
  (gitignored). Disk-bound; not a code issue but an operational prerequisite.
- **`enrichment_log`/`extraction_runs` only in SQLite.** Bronze `extraction_log`
  table (Workflow 2) is not written by this extractor — run history is local-only.

## Stale `V***` / `R***` / `B***` references found here (flagged, not fixed)

These are comment/doc-only and contradict the prefix-free convention; reword to
cite the manifest, not prefixes:

- `extraction/met/config.py:53-54` — "objects created in infrastructure/V001-V007".
- `extraction/met/README.md:37` — "infra from `infrastructure/V001-V007` applied".
- `/.env.example:9,13` — "infrastructure/V008__create_service_user.sql" and
  "Service account created by V008".
- `rename_and_update.py` (whole file) — the rename map itself; treat as
  obsolete-script-to-retire rather than a comment to reword.

## When to escalate to full source

- Changing the Bronze JSON shape or COPY mapping → `snowflake_uploader.py` +
  `sql/copy_into_bronze.sql` (keep `met_artworks` columns and `_CSV_PAYLOAD_COLUMNS`
  in lockstep).
- Adding/removing a descriptive column → `sql/schema.sql`,
  `csv_bootstrap._map_row`, `sql/upsert_artwork.sql`, and
  `snowflake_uploader._CSV_PAYLOAD_COLUMNS` together.
- Tuning API behavior → env knobs first (`MET_API_*`); only open
  `image_enricher.py` for retry/limiter logic.
- Native-dbt migration → revisit `profiles.yml.example` (env_var/key-pair gap).
