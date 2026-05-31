-- =============================================================================
-- create_run_control.sql: Durable, session-independent run/checkpoint table.
--
-- WHY: Snowflake sessions are NOT resumable across a connection drop (session
-- state, USE context, temp tables, open transactions are lost; SESSION_ID is a
-- monitoring/control handle, not a reattach handle). To survive repeated
-- connection errors / overlapping Cortex windows, resume the WORK, not the
-- session: a caller-supplied stable run_id checkpoints progress HERE, and any
-- fresh session reads the last checkpoint for that run_id and continues. This is
-- the same idempotent-checkpoint pattern as MET_ENRICHMENT_CONTROL.
--
-- session_id + query_tag are recorded for provenance so a dual-instance write
-- (two windows touching the same run_id/step) is detectable after the fact.
--
-- Home: BRONZE (consistent with the other control/observability tables here --
-- MET_ENRICHMENT_CONTROL, EXTRACTION_LOG). Move to a dedicated OPS schema later
-- if control metadata should be separated from raw data.
--
-- Grants: NO new grant needed. create_grants.sql already grants LOADER
-- SELECT/INSERT/UPDATE/DELETE and TRANSFORMER SELECT on ALL + FUTURE TABLES in
-- BRONZE, and refresh_grants.sql re-grants on ALL; this FUTURE-table grant covers
-- RUN_CONTROL automatically.
--
-- Idempotency: state-bearing table -> CREATE TABLE IF NOT EXISTS (per the
-- class-based idempotency split in docs/context/ddl-infrastructure.md).
-- Paired rollback: infrastructure/drop_run_control.sql
-- =============================================================================

USE ROLE ARTWORK_ADMIN;
USE DATABASE ARTWORK_DB;
USE SCHEMA BRONZE;

CREATE TABLE IF NOT EXISTS RUN_CONTROL (
    run_id        VARCHAR        NOT NULL COMMENT 'Caller-supplied STABLE run/thread id; survives reconnects (the durable thread)',
    step          VARCHAR        NOT NULL COMMENT 'Logical step/phase name within the run',
    status        VARCHAR        NOT NULL DEFAULT 'in_progress' COMMENT 'in_progress | done | error',
    checkpoint    VARIANT        COMMENT 'Arbitrary JSON checkpoint payload to resume this step from',
    note          VARCHAR        COMMENT 'Human-readable note / conclusion for this step',
    session_id    VARCHAR        COMMENT 'CURRENT_SESSION() that last wrote this row (provenance / dual-instance detection)',
    query_tag     VARCHAR        COMMENT 'QUERY_TAG correlation id at write time, if set',
    created_at    TIMESTAMP_NTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'When this (run_id, step) row was first inserted (UTC)',
    updated_at    TIMESTAMP_NTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'When this row was last written (UTC); writer sets this explicitly on UPDATE',
    CONSTRAINT pk_run_control PRIMARY KEY (run_id, step)
)
COMMENT = 'Durable run/checkpoint control table. One row per (run_id, step). Resume work across connection drops by reading the last checkpoint for a run_id.';
