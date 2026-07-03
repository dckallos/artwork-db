-- =============================================================================
-- generate_schema_name.sql -- Custom schema routing for the Artwork Pipeline
-- =============================================================================
--
-- CONSIDERATIONS (why this macro exists and the tradeoffs made):
--
-- 1. dbt's DEFAULT behavior:
--    dbt concatenates target.schema + custom_schema_name with an underscore.
--    With target.schema = 'SILVER' and +schema: 'GOLD' in dbt_project.yml,
--    the default produces: SILVER_GOLD (not what we want).
--    We want: GOLD (the custom_schema_name used verbatim) in production.
--
-- 2. Why VERBATIM and not PREFIX:
--    Our architecture has distinct schemas (BRONZE, SILVER, GOLD) at the same
--    level. They are not sub-schemas of a base. The target.schema in
--    profiles.yml (SILVER) is a default for models that don't declare +schema,
--    not a namespace prefix. Staging models omit +schema and land in SILVER;
--    mart models declare +schema: GOLD and land in GOLD.
--
-- 3. The ALLOWLIST decision:
--    We hardcode approved schemas rather than blindly passing through any value.
--    Tradeoff:
--      PRO: A typo like +schema: GOLDD fails at compile time with a clear
--           message, not at runtime with a Snowflake "object does not exist"
--           error (or worse, silently creating a new schema if CREATE SCHEMA
--           were ever granted).
--      CON: Adding a new schema requires editing this macro IN ADDITION TO
--           creating it in IaC. This is intentional friction -- it forces a
--           deliberate decision, not an accident.
--
-- 4. Per-developer prefix:
--    We have implemented the multi-developer pattern. Local runs (e.g., target 'dev')
--    will concatenate the developer's default schema (e.g., dbt_daniel) with
--    the custom schema (e.g., GOLD) to produce dbt_daniel_GOLD.
--    Production and snowflake-native targets bypass this and use the verbatim schema.
--
-- 5. Why this is in the dbt layer (not IaC):
--    This macro controls what SQL dbt GENERATES. It is logic about dbt's
--    behavior, authored by whoever maintains the dbt project. It does not
--    touch Snowflake directly. The DBA's enforcement is the RBAC grants
--    (or lack thereof) -- this macro is supplementary developer UX.
--
-- MAINTENANCE: If you add a new schema to the Medallion architecture:
--   1. Add it to infrastructure/create_schemas.sql (IaC -- DBA owns this)
--   2. Add grants in infrastructure/create_grants.sql (IaC -- DBA owns this)
--   3. Run `make infra` to apply
--   4. Add the schema name to allowed_schemas below (dbt -- engineer owns this)
--   5. Reference it in dbt_project.yml with +schema: NEW_SCHEMA
--
-- =============================================================================

{% macro generate_schema_name(custom_schema_name, node) -%}

    {% set allowed_schemas = ['SILVER', 'GOLD', 'DBT_TEST__AUDIT'] %}
    {% set default_schema = target.schema %}

    {%- if custom_schema_name is none -%}
        {# No +schema declared on the model; use the target default. #}
        {{ default_schema }}
        
    {%- elif custom_schema_name | upper in allowed_schemas -%}
        {# Approved schema: route based on execution context #}
        
        {%- if target.name in ['prod', 'snowflake'] -%}
            {# Production or Snowflake-native: use verbatim (no prefix concatenation). #}
            {{ custom_schema_name | upper }}
        {%- else -%}
            {# Local dev run: concatenate the developer's schema with the custom schema #}
            {{ default_schema }}_{{ custom_schema_name | upper }}
        {%- endif -%}

    {%- else -%}
        {# Unapproved schema: fail early #}
        {{ exceptions.raise_compiler_error(
            "Schema '" ~ custom_schema_name ~ "' is not in the approved list: "
            ~ allowed_schemas | join(', ') ~ ". "
            ~ "Create it via IaC first (infrastructure/create_schemas.sql), "
            ~ "then add to macros/generate_schema_name.sql allowed_schemas."
        ) }}
    {%- endif -%}

{%- endmacro %}