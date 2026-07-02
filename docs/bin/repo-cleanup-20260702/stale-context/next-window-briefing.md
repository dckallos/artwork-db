# Next-Window Briefing — dbt / Medallion / IaC Acceleration

> **PASTE-INTO-A-NEW-CORTEX-WINDOW HAND-OFF.** Authored 2026-06-06 at the owner's
> request: *"the mentorship is going too slowly."* This window's job is to shift
> from slow one-model-per-unit tutoring to **foundational, batched build steps**
> that move the artwork medallion architecture forward — while still explaining
> the WHY. Web search is ENABLED; use it to validate current (2026) best practices
> and GA status before proposing/building.

---

## 0. FIRST RESPONSE protocol (do this, in order, before any build)

1. **Solo + fork check.** `COUNT(DISTINCT SESSION_ID)` over
   `SNOWFLAKE.INFORMATION_SCHEMA.QUERY_HISTORY` (last 10 min, `QUERY_TAG ILIKE
   '%cortex_code_snowsight%'`) AND check `ARTWORK_DB.BRONZE.CORTEX_FORK_INCIDENTS`.
   Exactly 1 session = solo; >1 = stop and ask. NOTE: file edits do NOT show in
   query history — a concurrent fork has repeatedly raced this repo, so also watch
   `ls --full-time` mtimes on files you didn't touch. If a task is already done by
   a fork, review its logic pessimistically and keep it only if sound.
2. **Quote** the latest `End of this window` header from
   `docs/context/session-3-progress-log.md` back to the owner (the ritual).
3. **Review** (don't re-teach): skim `dbt-plan.md` (D1–D7, DAG, M1–M3),
   `dbt-curriculum.md` (status table), the active journal, the 2 existing models,
   and `dbt-governance-plan.md`. Confirm live state with the read-only SQL in §3.
4. **Propose + ASK.** Present the foundational step-menu (§4), then use the
   AskUserQuestion tool to let the owner choose direction(s). Use **web search** to
   confirm specifics (dbt-snowflake version, incremental strategies, `CREATE DBT
   PROJECT` GA features, model contracts, Cortex Analyst/semantic-view fit).
5. **Dual-FS + gating.** State the plan, WAIT for explicit go + date before writing.
   Workspace edits are NOT on the Mac until the owner syncs. The owner runs all
   `dbt`/`make`/`snow` commands on the Mac (Mac #2 is the guinea pig). Report
   applied-to-account yes/no and pushed-to-Mac yes/no every turn.

---

## 1. The directive: GO FASTER (what "accelerate" means here)

The unit-by-unit curriculum (1 staging model per "unit", 6 units) is too slow for a
learner who has already shipped Bronze ingestion, key-pair IaC, governance macros,
and 2 staging models. **Collapse the remaining curriculum into a few high-leverage
batches**, and run the cross-cutting foundations in parallel rather than as serial
"units." Keep the teaching (name decision forks, explain the WHY, introduce one
deliberate failure per batch) — but stop pacing at one object per session.

Concretely: Units 3–6 of the old curriculum should become **~2 build batches + 1
foundations pass**, not 4 separate windows.

---

## 2. Greater goals of the artwork medallion project (the north star)

- **A queryable, source-neutral Gold star** over Met OpenAccess: `dim_artworks`,
  `dim_artists`, `fct_artwork_images`, plus an `openaccess_catalog` wide OBT
  (public-domain + has-image) for BI/app/AI consumption. (`dbt-plan.md` D3.)
- **Multi-source future** (CMA, AIC, Smithsonian) attached to the SAME star via a
  `source_system` column and artist entity-resolution — but only AFTER the Met
  spine is proven (D1 depth-before-breadth).
- **Production maturity:** incremental + hard-delete propagation (the DATA-01 gap),
  source freshness, completeness tests, then a path to **Snowflake-native dbt**
  (`CREATE DBT PROJECT` + Task scheduling, D2/M5) and/or Airflow.
- **An AI/consumption layer** on the public-domain catalog (semantic view → Cortex
  Analyst / Search / Snowflake Intelligence) — see `cortex-ai-agents-playbook.md`
  and `track-d-resumable-agents.md`. This is where the medallion pays off.
- **Governance/observability** kept first-class (masking/contacts/DMFs, lineage),
  consistent with the Horizon-era tooling already in the repo.

---

## 3. Current state (verify live before building — read-only)

```sql
-- Bronze inputs
SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.RAW_MET_OBJECTS;        -- ~503
SELECT COUNT(*) FROM ARTWORK_DB.BRONZE.MET_ENRICHMENT_CONTROL; -- ~2327
-- Silver (what dbt has built)
SHOW VIEWS IN SCHEMA ARTWORK_DB.SILVER;   -- expect STG_MET__ARTWORKS (+ ENRICHMENT_STATUS if Unit 3 ran)
-- Gold (expected EMPTY today)
SHOW TABLES IN SCHEMA ARTWORK_DB.GOLD;
```

- dbt project: `artwork_pipeline/` — profile `artwork_pipeline`, dual-mode
  `profiles.yml` (`dev` local key-pair via env_var; `snowflake` session-based).
  `+copy_grants: true` global; staging→SILVER (view), marts→GOLD (table).
  Governance macros: `generate_schema_name` (verbatim, no prefix) +
  `override_create_schema`. Packages: `dbt_utils`, `codegen`.
- Connections: post-migration, `~/.snowflake/connections.toml` is the sole store;
  transformer connection = `mk07348_transformer` (role `ARTWORK_TRANSFORMER`).
- Models present: `stg_met__artworks`, `stg_met__enrichment_status`. NOT yet built:
  `stg_met__artists`, `stg_met__images`, and ALL of Gold.

---

## 4. Proposed foundational step-menu (present these; let the owner choose)

> These are starting proposals, NOT a locked plan. Research current best practice
> with web search, then refine WITH the owner. Pick a primary track; the rest can
> follow.

### Track A — Finish the Met Silver→Gold spine (collapses old Units 3–6)
- **A1 (one batch):** remaining Silver staging — `stg_met__artists` (dedup, compound
  names, pick PRIMARY artist) + `stg_met__images` (LATERAL FLATTEN primary +
  additional_images). Tests in the same pass.
- **A2 (one batch):** the Gold star — `dim_artists`, `dim_artworks` (surrogate keys
  via `dbt_utils.generate_surrogate_key`, `source_system='met'`),
  `fct_artwork_images`, + relationship/uniqueness tests across schemas.
- **A3:** `openaccess_catalog` OBT (public-domain + has-image, pre-joined) AND convert
  `stg_met__artworks` to **incremental with hard-delete** (DATA-01) — the hardest,
  highest-learning piece. Research: `incremental_strategy` (merge vs delete+insert),
  hard-delete via `MET_CSV_SNAPSHOT` diff.

### Track B — Compounding foundations (run alongside A)
- **B1:** Wire dbt into IaC for real — `make dbt-build` peer target via
  `scripts/dbt_orchestrate.sh`; `.env` as single source (D5); `make check-env`.
- **B2:** dbt **model contracts** + `not_null`/`unique`/`relationships` + a custom
  `row_count_delta` completeness test + source **freshness** on `_extracted_at`.
- **B3:** `dbt docs generate` lineage/catalog — cheap, high-value before source #2.
- **B4:** CI smoke (`dbt build` on PR) — research GitHub Actions vs Snowflake-native.

### Track C — Architecture maturity (a direction decision, research-heavy)
- **C1:** Snowflake-native dbt (`CREATE DBT PROJECT` + Task schedule, D2/M5) vs stay
  local dbt Core + future Airflow. Research GA status/limits in 2026.
- **C2:** Multi-source onboarding readiness (CMA first) — entity resolution into
  `dim_artists`.
- **C3:** AI/consumption layer — semantic view over `openaccess_catalog` → Cortex
  Analyst / Search / Snowflake Intelligence. (Invoke `semantic_studio` skill.)

**Recommended default if the owner is unsure:** A1+A2 in two batches (gets a real
Gold star fast), with B1 wired in the same arc so dbt becomes a true IaC peer.

---

## 5. Standing rules (carry forward, non-negotiable)

- **Dual-FS:** never run `make`/`dbt`/`python`/`snow` from the workspace; author
  files, the owner runs on the Mac. Report applied/pushed status each turn.
- **Gating:** state plan → wait for explicit go + date → then write.
- **Fork awareness:** a concurrent instance has repeatedly edited this repo. Use
  mtimes, keep the relevant checklist/ledger as the shared source of truth, and
  pessimistically review any work you didn't author.
- **Mentor voice:** explain the WHY, name decision forks, one deliberate failure per
  batch — but at batch cadence, not one-object-per-window.
- **Bronze is sacred** (dbt never writes it). Silver/Gold fully re-derivable.
- **Update** `dbt-curriculum.md` status + the active journal as batches land; add an
  `End of this window` entry to `session-3-progress-log.md` at the close.
