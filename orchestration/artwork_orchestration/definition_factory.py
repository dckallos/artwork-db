"""
Definitions factory for testable Dagster code-location assembly.

This module intentionally does NOT import the real dbt asset module at import time. The
default Dagster entry point still lives in ``definitions.py``; this module provides the
injectable construction seam used by tests and tooling, so a test can assemble a code
location with STUB dbt assets/resources without a built manifest.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from dagster import Definitions

from .config import FRAMEWORK
from .dbt_manifest import gold_mart_names
from .factories.assets import build_source_assets
from .factories.checks import build_freshness_checks, build_source_checks
from .factories.jobs import build_jobs
from .factories.schedules import build_schedules
from .loader import load_source_specs
from .model import FrameworkConfig
from .sources import REGISTRY
from .spec import SourceRegistry


def derive_gold_marts(framework: FrameworkConfig) -> List[str]:
    """
    Return dbt Gold mart names from the manifest, falling back to framework config.
    """
    return gold_mart_names() or list(framework.freshness.gold_marts)


def assemble_definition_parts(
    framework: FrameworkConfig,
    registry: SourceRegistry,
    dbt_assets,
    *,
    gold_marts: Optional[Sequence[str]] = None,
):
    """
    Build extraction assets, checks, jobs and schedules from explicit inputs.

    Pure: depends only on its arguments, so it is safe to call repeatedly (tooling, tests)
    and against fixture registries. Returns a 4-tuple.

    Args:
        framework: Parsed framework configuration.
        registry: Source registry to assemble.
        dbt_assets: dbt asset definition to include in the dbt-only job.
        gold_marts: Optional pre-derived Gold mart names. Supplying this keeps callers from
            re-reading the manifest when they already have the list.
    """
    marts = list(gold_marts) if gold_marts is not None else derive_gold_marts(framework)

    extraction_assets = [a for spec in registry for a in build_source_assets(spec)]
    asset_checks = [c for spec in registry for c in build_source_checks(spec)]
    asset_checks += build_freshness_checks(
        registry,
        gold_assets=marts,
        gold_lag_hours=framework.freshness.gold_lag_hours,
    )
    jobs = build_jobs(registry, dbt_assets=dbt_assets)
    schedules = build_schedules(registry, {j.name: j for j in jobs})
    return extraction_assets, asset_checks, jobs, schedules


def _default_dbt_assets():
    """
    Load the real dbt assets only when a caller actually needs them.
    """
    from .assets_dbt import artwork_dbt_assets

    return artwork_dbt_assets


def _default_dbt_resource():
    """
    Load the real dbt resource only when a caller actually needs it.
    """
    from .resources import dbt_resource

    return dbt_resource


def build_definitions(
    framework: Optional[FrameworkConfig] = None,
    sources_dir: Optional[str] = None,
    *,
    dbt_assets=None,
    dbt_resource_obj=None,
) -> Definitions:
    """
    Assemble a :class:`~dagster.Definitions` from explicit inputs.

    Args:
        framework: Framework config to use; defaults to the loaded :data:`FRAMEWORK`.
        sources_dir: Directory to scan for ``*.yaml`` source specs; defaults to the packaged
            ``sources/`` registry (:data:`REGISTRY`). Pass a temp dir to test that a new
            source needs zero framework ``.py`` edits.
        dbt_assets: dbt assets definition to include. Tests may pass a stub so importing this
            factory does not require a built manifest.
        dbt_resource_obj: The ``"dbt"`` resource. Tests may pass a stub resource.
    """
    fw = framework or FRAMEWORK
    registry: SourceRegistry = (
        SourceRegistry(load_source_specs(sources_dir)) if sources_dir is not None else REGISTRY
    )
    the_dbt_assets = dbt_assets if dbt_assets is not None else _default_dbt_assets()
    the_dbt_resource = (
        dbt_resource_obj if dbt_resource_obj is not None else _default_dbt_resource()
    )

    extraction_assets, asset_checks, jobs, schedules = assemble_definition_parts(
        fw,
        registry,
        the_dbt_assets,
    )
    return Definitions(
        assets=[*extraction_assets, the_dbt_assets],
        asset_checks=asset_checks,
        jobs=jobs,
        schedules=schedules,
        resources={"dbt": the_dbt_resource},
    )
