# Adding a new museum

You do **not** need to understand the orchestration framework or write any Python. A new
museum is added by touching **four things**, only one of which is a framework file.

## The four artifacts you own

1. **Bronze DDL** — create your museum's raw landing tables (in `infrastructure/`), the
   same way the existing museums' Bronze tables are created.

2. **Your extraction CLI** — add your scripts under `extraction/<key>/` so that
   `python -m extraction.<key>.run <subcommand>` runs one phase and **exits 0 on
   success**. This is legitimately source-specific code and is yours to write.

3. **One YAML file** — copy an existing file in
   `orchestration/artwork_orchestration/sources/` to `sources/<key>.yaml` and fill it in.
   For a simple "download a snapshot" source that is about six lines:

   ```yaml
   source: example_museum
   cli_module: extraction.example_museum.run
   steps:
     - name: snapshot
       run: snapshot
       produces: [raw_example_museum_objects, raw_example_museum_agents]
   ```

   Field-by-field docs are in `SCHEMA.md`. Rules of thumb:
   - Each `produces` entry is a table dbt reads (a "dbt source"). List them by name.
   - Want a "did any rows land?" check? Use `{table: raw_example_museum_objects, check_nonempty: true}`.
     Otherwise **let dbt handle data quality** (that is the recommended path).
   - Only if a step calls a **rate-limited API**, add `rate_limited: true` to that step and
     one `tag_concurrency_limits` entry for your source key in
     `orchestration/dagster_home/dagster.yaml` (copy the existing one, change the value).

4. **Nothing else.** Reload Dagster. Your assets, checks, jobs, and schedule are generated
   automatically — no framework `.py` file changes.

## What you get, automatically

- One asset per step, chained in order (`<key>__<step>`), with the right group, retry
  policy, and timeout.
- Per-source jobs: `<key>_ingest_job` (and `<key>_enrich_next_batch_job` if a step is
  partitioned + rate-limited).
- Inclusion in the global `ingest_all_job` and `full_pipeline_job`.
- A weekly/hourly schedule (created **stopped**; enable it on the production host).
- Any checks you declared, plus the dbt Gold freshness checks.

## Checklist

- [ ] Bronze tables created (DDL).
- [ ] `python -m extraction.<key>.run <subcommand>` works and exits 0.
- [ ] `sources/<key>.yaml` written (validate by reloading Dagster — errors name the exact
      file/field).
- [ ] If rate-limited: `rate_limited: true` on the step **and** a `dagster.yaml`
      `tag_concurrency_limits` entry for `<key>`.
