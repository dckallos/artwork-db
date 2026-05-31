# Met Extraction Pipeline Code Review

**Date:** 2026-05-31  
**Reviewer:** Claude (Senior Data Engineer perspective)  
**Scope:** Met extraction pipeline (Phase 1 snapshot + Phase 2 control seed + Phase 3 lease-claim enrichment)

## Executive Summary

**Overall Health:** The Met pipeline is well-architected with clear separation of concerns, proper error handling, and thoughtful design choices. However, it **fundamentally violates** the repo's core convention that ALL Snowflake access must go through the Snowflake CLI (`snow sql`), not the Python connector.

**CLI Migration Recommendation:** **PARTIAL MIGRATION** - Migrate Phase 2 (control seeder) and read-only operations to CLI. Keep the connector for Phase 3's complex transactional work (lease claim + staging + assembly + callback) where CLI atomicity would be harder and riskier. This balances convention compliance with pragmatic engineering.

## BLOCKER - CLI Convention Violation

### Current State

The repository has a clear, documented convention enforced by the orchestration layer:
- ALL Snowflake DDL/operations go through `snow sql -c <connection> -f <file>.sql`
- Scripts like `apply_sql.sh`, `check.sh`, `checkpoint.sh` wrap the CLI
- Key-pair auth is configured in `~/.snowflake/config.toml` connections

Yet the extraction code directly imports and uses `snowflake.connector`:
- `snowflake_uploader.py:148` - `_snowflake_connect()` opens direct connection
- `control_seeder.py:138` - Direct connection for MERGE
- `met_enricher.py:248` - Direct connection for complex multi-statement transaction

### Impact of CLI Migration

**What the connector does today:**

1. **Single MERGE + result count** (control_seeder.py)
   - Seeds control table with WHERE predicate and LIMIT
   - Returns "rows inserted" count

2. **Multi-statement transaction** (met_enricher.py)
   - Claim UPDATE with lease
   - PUT staged files  
   - COPY INTO temp table
   - MERGE assembly
   - Batch callback UPDATE
   - Lease release on failure
   - All within transaction control

3. **PUT + COPY + mark uploaded** (snowflake_uploader.py)
   - Stage NDJSON files
   - COPY INTO bronze
   - Parse COPY result for row count

**CLI mapping analysis:**

1. **Single MERGE** → Easy CLI migration
   - `snow sql -c loader -f seed_control.sql -D "predicate=..." -D "limit=1000"`
   - Getting row count: Add `SELECT 'INSERTED:' || COUNT(*) FROM table_changes(...)` 

2. **Multi-statement transaction** → HARD atomicity challenge  
   - CLI runs each statement separately by default
   - Would need `BEGIN TRANSACTION; ... COMMIT;` wrapper
   - Error rollback harder to control
   - Lease atomicity critical for correctness

3. **PUT/COPY** → Moderate complexity
   - `snow stage copy` exists but different syntax
   - Need to parse result output for counts

### The Hidden Benefit

The entire `%`-binding bug class that plagued development (see `db.strip_sql_comments`, the `{predicate}` kwarg errors in progress log) **disappears** under CLI. The connector does `command % params` over the WHOLE string including comments; CLI's `-D` template substitution is cleaner.

## Severity-Ranked Findings

### BLOCKER

**[B1] CLI Convention Violation**  
**File:** All Python files using `snowflake.connector`  
**Why it matters:** Violates documented repo convention; creates maintenance split  
**Fix:** See detailed migration plan in "CLI Migration Specifics" section

### HIGH

**[H1] No Atomicity in Legacy Upload Path**  
**File:** `snowflake_uploader.py:186-209`  
**Issue:** Death after COPY but before `_mark_uploaded` → re-run re-uploads → Bronze duplicates  
**Why:** COPY with PURGE=TRUE destroys evidence; Bronze is append-only  
**Fix:** Already addressed in Phase 3 design (transactional assembly). Mark legacy path deprecated.

**[H2] Deaccession Blind Spot (DATA-01)**  
**File:** `csv_bootstrap.py` entire approach  
**Issue:** UPSERT-only into SQLite; vanished CSV rows never deleted  
**Why:** Directly violates owner's "timeliness/deaccession" cornerstone  
**Fix:** Already designed - `MET_CSV_SNAPSHOT` enables snapshot diff: 
```sql
-- Detect deaccessions
SELECT s1.object_id 
FROM MET_CSV_SNAPSHOT s1
LEFT JOIN MET_CSV_SNAPSHOT_CURRENT s2 ON s1.object_id = s2.object_id  
WHERE s2.object_id IS NULL;
```

### MEDIUM

**[M1] Memory Explosion on Large Batches**  
**File:** `met_enricher.py:153`  
```python
await asyncio.gather(*(worker(oid) for oid in object_ids))
```
**Issue:** Creates ALL tasks upfront for unlimited batch. With 471k rows, hundreds of MB overhead  
**Fix:** Batch the gather:
```python
GATHER_BATCH_SIZE = 1000
for i in range(0, len(object_ids), GATHER_BATCH_SIZE):
    batch = object_ids[i:i + GATHER_BATCH_SIZE]
    await asyncio.gather(*(worker(oid) for oid in batch))
```

**[M2] Missing Git LFS Pointer Guard**  
**File:** `csv_bootstrap.py:72-89` (download_csv)  
**Issue:** Could silently download 130-byte pointer instead of 280MB CSV  
**Fix:** Already implemented in `assert_real_met_csv()` but worth highlighting as it was a real bug

**[M3] SQLite PRAGMA Scope Bug**  
**File:** `db.py:46-52`  
**Issue:** `synchronous=NORMAL` set in schema.sql only affects initialization connection  
**Fix:** Set PRAGMAs in connect():
```python
def connect(sqlite_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(sqlite_path))
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")  
    conn.execute("PRAGMA busy_timeout = 5000")
```

### LOW

**[L1] Hardcoded Positional COPY Result**  
**File:** `snowflake_uploader.py:190`  
```python
rows_loaded = sum(int(r[3]) for r in result)
```
**Issue:** Brittle if Snowflake changes column order  
**Fix:** Parse by column name or document the assumption

**[L2] Duplicated Chunk Logic**  
**File:** `snowflake_uploader.py:242-267`  
**Issue:** Chunk flush logic repeated in loop + after loop  
**Fix:** Extract `_flush_chunk()` method

## CLI Migration Specifics

### Phase 2 - Control Seeder (RECOMMENDED TO MIGRATE)

**Current:**
```python
cur.execute(sql, params)
result = cur.fetchone()
inserted = int(result[0])
```

**CLI approach:**
```bash
# Create SQL file with result capture
cat > /tmp/seed_with_count.sql << 'EOF'
${ORIGINAL_SEED_SQL}
SELECT 'ROWS_INSERTED:' || COUNT(*) 
FROM table_changes('MET_ENRICHMENT_CONTROL', 'start_time');
EOF

# Execute and parse output
OUTPUT=$(snow sql -c loader -f /tmp/seed_with_count.sql \
  -D "predicate=is_public_domain=TRUE" -D "limit=1000")
INSERTED=$(echo "$OUTPUT" | grep "ROWS_INSERTED:" | cut -d: -f2)
```

### Phase 3 - Met Enricher (KEEP CONNECTOR)

The transaction complexity makes CLI migration risky:
- Atomic lease claim is critical
- Assembly coordinates 3 tables  
- Rollback on failure must be guaranteed
- Would require complex BEGIN/COMMIT wrapper

**Recommendation:** Document this as an approved exception with clear rationale.

### Utility Functions (RECOMMENDED TO MIGRATE)

Status checks, counts, simple SELECTs should all use CLI:
```python
def check_status_cli(limit: Optional[int] = None) -> str:
    """Check enrichment status using CLI."""
    cmd = ["snow", "sql", "-c", "loader", 
           "-f", "sql/check_status.sql"]
    if limit:
        cmd.extend(["-D", f"limit={limit}"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout
```

## Data Quality & Design Strengths

### Excellent Design Choices

1. **Batch-grained callbacks** - O(1) Snowflake roundtrips per batch, not O(N) per row
2. **Lease pattern** - Clean claim/release with TTL reclaim task  
3. **Server-side assembly** - 47 CSV columns never leave Snowflake
4. **Session temp tables** - Auto-cleanup on disconnect
5. **MERGE idempotency** - Re-runs don't corrupt state

### Observability

**[O1] Comprehensive EXTRACTION_LOG**  
All phases write start/complete/failed with row counts. Well done.

**[O2] Clear batch_id naming**  
`met_seed_20260531T093000Z_abc123` immediately identifies phase + time + uniqueness

## Security & Robustness

### Strengths

1. **No SQL injection** - All user values go through bind parameters
2. **Key-pair auth** - No passwords in code
3. **Private key path expansion** - Handles `~` correctly
4. **Error message truncation** - Prevents log spam

### Minor Improvements

**[S1] Add connection timeout**
```python
connect_kwargs["network_timeout"] = 30
connect_kwargs["connection_timeout"] = 60  
```

## Performance Observations

1. **Rate limiter works** - 20 RPS default is polite and tunable via env
2. **Chunked uploads** - 5000-row batches balance memory/throughput  
3. **VARIANT storage** - Correct choice for sparse Bronze data
4. **Index on lease timestamp** - Would help reclaim task when volume grows

## Documentation Quality

The SQL files have EXCELLENT documentation:
- Clear parameter explanations  
- Bind safety warnings
- Design rationale inline
- Example renders

Python docstrings are thorough with clear strategy sections.

## Recommendations Summary

1. **CRITICAL:** Migrate Phase 2 (control seeder) to CLI immediately - it's a simple MERGE
2. **PRACTICAL:** Keep Phase 3 (enricher) on connector with documented exception
3. **CLEANUP:** Mark legacy upload path deprecated - Phase 3 supersedes it
4. **FUTURE:** When volume grows, add INDEX on `claimed_at` for reclaim task
5. **TESTING:** The untested SQL templates need preflight validation

## Next Steps

1. Create `scripts/sql/seed_enrichment_control.sql` wrapper for CLI
2. Modify `control_seeder.py` to shell out to CLI
3. Document the enricher transaction as approved connector usage
4. Add integration test that validates atomicity 

This pipeline shows thoughtful engineering with proper separation of concerns. The CLI violation is significant but fixable with the partial migration approach.