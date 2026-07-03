"""
Integration smoke test for manifest-free definitions factory assembly.

This exercises the injectable factory path with stub dbt assets/resources. The real
Dagster code-location smoke test (``test_definitions_smoke.py``) may still rely on a built
dbt manifest; this test proves the pure assembly seam can be imported and used without one.
"""
from __future__ import annotations

import pytest

pytest.importorskip("dagster", reason="integration tests require the Dagster runtime")

from dagster import Definitions, ResourceDefinition, asset  # noqa: E402

from artwork_orchestration.definition_factory import build_definitions  # noqa: E402


@asset(name="stub_dbt_asset")
def stub_dbt_asset() -> None:
    """
    Small stand-in for the manifest-backed dbt assets definition.
    """


def test_build_definitions_accepts_stubbed_dbt_components() -> None:
    """
    build_definitions assembles with stub dbt assets/resource and no built manifest.
    """
    defs = build_definitions(
        dbt_assets=stub_dbt_asset,
        dbt_resource_obj=ResourceDefinition.hardcoded_resource(object()),
    )
    assert isinstance(defs, Definitions)
    assert list(defs.assets)
    assert "dbt" in defs.resources
