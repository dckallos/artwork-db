"""Derive dbt model facts from the compiled manifest -- so nothing here is hand-listed.

The Gold marts that get a freshness check used to be a hardcoded list in
``framework.yaml``. That is a maintained duplicate of what dbt already declares. Instead
we read the compiled ``manifest.json`` and select the models dbt itself tags as marts
(``dbt_project.yml`` sets ``marts: +tags: ["marts"]``). The list therefore scales with
the dbt project automatically, with no orchestration-side edits.

Fully best-effort and offline-safe: if the manifest has not been built yet (it requires
``dbt parse``/``dbt build``), every function returns ``[]`` and the caller falls back to
whatever is configured. No dbt import and no network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .config import FRAMEWORK, REPO_ROOT

# The dbt project dir is where profiles.yml lives (single-sourced from framework.yaml);
# the compiled manifest is always <project>/target/manifest.json.
_MANIFEST_PATH = REPO_ROOT / FRAMEWORK.connection.profiles_dir / "target" / "manifest.json"

_MART_TAG = "marts"


def _load_manifest() -> dict:
    try:
        return json.loads(_MANIFEST_PATH.read_text())
    except Exception:  # noqa: BLE001 -- missing/unparsed manifest is expected offline
        return {}


def models_tagged(tag: str) -> List[str]:
    """Names of dbt models carrying ``tag`` in the compiled manifest (sorted)."""
    manifest = _load_manifest()
    names = {
        node.get("name")
        for node in manifest.get("nodes", {}).values()
        if node.get("resource_type") == "model" and tag in (node.get("tags") or [])
        if node.get("name")
    }
    return sorted(names)


def gold_mart_names() -> List[str]:
    """dbt Gold mart model names, derived from the manifest (``[]`` if not built yet)."""
    return models_tagged(_MART_TAG)
