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

# MetObjects.csv is stored via Git LFS. raw.githubusercontent.com serves the
# ~130-byte LFS *pointer*, not the file; the media host serves real LFS content
# (DATA-06). Override with MET_CSV_URL if the path ever changes.
MET_CSV_URL = (
    "https://media.githubusercontent.com/media/metmuseum/openaccess/master/MetObjects.csv"
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
    csv_url: str = field(default_factory=lambda: os.getenv("MET_CSV_URL", MET_CSV_URL))
    csv_local_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("MET_CSV_LOCAL_PATH", "./data/MetObjects.csv")
        )
    )

    # API enrichment tuning. Met allows ~80 rps but empirically returns 403 as
    # a soft-throttle well below that ceiling (owner's 2026-05-31 200-row run:
    # 104/200 went 403 at ~11 rps observed). The defaults below match the prior
    # production project's tuning -- modest concurrency, conservative target RPS
    # that the adaptive limiter then nudges up via cool_up() on every success.
    # MAX_RETRIES=8 is large enough that a Retry-After-driven backoff sequence
    # (e.g. 1s, 2s, 4s, 8s, 16s, 30s, 30s) can ride out a sustained throttle.
    api_base: str = MET_API_BASE
    # At 40 rps (often decaying to 5-10 under throttle), >3 workers adds
    # contention without throughput gain. Reserved for future threading use.
    api_max_concurrency: int = int(os.getenv("MET_API_CONCURRENCY", "3"))
    api_requests_per_second: float = float(os.getenv("MET_API_RPS", "40"))
    api_max_retries: int = int(os.getenv("MET_API_MAX_RETRIES", "8"))
    api_request_timeout_seconds: int = int(os.getenv("MET_API_TIMEOUT", "20"))
    api_user_agent: str = os.getenv(
        "MET_API_USER_AGENT",
        "artwork-db/1.0 (contact: daniel@porchanalytics.com)",
    )

    # Snowflake connection. Bronze loader role/warehouse/db/schema/stage match
    # the objects created under infrastructure/. Authentication is KEY-PAIR:
    # ARTWORK_LOADER_SVC is a TYPE = SERVICE user with no password, so we point
    # the connector at the same private key registered by
    # scripts/snowflake_cli/06_setup_loader_keypair.sh. No password at rest.
    snowflake_account: Optional[str] = os.getenv("SNOWFLAKE_ACCOUNT")
    snowflake_user: Optional[str] = os.getenv("SNOWFLAKE_USER")
    snowflake_private_key_file: Optional[str] = os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE")
    # Only needed if the private key is an ENCRYPTED PKCS#8 file; the keys minted
    # by 06_setup_loader_keypair.sh are unencrypted (-nocrypt), so this is None.
    snowflake_private_key_file_pwd: Optional[str] = os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE_PWD")
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