"""
Acceptance coverage for the prime directive: a new source is discovered from a
single YAML file with ZERO framework ``.py`` edits.

This replaces the implicit source-decoupling proof the removed CMA placeholder
used to provide (issue #23, Option A). The fixture source lives under
``tests/fixtures/sources/`` -- never in the production-like package registry --
and is parsed through the same :func:`load_source_specs` path production uses.

``loader`` transitively imports :mod:`artwork_orchestration.spec`, which imports
the Dagster ``AssetKey`` type, so this test self-skips where Dagster is absent
(matching the suite's integration tests).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("dagster", reason="loader.spec imports the Dagster AssetKey type")

from artwork_orchestration.loader import load_source_specs  # noqa: E402

_FIXTURE_SOURCES = Path(__file__).resolve().parents[1] / "fixtures" / "sources"


def test_a_new_source_yaml_is_discovered_without_framework_edits() -> None:
    """
    Dropping one ``<key>.yaml`` into a sources dir registers a fully-typed source.
    """
    specs = load_source_specs(str(_FIXTURE_SOURCES))
    by_key = {s.key: s for s in specs}

    assert "example_museum" in by_key, (
        "load_source_specs must discover a source purely from its YAML file "
        "(no framework .py edit registers it)"
    )
    spec = by_key["example_museum"]
    assert spec.cli_module == "extraction.example_museum.run"
    assert spec.group_name == "extraction_example_museum"

    tables = [produced.table for _step, produced in spec.iter_produces()]
    assert tables == ["raw_example_museum_objects", "raw_example_museum_agents"]

    # The bare-string produce is a dbt-source terminal (keeps dbt lineage); the
    # mapping produce carries the auto non-empty asset-check flag.
    terminals = [p.table for _s, p in spec.iter_produces() if p.dbt_source]
    assert "raw_example_museum_agents" in terminals
    objects = spec.find_produce("raw_example_museum_objects")
    assert objects is not None and objects.nonempty is True
