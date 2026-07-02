"""Central configuration for the orchestration layer.

Everything that used to be a hardcoded ``ARTWORK_DB.BRONZE.<TABLE>`` string now
flows through :class:`BronzeConfig`, so the database/schema are set ONCE (and are
env-overridable for dev/stage/prod) instead of being copied into every asset,
check, and metadata query.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Repo root: config.py lives at orchestration/artwork_orchestration/config.py, so the
# repo root is three parents up. This is the single home for the path (resources.py,
# _runner.py and _snowflake.py all import it from here) -- deliberately dependency-free
# so importing it never drags in the dbt stack.
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BronzeConfig:
    """Location of the raw (Bronze) landing tables in Snowflake.

    Overridable via ``ARTWORK_DB`` / ``ARTWORK_BRONZE_SCHEMA`` so the same code
    runs against a dev/stage/prod database without edits.
    """

    database: str = os.getenv("ARTWORK_DB", "ARTWORK_DB")
    schema: str = os.getenv("ARTWORK_BRONZE_SCHEMA", "BRONZE")

    def fqn(self, table: str) -> str:
        """Fully-qualified name for a Bronze table, e.g. ``ARTWORK_DB.BRONZE.RAW_MET_OBJECTS``."""
        return f"{self.database}.{self.schema}.{table.upper()}"


# One shared instance; import this rather than constructing your own.
BRONZE = BronzeConfig()
