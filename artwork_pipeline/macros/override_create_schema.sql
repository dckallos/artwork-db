-- =============================================================================
-- override_create_schema.sql -- Suppress dbt's automatic schema creation
-- =============================================================================
-- WHY: dbt runs CREATE SCHEMA IF NOT EXISTS before every model execution.
-- This requires CREATE SCHEMA privilege on the database, which violates our
-- least-privilege design (ARTWORK_TRANSFORMER only gets USAGE + CREATE TABLE/VIEW
-- on pre-existing schemas). Schemas are managed by IaC (make infra), not dbt.
--
-- ENFORCEMENT NOTE: This macro is developer UX, not a security control.
-- Even without this macro, Snowflake would deny the CREATE SCHEMA because
-- the ARTWORK_TRANSFORMER role lacks the privilege. This macro simply:
--   1. Eliminates a wasted round-trip to Snowflake.
--   2. Produces a clearer error context for the engineer.
--
-- EFFECT: dbt skips schema creation entirely. If a model targets a schema that
-- does not exist, it will fail at CREATE TABLE/VIEW time with a clear error.
-- =============================================================================

{% macro create_schema(relation) %}
  {# No-op: schema lifecycle managed by IaC, not dbt. #}
{% endmacro %}

{% macro drop_schema(relation) %}
  {# No-op: schema lifecycle managed by IaC, not dbt. #}
{% endmacro %}
