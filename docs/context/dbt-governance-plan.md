# dbt Governance Plan -- Proposal

> **Status: PROPOSAL** (not yet approved for implementation).
> Transition to approved solution: change Status to APPROVED, update "Proposed"
> language to "Required", and add implementation dates per layer.

> **Tier-1 doc.** Reference for how a Snowflake administrator should govern dbt
> deployments to prevent object proliferation, cost explosion, privilege leakage,
> and orphaned artifacts. Framed as a proposal for review; designed to transition
> into an implementation spec after approval.

---

## Problem Statement

### The core risk

dbt is a DDL engine. Every `dbt run` executes `CREATE OR REPLACE` statements
against Snowflake. A misconfigured dbt project -- or a well-meaning engineer with
broad grants -- can:

1. **Create unbounded schemas and objects.** dbt's default behavior runs
   `CREATE SCHEMA IF NOT EXISTS` before every model execution. A typo in
   `+schema:` config silently creates a new schema. Multiply by N developers
   and you get schema sprawl with no owner, no retention policy, and no audit
   trail.

2. **Consume unbounded compute.** A bad join (missing predicate, Cartesian
   product) inside a TABLE materialization runs until the warehouse suspends or
   credits are exhausted. dbt has no built-in query timeout.

3. **Leak privileges.** Without `copy_grants`, every `CREATE OR REPLACE`
   strips grants from the replaced object. Downstream consumers silently lose
   access after each dbt run. Conversely, granting `CREATE SCHEMA` lets dbt
   roles mint new schemas that inherit FUTURE GRANTS -- unintended access paths.

4. **Leave orphans.** When a model is removed from the dbt project (file
   deleted, ref dropped), the corresponding Snowflake object persists
   indefinitely. Over time, schemas accumulate dead tables/views that consume
   storage, confuse consumers, and create governance blind spots.

5. **Overwrite production.** Without environment isolation, a developer running
   `dbt run` against the wrong target writes directly to production schemas.
   There is no built-in confirmation prompt. The `CREATE OR REPLACE` DDL is
   destructive and immediate.

### Why this matters at scale

A single dbt engineer on a personal project (this repo today) can manage these
risks through discipline alone. Once there are 2+ engineers, or a CI/CD system
deploying automatically, discipline alone fails. The blast radius of a bad
`dbt run` includes: data loss (replaced tables), privilege loss (dropped grants),
cost spikes (runaway queries), and consumer outages (broken views referencing
orphaned objects).

### What Snowflake provides vs. what dbt provides

| Concern | Snowflake-native control | dbt-native control |
|---------|--------------------------|-------------------|
| Who can create objects | RBAC grants (per-schema, per-object-type) | None (dbt assumes its role has the right grants) |
| Where objects land | Schema exists or doesn't; `CREATE SCHEMA IF NOT EXISTS` needs privilege | `generate_schema_name` macro (customizable) |
| Cost bounding | Resource Monitors, statement timeouts, warehouse auto-suspend | None (dbt submits SQL; Snowflake executes it) |
| Object lifecycle | No built-in TTL on tables/views | `on-run-end` hooks (custom); no native orphan detection |
| Privilege continuity | `COPY GRANTS` clause on DDL | `copy_grants` config (must be explicitly set) |
| Audit trail | `QUERY_HISTORY`, `ACCESS_HISTORY`, `TAG_REFERENCES` | `query_tag` (auto-set to model name); manifest.json |

**Gap:** Neither platform provides governance out of the box. Snowflake provides
the primitives; dbt provides the hooks. The administrator must wire them together.

---

## Considerations for Reviewers

Before approving this proposal, the following factors should be weighed:

### 1. Team size and trust model

- **Solo/small team (1-3 engineers):** Layers 1 + 2 + the Minimum Viable set
  (see below) may be sufficient. Over-engineering governance for a team that
  communicates directly adds friction without proportional safety.
- **Medium team (4-10):** All 5 layers become relevant. Environment isolation
  (per-developer schemas) and CI-gated prod deployment are critical.
- **Large team (10+):** Consider dbt Cloud's built-in governance features (IDE
  environment locking, job-level permissions, CI checks) as an alternative to
  hand-wiring all of this. Cost-benefit shifts.

### 2. Environment: dbt Core vs. dbt Cloud vs. Snowflake-native dbt

- **dbt Core (this project):** All governance must be hand-built (macros, RBAC,
  resource monitors). Full control, full responsibility.
- **dbt Cloud:** Provides environment management, CI integration, and
  per-job permissions natively. Some layers below become redundant (e.g.,
  per-developer schema routing is built-in).
- **Snowflake-native `CREATE DBT PROJECT`:** Snowflake manages execution. Role
  governance is identical, but orchestration shifts to Snowflake Tasks. Resource
  monitors still apply. Macro-level controls (custom `generate_schema_name`) may
  not be available in the native path -- verify before adopting.

### 3. Incremental adoption vs. big-bang

This proposal is layered intentionally. Each layer is independently valuable and
can be adopted without the others. Recommended adoption order:

1. Layer 1 (RBAC) -- non-negotiable baseline.
2. Layer 2 (Cost) -- protects trial/POC accounts immediately.
3. Layer 3 (Object proliferation) -- becomes critical at first multi-developer milestone.
4. Layer 4 (Multi-developer) -- needed before second engineer writes models.
5. Layer 5 (Observability) -- ongoing refinement, not a gate.

### 4. Maintenance burden

Every custom macro and hook is code that must be maintained. Reviewers should
evaluate: does the team have the dbt proficiency to debug a failing
`generate_schema_name` macro? If not, the simpler path (grant `CREATE SCHEMA`,
accept the proliferation risk, audit monthly) may be pragmatically correct.

### 5. Snowflake edition constraints

- **Object tagging (Layer 3):** Available on all editions for basic usage.
  Propagation and tag-based masking require Enterprise Edition.
- **Managed Access schemas (Layer 1):** Available on all editions.
- **Resource Monitors (Layer 2):** Available on all editions.
- **`STATEMENT_TIMEOUT_IN_SECONDS` (Layer 2):** Available on all editions
  (warehouse-level or session-level parameter).

---

## Proposed Framework: 5 Layers of Defense

### Layer 1: RBAC -- Least-Privilege Role Design

**Principle:** dbt roles should have the minimum grants needed to create objects
in pre-existing schemas. They should never be able to create schemas, databases,
or grant access to other roles.

**Proposed controls:**

| Control | Rationale | Snowflake DDL |
|---------|-----------|---------------|
| No `CREATE SCHEMA` on database | Prevents schema sprawl from dbt misconfig | Do NOT grant; suppress dbt's schema-creation with a no-op macro |
| `MANAGED ACCESS` on target schemas | Centralizes grant authority to schema owner (admin role); dbt role cannot leak privileges | `CREATE SCHEMA ... WITH MANAGED ACCESS` or `ALTER SCHEMA ... ENABLE MANAGED ACCESS` |
| Separate dev vs. prod roles | Dev engineer cannot accidentally overwrite production objects | `TRANSFORMER_DEV` (sandbox), `TRANSFORMER_PROD` (CI-only) |
| `FUTURE GRANTS` for downstream read | New dbt objects auto-inherit SELECT grants for analyst roles | `GRANT SELECT ON FUTURE TABLES IN SCHEMA ... TO ROLE ...` |
| No inheritance from SYSADMIN/ACCOUNTADMIN | Transformer roles are leaf nodes in the hierarchy | Role hierarchy: `ARTWORK_ADMIN` > `TRANSFORMER_PROD` (no upward path to SYSADMIN) |

**dbt macro -- no-op schema creation:**

```sql
-- macros/override_create_schema.sql
{% macro create_schema(relation) %}
  {# Schema lifecycle is managed by IaC (make infra), not dbt.
     This no-op prevents dbt from requiring CREATE SCHEMA privilege. #}
{% endmacro %}
```

**Why this works:** dbt calls `create_schema()` before model execution. The no-op
skips the `CREATE SCHEMA IF NOT EXISTS` DDL entirely. The schema must already
exist (created by your IaC layer). If a model targets a non-existent schema, it
fails at `CREATE TABLE/VIEW` time with a clear error, not silently creates one.

**Damage scenario without this layer:** An engineer adds `+schema: SILVER_V2` in
`dbt_project.yml`. dbt creates `ARTWORK_DB.SILVER_V2` without any admin review.
FUTURE GRANTS on the database auto-fire, giving analyst roles SELECT on
everything in the new schema. The engineer's experimental models are now visible
to all downstream consumers. Nobody notices for weeks.

---

### Layer 2: Warehouse & Compute Cost Controls

**Principle:** dbt should never be able to consume unbounded compute. Every dbt
execution should have a hard ceiling on credits, query duration, and queue time.

**Proposed controls:**

| Control | Rationale | Snowflake DDL |
|---------|-----------|---------------|
| Dedicated warehouse(s) | Isolates dbt compute from ad-hoc queries; enables per-warehouse monitoring | `CREATE WAREHOUSE DBT_DEV_WH ...` / `CREATE WAREHOUSE DBT_PROD_WH ...` |
| Resource Monitor with suspend | Hard credit ceiling per period | `CREATE RESOURCE MONITOR ... CREDIT_QUOTA = N TRIGGERS ON ... PERCENT DO SUSPEND` |
| `STATEMENT_TIMEOUT_IN_SECONDS` | Kills runaway queries (bad joins, full-table scans) | `ALTER WAREHOUSE ... SET STATEMENT_TIMEOUT_IN_SECONDS = 900` |
| `STATEMENT_QUEUED_TIMEOUT_IN_SECONDS` | Prevents query pile-up when warehouse is suspended | `ALTER WAREHOUSE ... SET STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 120` |
| Auto-suspend + X-Small default | Minimizes idle cost; forces engineers to right-size | `AUTO_SUSPEND = 60, WAREHOUSE_SIZE = 'XSMALL'` |

**Proposed warehouse parameters (dev):**

```sql
CREATE WAREHOUSE IF NOT EXISTS DBT_DEV_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  STATEMENT_TIMEOUT_IN_SECONDS = 900          -- 15 min max per query
  STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 120;  -- 2 min max queue

CREATE RESOURCE MONITOR DBT_DEV_MONITOR
  WITH CREDIT_QUOTA = 10                      -- adjust per budget
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 50 PERCENT DO NOTIFY
    ON 90 PERCENT DO SUSPEND
    ON 100 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE DBT_DEV_WH SET RESOURCE_MONITOR = DBT_DEV_MONITOR;
```

**Damage scenario without this layer:** An engineer writes a staging model with
a missing join predicate. The resulting Cartesian product attempts to materialize
a table with billions of rows. The warehouse scales to 4XL (if multi-cluster)
and runs for hours before anyone notices. On a trial account with 400 free
credits, this single run could exhaust the entire budget.

---

### Layer 3: Object Proliferation Controls

**Principle:** Every Snowflake object created by dbt should be intentional,
traceable, and removable. The administrator should be able to answer: "what did
dbt create, when, and is it still needed?"

**Proposed controls:**

| Control | Rationale | Implementation |
|---------|-----------|----------------|
| Guarded `generate_schema_name` macro | Restricts which schemas dbt can target; raises compilation error for unapproved schemas | dbt macro with allowlist |
| Object tagging (auto via post-hook) | Every dbt object gets a `dbt_project` + `dbt_model` tag for audit | `post-hook` in `dbt_project.yml` |
| Orphan detection | Identifies objects in target schemas that are NOT in the dbt manifest | `on-run-end` hook or scheduled TASK |
| No dynamic schema naming in prod | Prod target uses fixed schema names; no `{{ env_var('USER') }}` interpolation | Profile-level enforcement |

**dbt macro -- guarded schema name:**

```sql
-- macros/generate_schema_name.sql
{% macro generate_schema_name(custom_schema_name, node) %}
    {# Allowlist of schemas dbt is permitted to write to.
       Add new schemas here ONLY after IaC creates them. #}
    {% set allowed_schemas = ['SILVER', 'GOLD'] %}

    {% if custom_schema_name is none %}
        {{ target.schema }}
    {% elif custom_schema_name | upper in allowed_schemas %}
        {{ custom_schema_name | upper }}
    {% else %}
        {{ exceptions.raise_compiler_error(
            "Schema '" ~ custom_schema_name ~ "' is not in the approved list: "
            ~ allowed_schemas | join(', ') ~ ". "
            ~ "Add it to IaC first, then update macros/generate_schema_name.sql."
        ) }}
    {% endif %}
{% endmacro %}
```

**dbt post-hook for object tagging:**

```yaml
# In dbt_project.yml (proposed)
models:
  artwork_pipeline:
    +post-hook:
      - "ALTER {{ model.config.materialized | upper }} {{ this }} SET TAG ARTWORK_DB.GOVERNANCE.DBT_PROJECT = '{{ project_name }}', ARTWORK_DB.GOVERNANCE.DBT_MODEL = '{{ model.name }}'"
```

**Considerations for tagging:**
- Requires a `GOVERNANCE` schema with tag objects pre-created by IaC.
- The transformer role needs `APPLY` privilege on the tags.
- Tag values are limited to 256 characters.
- `ALTER ... SET TAG` on views re-triggers `COPY GRANTS` -- test behavior.

**Orphan detection query (proposed):**

```sql
-- Run periodically (TASK or on-run-end hook).
-- Returns objects in SILVER/GOLD not present in the latest dbt manifest.
SELECT TABLE_NAME, TABLE_SCHEMA, TABLE_TYPE, CREATED, LAST_ALTERED
FROM ARTWORK_DB.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA IN ('SILVER', 'GOLD')
  AND TABLE_NAME NOT IN (<list from manifest.json nodes>);
```

**Damage scenario without this layer:** Over 6 months of development, engineers
create 40 staging models. 12 are later deleted from the dbt project (refactored
or abandoned). The 12 Snowflake views persist in SILVER, consuming no storage
(they're views) but confusing consumers who query them expecting valid data.
One orphaned view references a since-dropped Bronze table -- queries against it
return cryptic "Object does not exist" errors. Nobody knows which views are
still part of the active pipeline.

---

### Layer 4: Multi-Developer Environment Isolation

**Principle:** Developers should be able to iterate freely without risk of
overwriting each other's work or production data.

**Proposed controls:**

| Control | Rationale | Implementation |
|---------|-----------|----------------|
| Per-developer dev schemas | `SILVER_<USER>` / `GOLD_<USER>` | `generate_schema_name` macro branches on `target.name` |
| CI-only prod keys | No human holds the `TRANSFORMER_PROD` private key | Key stored in CI secret vault only |
| `dbt build` enforcement | Tests run atomically with models; failures block deployment | Orchestration script validates phase = `build`, not `run` |
| Pre-commit compilation check | Catches syntax errors before Snowflake is touched | `dbt compile --no-partial-parse` in pre-commit hook |
| Model ownership metadata | Accountability for who owns each model | `meta: {owner: "daniel"}` in YAML |

**Per-developer schema routing (proposed macro extension):**

```sql
{% macro generate_schema_name(custom_schema_name, node) %}
    {% set allowed_schemas = ['SILVER', 'GOLD'] %}

    {% if target.name == 'dev' %}
        {# Dev: prefix with developer identifier for isolation #}
        {% set dev_prefix = env_var('DBT_DEV_SCHEMA_PREFIX', 'DEV') %}
        {% if custom_schema_name is none %}
            {{ dev_prefix }}_{{ target.schema }}
        {% else %}
            {{ dev_prefix }}_{{ custom_schema_name | upper }}
        {% endif %}
    {% elif target.name == 'prod' %}
        {# Prod: strict allowlist, no prefix #}
        {% if custom_schema_name is none %}
            {{ target.schema }}
        {% elif custom_schema_name | upper in allowed_schemas %}
            {{ custom_schema_name | upper }}
        {% else %}
            {{ exceptions.raise_compiler_error(
                "Schema '" ~ custom_schema_name ~ "' not approved for prod."
            ) }}
        {% endif %}
    {% else %}
        {{ target.schema }}
    {% endif %}
{% endmacro %}
```

**Consideration:** Per-developer schemas require `CREATE SCHEMA` privilege OR
pre-creation via IaC. For dev environments, the pragmatic path is often to
grant `CREATE SCHEMA` on a separate DEV database (not the production database).
This contains the blast radius: developers can sprawl in DEV_DB freely, but
cannot touch ARTWORK_DB.

**Damage scenario without this layer:** Two engineers both run `dbt run` against
the same `SILVER` schema simultaneously. Engineer A's `CREATE OR REPLACE VIEW`
executes between Engineer B's compile step and execute step. Engineer B's run
succeeds but has overwritten A's just-deployed view. Neither knows. The last
writer wins, silently.

---

### Layer 5: Observability & Alerting

**Principle:** The administrator should have continuous visibility into what dbt
is doing, what it costs, and when it deviates from expected behavior.

**Proposed controls:**

| Control | Rationale | Implementation |
|---------|-----------|----------------|
| `QUERY_TAG` filtering | dbt auto-sets `query_tag` to model name; query `QUERY_HISTORY` filtered by tag | Built-in (no config needed) |
| Cost attribution via object tags | Join `TAG_REFERENCES` to `WAREHOUSE_METERING_HISTORY` for per-model cost | Object tagging (Layer 3) + scheduled report |
| Resource Monitor email alerts | Platform admin gets notified before credit exhaustion | `NOTIFY` trigger on resource monitor |
| `dbt source freshness` | Alerts when Bronze data is stale; prevents dbt from processing outdated inputs | `freshness:` block in `_sources.yml` |
| Run result persistence | Store `run_results.json` in a Snowflake table for historical trending | Post-run upload script or `on-run-end` macro |

**Proposed cost-attribution query:**

```sql
-- Per-model credit consumption (last 30 days)
SELECT
    SPLIT_PART(QUERY_TAG, '.', -1) AS DBT_MODEL_NAME,
    COUNT(*) AS QUERY_COUNT,
    SUM(TOTAL_ELAPSED_TIME) / 1000 AS TOTAL_SECONDS,
    SUM(CREDITS_USED_CLOUD_SERVICES) AS CLOUD_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE QUERY_TAG LIKE 'dbt%'
  AND START_TIME > DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY TOTAL_SECONDS DESC;
```

**Damage scenario without this layer:** A model that previously ran in 5 seconds
starts running in 5 minutes after a source table grows 100x. Nobody notices
until the monthly Snowflake bill arrives. By then, the model has run 30 times at
the inflated cost. With alerting, the first anomalous run triggers a
notification and the engineer can optimize before the next scheduled execution.

---

## Minimum Viable Governance (Proposed First Implementation)

For a solo developer or small team on a trial/POC account, the full 5-layer
framework is over-engineering. The following 3 controls provide the highest
risk-reduction per unit of effort:

### MVG-1: No-op `create_schema` macro

- **Effort:** 1 file, 3 lines of code.
- **Risk eliminated:** Schema sprawl from dbt misconfig.
- **Immediate need:** Fixes the `CREATE SCHEMA` privilege error without granting
  broader permissions.
- **Status: IMPLEMENTED** (2026-06-05). File: `artwork_pipeline/macros/override_create_schema.sql`.

### MVG-2: Custom `generate_schema_name` macro (simple version)

- **Effort:** 1 file, ~15 lines.
- **Risk eliminated:** dbt's default schema-prefixing behavior (which would write
  to `SILVER_GOLD` instead of `GOLD`).
- **Immediate need:** Required for Unit 4 (first Gold mart).
- **Status: IMPLEMENTED** (2026-06-05). File: `artwork_pipeline/macros/generate_schema_name.sql`.
  Allowlist: `['SILVER', 'GOLD', 'DBT_TEST__AUDIT']`.

### MVG-3: Resource Monitor on the dbt warehouse

- **Effort:** 2 SQL statements (IaC).
- **Risk eliminated:** Unbounded credit consumption from bad queries.
- **Immediate need:** Protects trial account credits.
- **Status: AUTHORED** (2026-06-05). File: `infrastructure/create_resource_monitors.sql`.
  Awaiting `make infra CONN=mk07348` on Mac to apply. 20 credits/month, suspend
  at 95%, STATEMENT_TIMEOUT=900s, QUEUED_TIMEOUT=120s.

**These 3 controls can be implemented independently and incrementally.** Each
subsequent layer adds defense-in-depth when the team or risk profile grows.

---

## Appendix: Key Snowflake Documentation References

- Resource Monitors: `CREATE RESOURCE MONITOR` DDL reference
- Managed Access Schemas: `CREATE SCHEMA ... WITH MANAGED ACCESS`
- Statement Timeout: `STATEMENT_TIMEOUT_IN_SECONDS` parameter
- Object Tagging: Introduction to object tagging (user guide)
- FUTURE GRANTS: `GRANT ... ON FUTURE` syntax
- Access Control Best Practices: Security > Access Control Considerations
- Dynamic Table Privileges: (relevant if migrating from dbt tables to dynamic tables)
- FUTURE GRANTS Precedence: Schema-level overrides database-level for same object type

---

## Approval Transition Checklist

When this proposal is approved, update as follows:

- [ ] Change document status from PROPOSAL to APPROVED at the top.
- [ ] Replace "Proposed controls" with "Required controls" in each layer.
- [ ] Add implementation dates and responsible party per control.
- [ ] Create corresponding IaC files for Snowflake-side controls (resource
      monitor, tags, managed access ALTER statements).
- [ ] Create dbt macro files for code-side controls.
- [ ] Add to `scripts/manifest.txt` if new DDL files are introduced.
- [ ] Update `AGENTS.md` Status table entry from "Proposal" to "Active" or
      "Applied" with date.
