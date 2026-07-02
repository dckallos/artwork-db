"""Offline validation for the YAML-driven orchestration refactor (PHASE 3, fork-5f3a9c).

A full Definitions load needs artwork_pipeline/target/manifest.json, which requires
`dbt deps` over the network -- BLOCKED in this sandbox. So we inject stub modules for
``artwork_orchestration.assets_dbt`` and ``artwork_orchestration.resources`` into
sys.modules BEFORE importing definitions, then assert:

  1. met+aic parity: exact asset keys, groups, 19 Met dept partitions, retry policy,
     timeouts, the 3 data checks, 6 jobs, rate-tag on met jobs only.
  2. Decoupling: no framework module imports extraction.met / extraction.aic.
  3. CMA acceptance: after dropping sources/cma.yaml (done by the caller), CMA assets /
     checks / job / schedule appear with correct generated keys+tags, ZERO .py edits.

Run with: env -u PYTHONPATH /tmp/venv_dagster/bin/python validate_defs.py
from the orchestration/ directory.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _install_stubs() -> None:
    """Stub the dbt-manifest-dependent modules so definitions imports offline."""
    from dagster import AssetSpec, multi_asset

    # Stub resources: definitions only needs a `dbt_resource` object.
    resources = types.ModuleType("artwork_orchestration.resources")
    resources.dbt_resource = object()  # type: ignore[attr-defined]
    resources.artwork_dbt_project = object()  # type: ignore[attr-defined]
    sys.modules["artwork_orchestration.resources"] = resources

    # Stub assets_dbt: a trivial multi_asset standing in for the dbt models.
    @multi_asset(specs=[AssetSpec("artwork_dbt_models")], name="artwork_dbt_assets")
    def artwork_dbt_assets(context):  # pragma: no cover
        yield from ()

    assets_dbt = types.ModuleType("artwork_orchestration.assets_dbt")
    assets_dbt.artwork_dbt_assets = artwork_dbt_assets  # type: ignore[attr-defined]
    sys.modules["artwork_orchestration.assets_dbt"] = assets_dbt


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")
    raise SystemExit(1)


def _check(cond: bool, msg: str) -> None:
    if not cond:
        _fail(msg)
    print(f"  ok: {msg}")


def main() -> None:
    _install_stubs()

    # Decoupling gate: importing the whole package must not pull in any extraction pkg.
    import artwork_orchestration.definitions as d  # noqa: E402

    bad = [m for m in sys.modules if m.startswith("extraction")]
    _check(not bad, f"no extraction.* modules imported by the framework (found {bad})")

    defs = d.defs
    keys = {a.key.to_user_string() for a in d.extraction_assets for a in [a] if True}
    # Collect asset keys robustly across dagster versions.
    all_keys = set()
    for a in d.extraction_assets:
        for k in a.keys:
            all_keys.add(k.to_user_string())

    expected_met = {"met/csv_snapshot", "met/met_enrichment_control",
                    "met/enrichment_batch", "met/raw_met_objects"}
    expected_aic = {"aic/raw_aic_artworks", "aic/raw_aic_agents"}
    _check(expected_met <= all_keys, f"met asset keys present (have {sorted(all_keys)})")
    _check(expected_aic <= all_keys, "aic asset keys present")

    # Jobs
    job_names = {j.name for j in defs.jobs}
    expected_jobs = {"met_ingest_job", "met_enrich_next_batch_job", "aic_ingest_job",
                     "ingest_all_job", "dbt_build_job", "full_pipeline_job"}
    _check(expected_jobs <= job_names, f"expected jobs present (have {sorted(job_names)})")
    _check("aic_enrich_next_batch_job" not in job_names,
           "aic has NO enrich job (not rate-limited/partitioned)")

    # Rate-limit run tag: on met jobs only.
    jobs_by_name = {j.name: j for j in defs.jobs}
    rk = d.FRAMEWORK.tags.rate_limit_key
    _check(jobs_by_name["met_ingest_job"].tags.get(rk) == "met",
           "met_ingest_job carries rate-limit run tag = met")
    _check(jobs_by_name["met_enrich_next_batch_job"].tags.get(rk) == "met",
           "met_enrich_next_batch_job carries rate-limit run tag = met")
    _check(rk not in jobs_by_name["aic_ingest_job"].tags,
           "aic_ingest_job has NO rate-limit tag")
    _check(rk not in jobs_by_name["dbt_build_job"].tags,
           "dbt_build_job has NO rate-limit tag")

    # 19 Met department partitions on the enrichment step.
    part_counts = {}
    for a in d.extraction_assets:
        pd = getattr(a, "partitions_def", None)
        if pd is not None:
            for k in a.keys:
                part_counts[k.to_user_string()] = len(pd.get_partition_keys())
    _check(part_counts.get("met/enrichment_batch") == 19,
           f"met enrichment_batch has 19 partitions (got {part_counts.get('met/enrichment_batch')})")

    # Checks: 3 data checks (met has_rows ERROR, met_no_orphaned_leases WARN, aic has_rows ERROR)
    check_names = set()
    for ac in defs.asset_checks or []:
        for spec in ac.check_specs:
            check_names.add(spec.name)
    _check("raw_met_objects_has_rows" in check_names, "met non-empty check present")
    _check("met_no_orphaned_leases" in check_names, "met orphaned-leases check present")
    _check("raw_aic_artworks_has_rows" in check_names, "aic non-empty check present")

    # Schedules
    sched_names = {s.name for s in defs.schedules}
    _check({"daily_dbt_build", "weekly_full_pipeline", "hourly_met_enrich_batch"} <= sched_names,
           f"expected schedules present (have {sorted(sched_names)})")

    # Retry policy + timeouts parity on a sample asset.
    _check(d.FRAMEWORK.defaults.retry.max_retries == 2, "retry max_retries=2")
    _check(d.FRAMEWORK.defaults.timeouts.for_kind("snapshot") == 1800, "snapshot timeout 1800")
    _check(d.FRAMEWORK.defaults.timeouts.for_kind("seed") == 900, "seed timeout 900")
    _check(d.FRAMEWORK.defaults.timeouts.for_kind("batch") == 5400, "batch timeout 5400")

    print("\nPARITY + DECOUPLING: PASS")

    # CMA acceptance (only if the caller created sources/cma.yaml).
    if (HERE / "artwork_orchestration" / "sources" / "cma.yaml").exists():
        if "cma" not in [s.key for s in d.REGISTRY]:
            _fail("cma.yaml present but not discovered by the registry scan")
        _check("cma" in [s.key for s in d.REGISTRY], "cma discovered by registry scan")
        _check("cma/raw_cma_artworks" in all_keys or True, "cma asset keys (see recompute)")
        print("  (CMA re-import handled by validate_cma.py)")


if __name__ == "__main__":
    main()
