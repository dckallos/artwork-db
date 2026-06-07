"""
Configuration and environment loading for the AIC extractor.

Loads credentials and runtime settings from environment variables, with
sensible defaults. All settings can be overridden via .env or shell env.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load .env from current working directory if present.
load_dotenv()

# AIC data dump: a ~115 MB tar.bz2 containing individual JSON files per entity.
AIC_DUMP_URL = "https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2"

# AIC public API base (for future delta path).
AIC_API_BASE = "https://api.artic.edu/api/v1"

# IIIF image service base URL (stable; from AIC's config.json endpoint).
AIC_IIIF_BASE = "https://www.artic.edu/iiif/2"

# Default image width (standard resolution per AIC recommendation).
AIC_DEFAULT_IMAGE_WIDTH = 843

# Max records per API search page (API-imposed ceiling).
AIC_API_PAGE_SIZE = 100

# Tier 1 entity folders to selectively extract from the tar.bz2.
AIC_TIER1_ENTITIES: List[str] = ["artworks", "agents"]

# Batch ID prefixes for provenance tracking (snap_* vs delta_*).
BATCH_PREFIX_SNAPSHOT = "snap"
BATCH_PREFIX_DELTA = "delta"


@dataclass
class Config:
    """Runtime configuration for the AIC extraction pipeline."""

    # Local file paths for the downloaded dump and extracted data.
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("AIC_DATA_DIR", "./data"))
    )
    tar_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("AIC_TAR_PATH", "./data/aic_dump.tar.bz2")
        )
    )
    extract_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("AIC_EXTRACT_DIR", "./data/aic_extract")
        )
    )

    # Dump download URL (override only if S3 path changes).
    dump_url: str = field(default_factory=lambda: os.getenv("AIC_DUMP_URL", AIC_DUMP_URL))

    # Snowflake connection. Uses the same key-pair auth as the Met loader:
    # ARTWORK_LOADER_SVC is TYPE = SERVICE with no password.
    snowflake_account: Optional[str] = os.getenv("SNOWFLAKE_ACCOUNT")
    snowflake_user: Optional[str] = os.getenv("SNOWFLAKE_USER")
    snowflake_private_key_file: Optional[str] = os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE")
    snowflake_private_key_file_pwd: Optional[str] = None
    snowflake_role: str = os.getenv("SNOWFLAKE_ROLE", "ARTWORK_LOADER")
    snowflake_warehouse: str = os.getenv("SNOWFLAKE_WAREHOUSE", "ARTWORK_WH")
    snowflake_database: str = os.getenv("SNOWFLAKE_DATABASE", "ARTWORK_DB")
    snowflake_schema: str = "BRONZE"
    snowflake_stage: str = "bronze_load_stage"

    def ensure_paths(self) -> None:
        """Create parent directories for local data files if missing."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tar_path.parent.mkdir(parents=True, exist_ok=True)
