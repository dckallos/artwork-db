"""
Custom dbt<->Dagster asset-key mapping.

The default translator would give dbt sources their own asset keys that don't
line up with our Python extraction assets. By mapping every dbt source to
``AssetKey([source_name, table_name])`` -- and keying the extraction assets the
same way (see factories/assets.py) -- the dbt models that ``source()`` these
tables automatically gain an upstream dependency on the extraction that
produces them. That gives you end-to-end lineage:

    <source>_snapshot -> <source>_control -> raw_<source>_objects -> dbt models
"""
from __future__ import annotations

from typing import Any, Mapping

from dagster import AssetKey
from dagster_dbt import DagsterDbtTranslator


def dbt_source_asset_key(source_name: str, table_name: str) -> AssetKey:
    """
    The single source-key scheme shared by dbt sources and extraction assets.
    """
    return AssetKey([source_name, table_name])


class ArtworkDbtTranslator(DagsterDbtTranslator):
    """
    Map dbt sources onto the extraction assets that populate them.
    """

    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        if dbt_resource_props.get("resource_type") == "source":
            return dbt_source_asset_key(
                dbt_resource_props["source_name"],
                dbt_resource_props["name"],
            )
        return super().get_asset_key(dbt_resource_props)
