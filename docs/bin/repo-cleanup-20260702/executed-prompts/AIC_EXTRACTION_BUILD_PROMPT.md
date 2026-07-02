# AIC Extraction Layer -- Build Prompt

## Your Role

You are a **Principal Software Engineer** at a top-tier company (think
Facebook/Google/Amazon) building a data extraction package from a finalized
design document. Your standards: simple over clever, minimal file count,
no dead code, no speculative abstractions. If it can be done in 50 lines,
don't write 200. The design is approved -- your job is to implement it
faithfully and ship something that works end-to-end on first run.

## Context

The AIC (Art Institute of Chicago) extraction layer has a **completed design
document** with all decisions finalized:

- **Design doc:** `docs/context/aic-extraction-design.md` (READ THIS FIRST)
- **Branch:** `donkey-kong-sandbox`
- **Account:** Snowflake `OBANOYY-MK07348`, role `ARTWORK_LOADER`, key-pair auth
- **Target:** `ARTWORK_DB.BRONZE` (3 tables: `RAW_AIC_ARTWORKS`, `RAW_AIC_AGENTS`, `AIC_LOAD_WATERMARK`)

The design specifies **3 Python files + 3 SQL templates**. This is intentional
simplicity. Do not inflate the file count.

## What Already Exists

- **Met extractor** at `extraction/met/` -- the established pattern for this repo.
  Use it as your style reference for:
  - `config.py` structure (dataclass + env vars + `load_dotenv()`)
  - `run.py` structure (argparse + subcommand dispatch)
  - SQL template loading via `db.load_sql()` (shared utility in `extraction/met/db.py`)
  - Snowflake connection via `_snowflake_connect()` in `snowflake_uploader.py`
  - README structure and configuration reference table
- **Infrastructure DDL** at `infrastructure/` -- but do NOT create DDL files here.
  The 3 Bronze tables will be added to `infrastructure/` via `make iac` separately.
  Your Python code should assume the tables exist.
- **`.env.example`** at the repo root and `extraction/met/.env.example` -- follow
  the same pattern for AIC-specific env vars.

## Key References (read before coding)

| What | Where | Why you need it |
|------|-------|----------------|
| Finalized design (all decisions, DDL, CLI spec, data flow) | `docs/context/aic-extraction-design.md` | The blueprint. Section 4 = file layout, Section 5 = CLI spec, Appendix A = config constants, Appendix B+C = SQL templates. |
| Met config.py (style reference) | `extraction/met/config.py` | Dataclass pattern, env var loading, field comments. |
| Met run.py (style reference) | `extraction/met/run.py` | Argparse with subcommands, logging config, clean dispatch. |
| Met snapshot_loader.py (closest analog) | `extraction/met/snapshot_loader.py` | PUT + COPY INTO + MERGE pattern against Bronze via key-pair auth. This is the template for AIC's `loader.py`. |
| Met snowflake_uploader.py (`_snowflake_connect`) | `extraction/met/snowflake_uploader.py` | Reusable Snowflake connection helper (key-pair auth, role/warehouse/db/schema set on connect). |
| Shared SQL loader | `extraction/met/db.py` (`load_sql`, `strip_sql_comments`) | Use these for loading `.sql` templates. Import from `extraction.met.db` -- do not duplicate. |
| Design doc Appendix D (Met comparison) | End of design doc | Shows exactly where AIC is simpler and why. |

## Deliverables

### 1. Python package: `extraction/aic/`

```
extraction/aic/
    __init__.py          # Empty package marker
    config.py            # Config dataclass (env vars, constants)
    run.py               # CLI entry point (snapshot, delta stub, status)
    loader.py            # Core logic: download, extract, transform, upload, merge, soft-delete
    sql/
        __init__.py      # Empty (makes sql/ importable for resources API)
        merge_aic_artworks.sql
        merge_aic_agents.sql
        soft_delete_deaccessioned.sql
```

### 2. Configuration

- `extraction/aic/.env.example` with all AIC-specific env vars + Snowflake connection vars.

### 3. README

- `extraction/aic/README.md` -- follow the structure of `extraction/met/README.md`:
  quick start, usage per subcommand, configuration reference table, recovery,
  verifying the load.

### 4. Requirements

- `extraction/aic/requirements.txt` -- pinned deps (should be minimal: `snowflake-connector-python`, `requests`, `python-dotenv`).

## Implementation Constraints

1. **v1 = `snapshot` subcommand only.** The `delta` subcommand should exist in
   the CLI (argparse) but print "Not yet implemented" and exit. Do not build
   the delta path.

2. **No SQLite.** The design explicitly decided against it (Section 4, "Why no
   SQLite?"). Do not introduce any local state beyond temp files.

3. **Reuse `extraction.met.db.load_sql` and `strip_sql_comments`.** Do not
   duplicate the SQL loader. Import it cross-package.

4. **Reuse `extraction.met.snowflake_uploader._snowflake_connect`.** Same
   connection helper, same key-pair auth, same env vars. Do not duplicate.

5. **Selective tar extraction.** Only extract `json/artworks/` and `json/agents/`
   from the tar.bz2. See design doc Section 1 pseudocode.

6. **Single NDJSON file per entity for v1.** Do not chunk. Revisit if COPY INTO
   takes >30s on XS warehouse (it won't for 131k rows).

7. **TEMPORARY staging table.** `CREATE TEMPORARY TABLE` for the COPY INTO target;
   it auto-drops on session close. No cleanup needed.

8. **Soft-delete runs on every `snapshot` invocation** (post-MERGE). See Appendix C.

9. **Progress reporting.** Emit a log line every 10,000 records during JSON-to-NDJSON
   transform. Use `logging.info`, not `print`.

10. **No threading, no async, no multiprocessing.** Serial is fine -- the whole
    snapshot path takes ~2-5 minutes.

11. **`_batch_id` prefix:** snapshot batches = `snap_{uuid_hex[:12]}`. See design
    doc Section 7.

12. **Type annotations on all public functions.** Follow the Met extractor's style.

13. **The `status` subcommand** queries `RAW_AIC_ARTWORKS`, `RAW_AIC_AGENTS`, and
    `AIC_LOAD_WATERMARK` to print row counts, deaccession counts, and last batch info.

## Quality Bar

Before declaring done:

1. `python -c "import extraction.aic"` -- imports cleanly.
2. `python -m extraction.aic.run --help` -- prints help with all subcommands.
3. `python -m extraction.aic.run snapshot --limit 5` -- smoke test (5 records).
4. No unused imports, no dead code, no `# TODO` that could be done now.
5. Docstrings on every module and every public function.
6. SQL templates match the DDL in the design doc (column names, types, comments).

## Style Rules

- ASCII-only (no smart quotes, em dashes, arrows).
- UPPERCASE Snowflake identifiers in SQL.
- `logging` (not `print`) for all operational output.
- One logical function per concern (download, extract, transform, upload, merge,
  soft-delete). Compose them in a `run_snapshot()` orchestrator.
- Error messages should include the failing entity/step so the operator can
  resume or debug without reading source.
- Follow existing code style in `extraction/met/` -- it is the canonical reference.
