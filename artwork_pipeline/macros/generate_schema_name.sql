-- =============================================================================
-- generate_schema_name.sql -- Env-aware custom schema routing (Artwork Pipeline)
-- =============================================================================
-- Implements the dbt `generate_schema_name_for_env` pattern: schema names are
-- routed by TARGET, not just concatenated. dbt only calls `generate_schema_name`
-- by default, so the env-aware logic lives here directly.
--
-- ROUTING (custom_schema_name comes from +schema in dbt_project.yml):
--   target.name == 'prod'      -> verbatim custom schema        SILVER / GOLD
--   otherwise (dev, staging, CI)-> <target.schema>_<CUSTOM>      (prefix branch)
--   custom_schema_name is none -> target.schema (models that declare no +schema)
--
-- The per-env prefix is DATA, not code: it comes from each target's `schema:`:
--   dev      schema: dbt_kalleward -> dbt_kalleward_SILVER / _GOLD
--   staging  schema: STAGING       -> STAGING_SILVER / STAGING_GOLD
--   prod     (verbatim branch)     -> SILVER / GOLD
-- Adding an env or renaming its schemas is a profiles.yml change, not a macro edit.
--
-- WHY per-target routing (not the default concat):
--   dbt's default would produce SILVER_GOLD from target.schema='SILVER' + +schema.
--   All three envs share ONE database (ARTWORK_DB, per plan 12.4.1), so prod and
--   staging must occupy DISTINCT schema names in the same DB -- prod verbatim,
--   staging carrying its target-schema prefix.
--
-- ALLOWLIST: approved custom schemas are hardcoded so a typo (+schema: GOLDD)
--   fails at compile time, not at runtime. Adding a schema is deliberate friction:
--     1. Create it + grants via IaC (infrastructure/, ACCOUNTADMIN) for EVERY env
--        variant (SILVER, GOLD, STAGING_SILVER, STAGING_GOLD, plus each dev prefix).
--     2. Add the base name to `allowed_schemas` below.
--     3. Reference it in dbt_project.yml with +schema: NEW_SCHEMA.
--
-- NOTE: schemas are NEVER created by dbt (see override_create_schema.sql -- the
--   transformer role lacks CREATE SCHEMA); they must pre-exist via IaC.
-- =============================================================================

{% macro generate_schema_name(custom_schema_name, node) -%}

    {% set allowed_schemas = ['SILVER', 'GOLD', 'DBT_TEST__AUDIT'] %}
    {% set default_schema = target.schema %}

    {%- if custom_schema_name is none -%}
        {# No +schema declared on the model; use the target default. #}
        {{ default_schema }}

    {%- elif custom_schema_name | upper in allowed_schemas -%}
        {# Approved schema: verbatim in prod, target-schema-prefixed elsewhere. #}

        {%- if target.name == 'prod' -%}
            {{ custom_schema_name | upper }}
        {%- else -%}
            {{ default_schema }}_{{ custom_schema_name | upper }}
        {%- endif -%}

    {%- else -%}
        {# Unapproved schema: fail early with an actionable message. #}
        {{ exceptions.raise_compiler_error(
            "Schema '" ~ custom_schema_name ~ "' is not in the approved list: "
            ~ allowed_schemas | join(', ') ~ ". "
            ~ "Create it (+ its per-env variants) via IaC first "
            ~ "(infrastructure/create_schemas.sql), then add the base name to "
            ~ "macros/generate_schema_name.sql allowed_schemas."
        ) }}
    {%- endif -%}

{%- endmacro %}
