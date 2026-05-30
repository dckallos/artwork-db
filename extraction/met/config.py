"""
Configuration and environment loading for the Met extractor.

Loads credentials and runtime settings from environment variables, with
sensible defaults. All settings can be overridden via .env or shell env.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from current working directory if present.
load_dotenv()

MET_CSV_URL = (
    "https://raw.githubusercontent.com/metmuseum/openaccess/master/MetObjects.csv"
)
MET_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


@dataclass
class Config:
    """Runtime configuration for the Met extraction pipeline."""

    # Local SQLite database path -- intermediate state only.
    sqlite_path: Path = field(
        default_factory=lambda: Path(os.getenv("MET_SQLITE_PATH", "./data/met.db"))
    )

    # CSV bootstrap inputs.
    csv_url: str = MET_CSV_URL
    csv_local_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("MET_CSV_LOCAL_PATH", "./data/MetObjects.csv")
        )
    )

    # API enrichment tuning. Met allows ~80 rps; 20 is a polite default.
    api_base: str = MET_API_BASE
    api_max_concurrency: int = int(os.getenv("MET_API_CONCURRENCY", "10"))
    api_requests_per_second: float = float(os.getenv("MET_API_RPS", "20"))
    api_max_retries: int = int(os.getenv("MET_API_MAX_RETRIES", "5"))
    api_request_timeout_seconds: int = int(os.getenv("MET_API_TIMEOUT", "30"))
    api_user_agent: str = os.getenv(
        "MET_API_USER_AGENT",
        "artwork-db/1.0 (contact: daniel@porchanalytics.com)",
    )

    # Snowflake connection. Bronze loader role/warehouse/db/schema/stage match
    # the objects created in infrastructure/V001-V007.
    snowflake_account: Optional[str] = os.getenv("SNOWFLAKE_ACCOUNT")
    snowflake_user: Optional[str] = os.getenv("SNOWFLAKE_USER")
    snowflake_password: Optional[str] = os.getenv("SNOWFLAKE_PASSWORD")
    snowflake_role: str = os.getenv("SNOWFLAKE_ROLE", "ARTWORK_LOADER")
    snowflake_warehouse: str = os.getenv("SNOWFLAKE_WAREHOUSE", "ARTWORK_WH")
    snowflake_database: str = os.getenv("SNOWFLAKE_DATABASE", "ARTWORK_DB")
    snowflake_schema: str = os.getenv("SNOWFLAKE_SCHEMA", "BRONZE")
    snowflake_table: str = os.getenv("SNOWFLAKE_TABLE", "raw_met_objects")
    snowflake_stage: str = os.getenv("SNOWFLAKE_STAGE", "bronze_load_stage")

    # Upload chunk size: rows per NDJSON file / COPY INTO operation.
    upload_chunk_size: int = int(os.getenv("MET_UPLOAD_CHUNK", "5000"))

    def ensure_paths(self) -> None:
        """Create parent directories for local data files if missing."""
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.csv_local_path.parent.mkdir(parents=True, exist_ok=True)