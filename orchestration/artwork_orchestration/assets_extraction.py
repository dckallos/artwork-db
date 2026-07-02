"""Extraction assets -- thin Dagster wrappers over the existing extraction CLIs.

Design choice for the dev phase: rather than refactor the extraction code now,
each asset shells out to the module CLI that already exists
(``python -m extraction.met.run ...`` / ``extraction.aic.run ...``). Once the
orchestration layer is stable we can refactor these into typed, in-process
assets (a later "enhance the extraction layer" milestone).

The TERMINAL assets are keyed to match the dbt source keys (see translator.py),
so the dbt models depend on them automatically.
"""
from __future__ import annotations

import subprocess
import sys

from dagster import AssetExecutionContext, MaterializeResult, asset, multi_asset, AssetOut

from .resources import REPO_ROOT
from .translator import dbt_source_asset_key


def _run_module(context: AssetExecutionContext, module_args: list[str]) -> None:
    """Run `python -m <module> <args...>` from the repo root, streaming output."""
    cmd = [sys.executable, "-m", *module_args]
    context.log.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise RuntimeError(
            f"Extraction command failed ({proc.returncode}): {' '.join(cmd)}"
        )


# ---------------------------------------------------------------------------
# Met pipeline: snapshot -> seed control -> enrich (assemble RAW_MET_OBJECTS)
# ---------------------------------------------------------------------------
@asset(group_name="extraction_met", key=["met", "csv_snapshot"], compute_kind="python")
def met_csv_snapshot(context: AssetExecutionContext) -> MaterializeResult:
    """Phase 1: load the Met OpenAccess CSV into BRONZE.MET_CSV_SNAPSHOT."""
    _run_module(context, ["extraction.met.run", "snapshot"])
    return MaterializeResult(metadata={"phase": "snapshot"})


@asset(
    group_name="extraction_met",
    key=dbt_source_asset_key("met", "met_enrichment_control"),
    deps=[met_csv_snapshot],
    compute_kind="python",
)
def met_enrichment_control(context: AssetExecutionContext) -> MaterializeResult:
    """Phase 2: seed MET_ENRICHMENT_CONTROL from the snapshot (dbt source)."""
    _run_module(context, ["extraction.met.run", "seed-control"])
    return MaterializeResult(metadata={"phase": "seed-control"})


@asset(
    group_name="extraction_met",
    key=dbt_source_asset_key("met", "raw_met_objects"),
    deps=[met_enrichment_control],
    compute_kind="python",
)
def raw_met_objects(context: AssetExecutionContext) -> MaterializeResult:
    """Phase 3: enrich the worklist and assemble BRONZE.RAW_MET_OBJECTS (dbt source)."""
    _run_module(context, ["extraction.met.run", "enrich-met"])
    return MaterializeResult(metadata={"phase": "enrich-met"})


# ---------------------------------------------------------------------------
# AIC pipeline: one snapshot run populates both source tables.
# ---------------------------------------------------------------------------
@multi_asset(
    group_name="extraction_aic",
    outs={
        "raw_aic_artworks": AssetOut(key=dbt_source_asset_key("aic", "raw_aic_artworks")),
        "raw_aic_agents": AssetOut(key=dbt_source_asset_key("aic", "raw_aic_agents")),
    },
    compute_kind="python",
)
def aic_snapshot(context: AssetExecutionContext):
    """Collect + ingest AIC in one run: download the S3 tar.bz2 dump, extract
    artworks + agents, transform to NDJSON, PUT to the Bronze stage, COPY into a
    temp table, and MERGE into BRONZE.RAW_AIC_ARTWORKS + RAW_AIC_AGENTS (with
    deaccession soft-delete). This is the fully-implemented `snapshot` path in
    extraction/aic/loader.py -- it needs outbound HTTPS to the AIC S3 bucket and
    ~2 GB local disk for the dump/extract.
    """
    _run_module(context, ["extraction.aic.run", "snapshot"])
    return (
        MaterializeResult(
            asset_key=dbt_source_asset_key("aic", "raw_aic_artworks"),
            metadata={"phase": "aic-snapshot"},
        ),
        MaterializeResult(
            asset_key=dbt_source_asset_key("aic", "raw_aic_agents"),
            metadata={"phase": "aic-snapshot"},
        ),
    )
