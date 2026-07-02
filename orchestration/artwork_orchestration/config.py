"""Central configuration for the orchestration layer.

Two things live here, both deliberately dependency-light so importing this module
never drags in the dbt stack:

* ``REPO_ROOT`` -- the single home for the repo path (resources.py, _runner.py,
  _snowflake.py, _connection.py all import it from here).
* ``FRAMEWORK`` / ``BRONZE`` -- the parsed, validated engine config loaded from
  ``framework.yaml`` (see loader.py + model.py). Everything that used to be a hardcoded
  ``ARTWORK_DB.BRONZE.<TABLE>`` string now flows through ``BRONZE.fqn(...)``; the
  database/schema (and every other knob) are set ONCE, in YAML, not in Python.
"""
from __future__ import annotations

from pathlib import Path

from .loader import load_framework_config

# config.py lives at orchestration/artwork_orchestration/config.py, so the repo root is
# three parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]

# The whole Layer-A engine config, parsed + validated from framework.yaml (cached).
FRAMEWORK = load_framework_config()

# Location of the raw (Bronze) landing tables; import this rather than hardcoding names.
BRONZE = FRAMEWORK.bronze
