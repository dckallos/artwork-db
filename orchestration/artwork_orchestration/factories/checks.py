"""Asset-check + freshness-check factory (generated from SourceSpecs).

Two sources of checks:
  * Non-empty checks -- auto-generated for every ``Produces(nonempty=True)`` table.
  * Custom checks    -- each ``SourceSpec.checks`` HealthCheck (e.g. 'no orphaned
    worklist leases').

All checks are BEST EFFORT: if Snowflake is unreachable the check returns
passed=False at WARN ("could not verify") rather than a hard failure, so a missing
driver in a dev shell is visible but non-blocking. Freshness checks come from every
``Produces(freshness_days=...)`` plus a static list of dbt Gold marts.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Sequence

from dagster import AssetCheckResult, AssetCheckSeverity, AssetKey, asset_check

from .._snowflake import render, sf_scalars
from ..config import BRONZE
from ..sources.spec import HealthCheck, Produces, SourceSpec

_SEVERITY = {"ERROR": AssetCheckSeverity.ERROR, "WARN": AssetCheckSeverity.WARN}


def _unverified() -> AssetCheckResult:
    return AssetCheckResult(
        passed=False,
        severity=AssetCheckSeverity.WARN,
        metadata={"error": "could not verify (no Snowflake connection)"},
    )


def _nonempty_check(spec: SourceSpec, produced: Produces):
    key = produced.asset_key(spec.key)
    sql = f"SELECT COUNT(*) FROM {BRONZE.fqn(produced.physical_table())}"

    @asset_check(
        asset=key,
        name=f"{produced.table}_has_rows",
        description=f"{produced.physical_table()} must be non-empty.",
        blocking=False,
    )
    def _check(context) -> AssetCheckResult:
        res = sf_scalars(context, {"rows": sql})
        if "rows" not in res:
            return _unverified()
        rows = res["rows"]
        return AssetCheckResult(
            passed=rows > 0,
            severity=_SEVERITY.get(produced.nonempty_severity, AssetCheckSeverity.ERROR),
            metadata={"rows": rows},
        )

    _check.__name__ = f"{spec.key}_{produced.table}_has_rows"
    return _check


def _custom_check(spec: SourceSpec, hc: HealthCheck):
    produced = spec.find_produce(hc.attach_table)
    if produced is None:  # pragma: no cover - defensive: spec authoring error
        raise ValueError(
            f"{spec.key} HealthCheck {hc.name!r} attaches to unknown table "
            f"{hc.attach_table!r}."
        )
    key = produced.asset_key(spec.key)

    @asset_check(asset=key, name=hc.name, description=hc.description, blocking=False)
    def _check(context) -> AssetCheckResult:
        res = sf_scalars(context, {"value": render(hc.sql)})
        if "value" not in res:
            return _unverified()
        value = res["value"]
        return AssetCheckResult(
            passed=hc.passes(value),
            severity=_SEVERITY.get(hc.severity, AssetCheckSeverity.WARN),
            metadata={hc.name: value},
        )

    _check.__name__ = f"{spec.key}_{hc.name}"
    return _check


def build_source_checks(spec: SourceSpec) -> List:
    """Auto non-empty checks + declared custom checks for one source."""
    checks: List = []
    for _step, produced in spec.iter_produces():
        if produced.nonempty:
            checks.append(_nonempty_check(spec, produced))
    for hc in spec.checks:
        checks.append(_custom_check(spec, hc))
    return checks


def build_freshness_checks(
    registry: Sequence[SourceSpec],
    gold_assets: Sequence[str] = (),
    gold_lag_hours: float = 30,
) -> List:
    """Freshness checks for every ``Produces(freshness_days=...)`` + the dbt Gold marts.

    Imported defensively: on a Dagster build without the freshness helper this
    degrades to [] rather than breaking the whole code location.
    """
    try:
        from dagster import build_last_update_freshness_checks  # type: ignore
    except Exception:  # noqa: BLE001
        return []

    checks: List = []
    for spec in registry:
        for _step, produced in spec.iter_produces():
            if produced.freshness_days is not None:
                checks += list(
                    build_last_update_freshness_checks(
                        assets=[produced.asset_key(spec.key)],
                        lower_bound_delta=timedelta(days=produced.freshness_days),
                    )
                )
    if gold_assets:
        checks += list(
            build_last_update_freshness_checks(
                assets=[AssetKey([a]) for a in gold_assets],
                lower_bound_delta=timedelta(hours=gold_lag_hours),
            )
        )
    return checks
