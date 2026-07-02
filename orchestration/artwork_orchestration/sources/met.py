"""Met (Metropolitan Museum of Art) source spec -- PURE DATA.

The Met pipeline is the complex case: a CSV snapshot, a seeded control table, a
bounded + department-partitioned + rate-limited enrichment step (one Met API call
per object against a single global rate cap), and a terminal verification asset.

Adding another museum with the same shape = copy this file, change the values.
"""
from __future__ import annotations

from ..policies import TIMEOUT_ENRICH_BATCH, TIMEOUT_SEED, TIMEOUT_SNAPSHOT
from .spec import ExtractionStep, HealthCheck, PartitionDim, Produces, SourceSpec

# Partition KEYS are slugs (Dagster forbids commas/brackets in keys); the value is
# the exact department string the enrich CLI binds behind --department. 19 depts.
MET_DEPARTMENTS = PartitionDim(
    name="department",
    cli_flag="--department",
    values={
        "ancient_near_eastern_art": "Ancient Near Eastern Art",
        "arms_and_armor": "Arms and Armor",
        "arts_of_africa_oceania_americas": "Arts of Africa, Oceania, and the Americas",
        "asian_art": "Asian Art",
        "costume_institute": "Costume Institute",
        "drawings_and_prints": "Drawings and Prints",
        "egyptian_art": "Egyptian Art",
        "european_paintings": "European Paintings",
        "european_sculpture_decorative_arts": "European Sculpture and Decorative Arts",
        "greek_and_roman_art": "Greek and Roman Art",
        "islamic_art": "Islamic Art",
        "medieval_art": "Medieval Art",
        "modern_contemporary_art": "Modern and Contemporary Art",
        "musical_instruments": "Musical Instruments",
        "photographs": "Photographs",
        "robert_lehman_collection": "Robert Lehman Collection",
        "the_american_wing": "The American Wing",
        "the_cloisters": "The Cloisters",
        "the_libraries": "The Libraries",
    },
)

MET_SPEC = SourceSpec(
    key="met",
    cli_module="extraction.met.run",
    rps_env_var="MET_API_RPS",
    steps=(
        # Phase 1: load the Met OpenAccess CSV into BRONZE.MET_CSV_SNAPSHOT.
        ExtractionStep(
            name="csv_snapshot",
            subcommand="snapshot",
            produces=(Produces("csv_snapshot", physical="MET_CSV_SNAPSHOT"),),
            timeout_s=TIMEOUT_SNAPSHOT,
        ),
        # Phase 2: seed MET_ENRICHMENT_CONTROL from the snapshot (a dbt source).
        ExtractionStep(
            name="enrichment_control",
            subcommand="seed-control",
            produces=(Produces("met_enrichment_control", dbt_source=True),),
            timeout_s=TIMEOUT_SEED,
            extra_metadata_sql={
                "pending": "SELECT COUNT(*) FROM {db}.{schema}.MET_ENRICHMENT_CONTROL "
                           "WHERE enrichment_status = 'pending'",
            },
        ),
        # Phase 3: bounded, department-partitioned, rate-limited enrichment. Claims a
        # slice of ONE department's worklist and assembles rows into RAW_MET_OBJECTS.
        ExtractionStep(
            name="enrichment_batch",
            subcommand="enrich-met",
            produces=(Produces("enrichment_batch"),),  # internal step asset; no table of its own
            partition=MET_DEPARTMENTS,
            uses_batch_flags=True,
            rate_limited=True,
            timeout_s=TIMEOUT_ENRICH_BATCH,
            extra_metadata_sql={
                "department_worklist_remaining":
                    "SELECT COUNT(*) FROM {db}.{schema}.MET_WORKLIST "
                    "WHERE department = '{partition_value}'",
                "department_done":
                    "SELECT COUNT(*) FROM {db}.{schema}.MET_ENRICHMENT_CONTROL c "
                    "JOIN {db}.{schema}.MET_CSV_SNAPSHOT s ON s.object_id = c.object_id "
                    "WHERE c.enrichment_status = 'done' "
                    "AND s.raw_payload:department::STRING = '{partition_value}'",
            },
        ),
        # Phase 4: terminal dbt source. Verify-only (no CLI) -- rows are assembled
        # server-side inside each enrichment batch; this reports the current state.
        ExtractionStep(
            name="raw_met_objects",
            subcommand=None,
            api_bound=False,
            produces=(
                Produces("raw_met_objects", dbt_source=True, nonempty=True,
                         nonempty_severity="ERROR", freshness_days=8),
            ),
            timeout_s=TIMEOUT_SEED,
            extra_metadata_sql={
                "with_primary_image": "SELECT COUNT(*) FROM {db}.{schema}.RAW_MET_OBJECTS "
                                      "WHERE has_primary_image = TRUE",
                "worklist_remaining": "SELECT COUNT(*) FROM {db}.{schema}.MET_WORKLIST",
            },
        ),
    ),
    checks=(
        HealthCheck(
            name="met_no_orphaned_leases",
            attach_table="met_enrichment_control",
            sql="SELECT COUNT(*) FROM {db}.{schema}.MET_ENRICHMENT_CONTROL "
                "WHERE claimed_at IS NOT NULL "
                "AND claimed_at < DATEADD('minute', -30, CURRENT_TIMESTAMP())",
            passes=lambda n: n == 0,
            severity="WARN",
            description="No worklist leases older than the 30-min reclaim TTL.",
        ),
    ),
)
