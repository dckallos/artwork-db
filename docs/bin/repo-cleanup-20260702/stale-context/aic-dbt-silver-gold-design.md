# AIC dbt Silver & Gold Pipeline — Detailed Design Decisions

> **Status: LEGACY** — Superseded by `docs/context/aic-silver-gold-implementation.md`
> (approved 2026-06-07). Retained for historical context only. Do NOT use this
> document for implementation decisions -- all topics here have been resolved in
> the implementation spec.
>
> Original status: DRAFT — was input for a review session.

---

## TOPIC 1: Image Data — Only 2 of 10 Records Have `image_id`

**Observation:** In the 10-record smoke test, only artworks `100` and `10000` have a non-null `image_id`. The other 8 have `None`. Additionally, `alt_image_ids` is an array field present in every record but empty (`[]`) in this sample.

**Automated data review actions needed:**

1. **Full-load image coverage audit** — After running the full snapshot (131k artworks), compute:
   - What percentage of artworks have a non-null `image_id`?
   - What percentage of artworks have a non-empty `alt_image_ids` array?
   - What's the distribution of `ARRAY_SIZE(alt_image_ids)`?
   - Cross-tabulate: how many artworks have `is_public_domain = true` AND `image_id IS NOT NULL`? (This is the actual serveable set.)

2. **Data quality tests in dbt** — Options for encoding these expectations:
   - `dbt_expectations.expect_column_proportion_of_unique_values_to_be_between` on `image_id` (non-null proportion)
   - A custom singular test that asserts `image_id IS NOT NULL` coverage exceeds a threshold (e.g., >60% of public-domain artworks)
   - A test that validates every non-null `image_id` is a valid UUID format (regex)
   - A test that validates `alt_image_ids` array members are valid UUIDs when present

3. **Fact-check against AIC's published stats:**
   - AIC claims ~130k artworks in the collection
   - Their website shows images for the majority of public-domain works
   - If our full load shows <50% image coverage, something is wrong in extraction (JSON parsing, field name mismatch)
   - If it shows >80%, the data is healthy — most coins/fragments genuinely lack images

**Status: NEEDS IMPLEMENTATION** — The full snapshot hasn't been run yet. The data audit queries should be written as both ad-hoc SQL (immediate) and dbt tests (persistent).

---

## TOPIC 2: `stg_aic__images` — Not a Simple Single-Image Model

**Corrected understanding:** AIC artworks have TWO image-related fields:

- `image_id` (STRING, nullable) — the primary image UUID
- `alt_image_ids` (ARRAY of strings) — additional/alternate view UUIDs

The `thumbnail` object also contains `height`, `width`, `alt_text`, and a base64 `lqip` (Low Quality Image Placeholder). These are useful metadata about the primary image.

**Options for `stg_aic__images` grain and structure:**

**Option A: One row per image per artwork (long format, matching Met's pattern)**
```
artwork_id | image_id_value | image_type        | ordinal_position | image_url | image_url_small
100        | 03c0fd...      | primary           | 1                | iiif/...  | iiif/.../200,/...
12345      | ab12cd...      | alt               | 2                | iiif/...  | iiif/.../200,/...
12345      | ef34gh...      | alt               | 3                | iiif/...  | iiif/.../200,/...
```

**Option B: One row per artwork, with primary + array preserved**
```
artwork_id | primary_image_url | alt_image_urls (ARRAY) | image_count
```

**Option C: Separate models — `stg_aic__primary_images` and `stg_aic__alt_images`**
One model for the scalar primary, another using LATERAL FLATTEN on `alt_image_ids`.

**Additional image-type considerations:**
- IIIF supports multiple "quality" modes (`default`, `color`, `gray`, `bitonal`), multiple sizes (`843,`, `200,`, `full`), and multiple formats (`jpg`, `png`, `webp`)
- Should the staging model produce one row per image_id, or one row per (image_id × size variant)?
- The Met staging model stores the raw URL from the API (Met provides the full URL). AIC requires URL construction — where should the construction happen? Options:
  - In the staging model SQL (computed column)
  - In a dbt macro (reusable across models)
  - In a Snowflake UDF (reusable outside dbt)
  - Only in Gold (staging stores just the `image_id`, Gold adds the URL)

**The `thumbnail` metadata question:**
- `thumbnail.height` and `thumbnail.width` are the pixel dimensions of the image
- `thumbnail.alt_text` is accessibility text
- These are image attributes, not separate images
- Should they live on `stg_aic__images` as columns, or on `stg_aic__artworks` (since there's exactly one thumbnail per artwork)?

**Status: PENDING DISCUSSION** — The grain, URL-construction location, and handling of IIIF variants all need explicit decisions before implementation.

---

## TOPIC 3: Gold `dim_artists` and `dim_artworks` — Beyond Simple UNION

**The problem with simple UNION ALL:**

A naive `UNION ALL stg_met__artists + stg_aic__artists` produces duplicate rows for the same real-world artist appearing in both collections. Edgar Degas has artworks in both the Met and AIC. A simple UNION gives you two "Edgar Degas" rows — one from each source — with no relationship between them.

**Options for combining artists across sources:**

**Option A: Source-partitioned (simplest)**
- Each source gets its own rows in `dim_artists`
- `source_system` is part of the surrogate key
- Same artist = 2 rows
- Entity resolution deferred entirely
- Pro: No false merges, no complexity
- Con: Downstream consumers see duplicates; cross-museum queries double-count

**Option B: Authority-linked deduplication (ULAN-based)**
- Both Met and AIC publish ULAN IDs for some agents
  - Met: `artist_ulan_url` (e.g., `http://vocab.getty.edu/page/ulan/500115588`)
  - AIC: `ulan_id` (numeric, e.g., `500115588`)
- Where ULAN IDs match, merge into one canonical row
- Where ULAN IDs are missing (very common — AIC's sample shows 0/10 agents have ULAN IDs), fall back to source-partitioned
- Pro: Correct for known matches; no false merges
- Con: ULAN coverage may be sparse (need to audit); requires merge-priority logic (which source's name/bio wins?)

**Option C: Fuzzy matching with Snowflake string functions**
- For artists without ULAN IDs, attempt matching on:
  - `JAROWINKLER_SIMILARITY(met_sort_name, aic_sort_title)` > threshold
  - `EDITDISTANCE(met_name, aic_name)` < threshold
  - Birth/death year exact match as a confirming signal
- Pro: Catches more matches than ULAN-only
- Con: False positives (common names like "John Smith"); requires manual review of edge cases; complex SQL; threshold tuning is subjective

**Option D: dbt intermediate model + manual review table**
- An intermediate model produces "candidate matches" (ULAN + fuzzy)
- A manually-curated seed CSV (`seeds/artist_crosswalk.csv`) stores confirmed matches
- Gold reads from the seed for confirmed merges, keeps everything else source-partitioned
- Pro: Human-in-the-loop prevents false merges; seed is version-controlled
- Con: Requires ongoing maintenance; doesn't scale to thousands of matches

**Option E: LLM-assisted entity resolution (Cortex AI)**
- Use `SNOWFLAKE.CORTEX.COMPLETE()` or `AI_CLASSIFY` to evaluate candidate pairs
- Prompt: "Are these the same person? Met: 'Degas, Edgar (French, 1834-1917)' vs AIC: 'Edgar Degas (French, 1834–1917)'"
- Pro: Handles variations humans handle (accents, date formats, alternate transliterations)
- Con: Cost per comparison; non-deterministic; needs guardrails

**Option F: Separate conformed dimension + bridge table**
- `dim_artists` contains ONE row per real-world artist (resolved)
- `bridge_artist_sources` maps (artist_id → source_system, source_artist_id) — many-to-one
- Pro: Clean star schema; no duplicates in the dimension
- Con: Requires resolution to be solved first; bridge adds join complexity

**The `dim_artworks` equivalent:**
- Artworks are unlikely to appear in multiple museums (unlike artists)
- The cross-source concern for artworks is conformity of columns, not deduplication
- The UNION for artworks is simpler: genuinely additive, not duplicative
- However: the FK from `dim_artworks.artist_id` to `dim_artists.artist_id` depends on which resolution approach is chosen

**Status: PENDING DISCUSSION** — This is an architectural decision with cascading implications for every Gold model. The choice between Options A-F (or a hybrid) determines the shape of the entire Gold layer.

---

## TOPIC 4: Artist FK Join — Accounting for Messy Data

**The FK join challenge:**

- **Met:** No direct artist FK. Uses pipe-delimited strings (`alpha_sort + ulan_url`) for matching, which is inherently lossy.
- **AIC:** Has a direct FK (`artwork.artist_id → agent.id`), which is clean for intra-source joins but irrelevant for cross-source resolution.

**Where "messy" manifests:**

1. **Missing ULAN IDs:** In the 10-record AIC agent sample, ZERO have `ulan_id`. If this holds at scale, there's no authority key to join on cross-source.

2. **Name normalization inconsistencies:**
   - Met: `"Degas, Edgar"` (alpha_sort format)
   - AIC: `"Degas, Edgar"` (sort_title format) — *might* match, but:
     - Met: `"Katsushika, Hokusai"` vs AIC: `"Hokusai, Katsushika"` — order varies
     - Accent handling: `"Dürer, Albrecht"` vs `"Durer, Albrecht"`
     - Date ranges in bio: `"(French, 1834-1917)"` vs `"French, 1834–1917"` (dash types differ)

3. **One-to-many artist assignments:**
   - Met packs multiple artists per artwork (pipe-delimited)
   - AIC has a single `artist_id` per artwork plus `artist_ids` (array of all contributors)
   - The "primary artist" concept isn't always the same between sources

**Options for handling this in staging (upstream preparation):**

- **Normalize in staging:** Create a `_normalized_name` column in both `stg_met__artists` and `stg_aic__artists` that strips accents, standardizes punctuation, uppercases, removes "(Nationality, dates)" suffixes
- **Expose match keys in staging:** Add explicit `_ulan_numeric_id` (parsed from URL for Met, direct field for AIC) and `_normalized_sort_name` columns that downstream Gold models can join on
- **Leave raw in staging, match in an intermediate model:** Staging stays source-faithful; a `int_artist_candidates` model does the matching work

**Snowflake functions available for fuzzy matching:**
- `JAROWINKLER_SIMILARITY(str1, str2)` — returns 0-100 score
- `EDITDISTANCE(str1, str2)` — Levenshtein distance
- `SOUNDEX(str)` — phonetic encoding
- `COLLATE(str, 'en-ci-ai')` — accent-insensitive, case-insensitive comparison
- `REGEXP_REPLACE` — for stripping parentheticals, normalizing punctuation

**dbt packages that assist:**
- `dbt_utils` — `generate_surrogate_key`, basic testing
- `dbt_expectations` — custom assertion tests
- No native dbt package does entity resolution out-of-the-box
- The `similarity-api` approach (external SaaS) or `zingg` (Spark-based) are external tools, not dbt-native

**Status: PENDING DISCUSSION** — The approach to preparing match keys in staging, the threshold for "good enough" matching, and whether to use pessimistic (only exact ULAN) or optimistic (fuzzy + manual review) strategies all require decisions.

---

## TOPIC 5: Entity Resolution — Concrete Detail

**What "entity resolution" means specifically in this context:**

Given two artist rows:
```
SOURCE: met_museum     | alpha_sort: "Degas, Edgar"   | ulan_url: http://vocab.getty.edu/page/ulan/500004327 | birth: 1834 | death: 1917
SOURCE: art_institute  | sort_title: "Degas, Edgar"   | ulan_id: NULL                                       | birth: 1834 | death: 1917
```

Are these the same entity? A human says yes. An algorithm needs rules.

**Resolution tiers (from most to least certain):**

| Tier | Signal | Confidence | Coverage |
|------|--------|-----------|----------|
| 1 | ULAN ID exact match | 100% | Low (AIC has sparse ULAN coverage) |
| 2 | Wikidata URL exact match | 100% | Unknown (AIC agents don't expose wikidata URLs) |
| 3 | Normalized name + birth_year + death_year all match | ~95% | Medium (depends on name normalization quality) |
| 4 | JAROWINKLER > 90 on normalized name + birth_year match | ~80% | Higher (catches spelling variations) |
| 5 | Name-only fuzzy match (no dates) | ~50% | Highest but many false positives |

**Implementation patterns:**

**Pattern A: Deterministic-only (Tier 1-2)**
```sql
-- int_artist_crosswalk.sql
SELECT
    met.artist_id AS met_artist_id,
    aic.artist_id AS aic_artist_id,
    'ulan_exact' AS match_method
FROM stg_met__artists met
INNER JOIN stg_aic__artists aic
    ON SPLIT_PART(met.artist_ulan_url, '/', -1) = aic.ulan_id::STRING
WHERE met.artist_ulan_url IS NOT NULL
  AND aic.ulan_id IS NOT NULL
```

**Pattern B: Tiered (deterministic + probabilistic)**
```sql
-- Tier 1: ULAN
... UNION ALL ...
-- Tier 2: Exact name + exact dates
... UNION ALL ...
-- Tier 3: Fuzzy name + exact dates
WHERE JAROWINKLER_SIMILARITY(
    UPPER(met.artist_alpha_sort),
    UPPER(aic.sort_title)
) >= 90
AND met.artist_begin_date = aic.birth_date
```

**Pattern C: Candidate generation + seed-based confirmation**
```sql
-- int_artist_match_candidates.sql (ephemeral or table)
-- Generates ALL possible matches above a low threshold
-- Human reviews, confirmed matches go into seeds/artist_crosswalk.csv
-- Gold reads the seed, ignores unconfirmed candidates
```

**Pattern D: Deferred — Gold uses source_system partitioning today**
```sql
-- dim_artists carries both rows; openaccess_catalog shows source_system
-- Consumers filter or group by source as needed
-- Resolution added later without breaking the schema (just changes which rows exist)
```

**Impact on downstream models:**
- If resolution merges artist rows, `dim_artworks.artist_id` must point to the merged ID
- `fct_artwork_images` joins through `dim_artworks` so it cascades
- `openaccess_catalog` would show one artist row for cross-source works

**Status: PENDING DISCUSSION** — The tier of resolution to implement, the tooling approach, and whether this is M1 scope or deferred all need decisions. The ULAN coverage audit (after full load) directly informs whether Tier 1 alone is sufficient.

---

## TOPIC 6: `fct_artwork_images` — Why Gold, Not Silver?

**Current state:** `fct_artwork_images` is a Gold model that UNIONs image data from staging and joins to `dim_artworks` for the surrogate FK.

**The question: Where should the UNION of Met + AIC images happen?**

**Option A: UNION in Gold (current pattern)**
- `stg_met__images` and `stg_aic__images` are independent staging models
- `fct_artwork_images` does `SELECT ... FROM stg_met__images UNION ALL SELECT ... FROM stg_aic__images`, then joins to `dim_artworks`
- Pro: Each staging model is source-faithful and testable in isolation
- Con: Gold model has source-specific logic (the UNION); adding a third source means editing Gold

**Option B: UNION in an intermediate model, Gold reads from intermediate**
- `int_combined_images` (Silver/intermediate layer) UNIONs staging models
- `fct_artwork_images` reads from `int_combined_images` + joins `dim_artworks`
- Pro: Gold is source-agnostic; adding a source means editing only the intermediate
- Con: Extra DAG node; intermediate layer adds complexity

**Option C: UNION in Silver via a combining staging model**
- `stg_combined__images` (in `staging/combined/`) explicitly UNIONs
- Pro: All combination logic lives in one layer
- Con: Blurs the staging convention (staging usually means "one source per model")

**Option D: Each Gold model handles its own UNION (current, keep as-is)**
- Gold models own the source-combination logic
- This is the dbt convention: staging = source-specific, marts = business-logic + combination
- The "join to dim_artworks for FK" is Gold-layer logic anyway
- Pro: Follows dbt best practices; Gold owns the business grain
- Con: Each Gold model that spans sources repeats UNION boilerplate

**The governance angle:**
- The governance plan (Layer 3) controls which schemas exist
- Whether UNIONs happen in Silver vs Gold doesn't change the schema footprint (both land in SILVER or GOLD)
- The decision is about DAG cleanliness and maintainability, not governance

**Status: PENDING DISCUSSION** — This is a DAG architecture preference. The dbt community convention favors Option D (Gold owns combination). But if you anticipate 5+ sources, an intermediate layer (Option B) prevents Gold models from growing unwieldy.

---

## TOPIC 7: Met Soft-Delete Columns

**Current Met state:** `RAW_MET_OBJECTS` has no `_is_deleted`, `_deleted_at`, or `_deletion_reason` columns. The Met extraction pipeline detects deletions differently:

- `MET_CSV_SNAPSHOT` stores object IDs from the OpenAccess CSV
- Anti-join between snapshot and `RAW_MET_OBJECTS` identifies removed objects
- But there's no persistent "this row is deleted" flag in Bronze

**Options for Met soft-delete:**

**Option A: Add soft-delete columns to `RAW_MET_OBJECTS` (match AIC pattern)**
- ALTER TABLE to add `_is_deleted BOOLEAN DEFAULT FALSE`, `_deleted_at`, `_deletion_reason`
- Extraction pipeline marks rows when objects disappear from the CSV
- Pro: Uniform pattern across all Bronze tables; Silver can filter identically for both sources
- Con: Requires Met extraction code changes; retroactive — existing rows need backfill

**Option B: Keep Met as-is, handle in Silver**
- `stg_met__artworks` includes all rows (no deletion concept)
- If a Met object is truly removed, it simply stops appearing in future snapshots — but the old Bronze row remains
- Pro: No extraction changes; Bronze is append-only
- Con: Silver may serve stale/removed artworks; no explicit deletion tracking

**Option C: Create a separate Met deletion-tracking table**
- `MET_DELETION_LOG` stores (object_id, detected_at, reason) when CSV anti-join fires
- Silver joins to this table to exclude deleted objects
- Pro: Doesn't modify existing Bronze table; explicit audit trail
- Con: Additional table; join complexity in Silver

**Option D: Use Snowflake streams + change tracking**
- Snowflake stream on `MET_CSV_SNAPSHOT` detects when an object_id disappears between snapshots
- A task processes the stream and writes to a deletion log
- Pro: Automated, event-driven
- Con: Over-engineered for current volume; requires stream + task infra

**Impact on Silver/Gold uniformity:**
- If Met has no `_is_deleted` and AIC does, the staging models have asymmetric WHERE clauses
- `stg_met__artworks`: `SELECT * FROM source` (no filter)
- `stg_aic__artworks`: `SELECT * FROM source WHERE _is_deleted = FALSE`
- This asymmetry is fine functionally but may confuse future maintainers

**Status: PENDING DISCUSSION** — This is a design debt decision. The AIC pattern (soft-delete in Bronze) is architecturally cleaner. Whether to retrofit Met now or accept the asymmetry is a prioritization choice.

---

## TOPIC 8: Governance Through These Pipelines

**How the governance plan (5 layers) applies to the AIC Silver/Gold work:**

**Layer 1 (RBAC):** Already implemented. `ARTWORK_TRANSFORMER_SVC` has `CREATE VIEW` on SILVER and `CREATE TABLE` on GOLD. No `CREATE SCHEMA`. The AIC staging models land in the same SILVER schema as Met — no new schemas needed. No additional grants required.

**Layer 2 (Cost):** Already implemented. Resource monitor on the warehouse. AIC staging models are views (zero compute at creation time). Gold tables are small (131k rows × 4 Gold tables). No cost risk from AIC addition.

**Layer 3 (Object Proliferation):**
- `generate_schema_name` allowlist already includes SILVER and GOLD — AIC models pass validation
- Object tagging: if implemented, new AIC models automatically get tagged via post-hook
- Orphan detection: new models must be added to the manifest. If an AIC staging model is later removed, the orphan query catches it
- **Action needed:** Verify the `generate_schema_name` macro handles the `aic` subfolder correctly (it should — dbt uses `+schema` config, not folder names)

**Layer 4 (Multi-developer):**
- Not yet relevant (solo developer)
- When relevant: AIC models would land in `DEV_SILVER` / `DEV_GOLD` per the macro
- No additional config needed

**Layer 5 (Observability):**
- `source freshness` needs a new `_aic__sources.yml` with `loaded_at_field: _EXTRACTED_AT` and `freshness: warn_after: {count: 30, period: day}` (AIC dump is monthly)
- `query_tag` auto-set by dbt for new models — no config needed
- Row-count tests on staging models (same as Met) guard against empty/exploded loads

**New governance considerations specific to multi-source Gold:**
- When Gold models UNION multiple sources, a bad staging model from one source can corrupt the entire Gold table
- Options for isolation:
  - Run sources in separate dbt invocations with `--select tag:aic` / `--select tag:met`
  - Add per-source row-count assertions in Gold (not just total, but per `source_system`)
  - Use `dbt build` (not `dbt run`) so tests gate the Gold materialization

**Status: APPROVED (existing governance applies) + NEEDS IMPLEMENTATION (source freshness, per-source Gold tests)**

---

## TOPIC 9: Summary Status Table

| Topic | Status | Blocking? |
|-------|--------|-----------|
| Image coverage audit (full load) | Needs implementation | Yes — informs image model design |
| `stg_aic__images` grain & URL construction | Pending discussion | Yes — determines Gold image model shape |
| Gold artist combination strategy (UNION vs resolution) | Pending discussion | Yes — determines Gold FK shape |
| Entity resolution approach & tooling | Pending discussion | Yes — cascades to all Gold models |
| `fct_artwork_images` UNION location (Silver vs Gold) | Pending discussion | No — cosmetic/maintainability |
| Met soft-delete alignment | Pending discussion | No — can be retrofitted later |
| Governance: source freshness config | Needs implementation | No — non-blocking but important |
| Governance: per-source Gold row-count tests | Needs implementation | No — defense-in-depth |
| AIC `alt_image_ids` handling | Pending discussion (depends on coverage audit) | Deferred until audit data available |

---

## Reference: Available AIC Payload Keys

### Artworks (98 keys)

Grouped by category:

**Identity:** `id`, `api_link`, `api_model`, `title`, `alt_titles`, `main_reference_number`

**Dates:** `date_display`, `date_start`, `date_end`, `date_qualifier_id`, `date_qualifier_title`, `fiscal_year`, `fiscal_year_deaccession`

**Artists:** `artist_id`, `artist_ids`, `artist_display`, `artist_title`, `artist_titles`, `alt_artist_ids`

**Classification:** `artwork_type_id`, `artwork_type_title`, `classification_id`, `classification_ids`, `classification_title`, `classification_titles`, `department_id`, `department_title`

**Medium/Materials:** `medium_display`, `dimensions`, `dimensions_detail`, `material_id`, `material_ids`, `material_titles`

**Geography/Location:** `place_of_origin`, `gallery_id`, `gallery_title`, `latitude`, `longitude`, `latlon`, `is_on_view`

**Style/Subject:** `style_id`, `style_ids`, `style_title`, `style_titles`, `subject_id`, `subject_ids`, `subject_titles`, `technique_id`, `technique_ids`, `technique_titles`, `term_titles`, `alt_style_ids`, `alt_subject_ids`, `alt_technique_ids`, `alt_material_ids`, `alt_classification_ids`, `category_ids`, `category_titles`, `theme_titles`

**Images:** `image_id`, `alt_image_ids`, `thumbnail` (object: `alt_text`, `height`, `width`, `lqip`), `color`, `colorfulness`, `is_zoomable`, `max_zoom_window_size`, `has_advanced_imaging`

**Text/Description:** `description`, `short_description`, `inscriptions`, `provenance_text`, `publication_history`, `exhibition_history`, `catalogue_display`, `edition`

**Rights/Access:** `is_public_domain`, `copyright_notice`, `credit_line`

**Boost/Visibility:** `is_boosted`, `boost_rank`, `has_not_been_viewed_much`, `has_educational_resources`, `has_multimedia_resources`

**Linked Resources:** `document_ids`, `sound_ids`, `video_ids`, `text_ids`, `section_ids`, `section_titles`, `site_ids`, `nomisma_id`, `suggest_autocomplete_all`, `on_loan_display`

**Metadata:** `source_updated_at`, `updated_at`, `timestamp`, `publishing_verification_level`

### Agents (15 keys)

`id`, `title`, `sort_title`, `alt_titles`, `is_artist`, `birth_date`, `death_date`, `description`, `ulan_id`, `api_link`, `api_model`, `source_updated_at`, `updated_at`, `timestamp`, `suggest_autocomplete_all`
