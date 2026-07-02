"""AIC (Art Institute of Chicago) source spec -- PURE DATA.

The AIC pipeline is the simple case: a single ``snapshot`` run downloads the S3
data dump and populates TWO Bronze tables (artworks + agents) in one shot. Because
the step produces two dbt-source tables, the asset factory emits a multi_asset.
"""
from __future__ import annotations

from ..policies import TIMEOUT_SNAPSHOT
from .spec import ExtractionStep, Produces, SourceSpec

AIC_SPEC = SourceSpec(
    key="aic",
    cli_module="extraction.aic.run",
    steps=(
        ExtractionStep(
            name="snapshot",
            subcommand="snapshot",
            timeout_s=TIMEOUT_SNAPSHOT,
            produces=(
                Produces("raw_aic_artworks", dbt_source=True, nonempty=True,
                         nonempty_severity="ERROR", freshness_days=8),
                Produces("raw_aic_agents", dbt_source=True),
            ),
        ),
    ),
)
