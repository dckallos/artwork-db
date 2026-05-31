---
name: run-met-loader
description: Run the Met Museum data loader with monitoring
---

# /run-met-loader

Run Met extraction with proper monitoring and error handling.

## What it does

1. Checks prerequisites (Bronze tables, credentials)
2. Shows current Bronze state
3. Runs the specified phase or full pipeline
4. Monitors progress
5. Shows results

## Usage

```
/run-met-loader              # Run full pipeline
/run-met-loader bootstrap    # Download CSV only
/run-met-loader enrich       # API enrichment only
/run-met-loader upload       # Upload to Bronze only
/run-met-loader status       # Check current status
```

## Implementation

```bash
#!/bin/bash
set -euo pipefail

PHASE="${1:-all}"

# Check prerequisites
echo "==> Checking prerequisites..."

# Check Bronze tables exist
if ! scripts/check.sh scripts/sql/show_pipeline_status.sql | grep -q "MET_ENRICHMENT_CONTROL"; then
    echo "ERROR: Bronze tables not found. Run 'make infra' first."
    exit 1
fi

# Check .env exists
if [[ ! -f .env ]]; then
    echo "ERROR: .env file not found. Copy from .env.example and configure."
    exit 1
fi

# Show current state
echo -e "\n==> Current Bronze state:"
snow sql --connection admin --query "
SELECT 
    'MET_ENRICHMENT_CONTROL' as table_name,
    COUNT(*) as row_count,
    COUNT(CASE WHEN enrichment_status = 'completed' THEN 1 END) as completed,
    COUNT(CASE WHEN enrichment_status = 'in_progress' THEN 1 END) as in_progress,
    COUNT(CASE WHEN lease_holder IS NOT NULL AND lease_expiry > CURRENT_TIMESTAMP() THEN 1 END) as active_leases
FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL
UNION ALL
SELECT 
    'RAW_MET_OBJECTS' as table_name,
    COUNT(*) as row_count,
    NULL as completed,
    NULL as in_progress,
    NULL as active_leases
FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;
"

# Run the loader
echo -e "\n==> Running Met loader (phase: $PHASE)..."
if [[ "$PHASE" == "status" ]]; then
    python -m extraction.met.run --phase status
else
    # Run with timestamp tracking
    START_TIME=$(date +%s)
    python -m extraction.met.run --phase "$PHASE"
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    echo -e "\n==> Extraction completed in ${DURATION} seconds"
    
    # Show results
    echo -e "\n==> Post-run Bronze state:"
    snow sql --connection admin --query "
    SELECT 
        COUNT(*) as total_objects,
        COUNT(CASE WHEN enrichment_status = 'completed' THEN 1 END) as enriched,
        MAX(last_updated) as latest_update
    FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL;
    "
fi
```