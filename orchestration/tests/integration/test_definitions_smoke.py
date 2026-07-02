"""Integration smoke test for the assembled code location.

Verifies the Phase-2 refactor did not break ``build_definitions()`` assembly. Requires a
real Dagster (and a built dbt manifest for the default registry), so it is skipped where
Dagster is unavailable. The exhaustive definitions-load parity checks (asset keys, partition
counts, per-source tags) are tracked separately under issue #6 section 4.
"""
from __future__ import annotations

import pytest

pytest.importorskip("dagster", reason="integration tests require the Dagster runtime")

from dagster import Definitions  # noqa: E402

from artwork_orchestration.definitions import build_definitions  # noqa: E402


def test_build_definitions_returns_a_definitions_with_assets() -> None:
    defs = build_definitions()
    assert isinstance(defs, Definitions)
    # At least the dbt assets are always present; extraction assets come from the registry.
    assert list(defs.assets)
    assert "dbt" in defs.resources
