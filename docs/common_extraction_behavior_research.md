# Common Extraction Behavior Research Notes

Verified on 2026-07-04.

This document reviews common behavior that could be reusable across artwork and cultural
collection extractors. It is research only. It does not choose an architecture, propose a
new package layout, or authorize changes to repository behavior.

The purpose is to help an AI or human recognize reuse opportunities without violating the
repository rule that orchestration remains YAML-driven and source-decoupled.

## Inputs Reviewed

- `docs/open_access_artwork_api_catalog.md`
- `docs/smithsonian_open_access_implementation_notes.md`
- `extraction/met/README.md`
- `extraction/aic/README.md`
- `extraction/met/config.py`
- `extraction/aic/config.py`
- `orchestration/artwork_orchestration/ADDING_A_SOURCE.md`
- `orchestration/artwork_orchestration/SCHEMA.md`
- `orchestration/artwork_orchestration/sources/met.yaml`
- `orchestration/artwork_orchestration/sources/aic.yaml`
- `orchestration/artwork_orchestration/sources/cma.yaml`
- `infrastructure/create_bronze_tables.sql`

## Guardrails For Any Future Common Behavior

Common behavior must stay generic. It should help source-specific extractors do transport,
storage, retry, provenance, and validation work without knowing museum names, table names,
or provider-specific field semantics.

Rules for future implementation decisions:

- Do not put museum names, table names, source-specific endpoint paths, or provider branches
  in orchestration framework Python.
- Do not infer a universal artwork schema in Python. Bronze keeps raw payloads; dbt staging
  owns typed source-specific interpretation.
- Do not normalize media rights into a single boolean without preserving source evidence.
- Do not assume API access is better than dumps. Several documented sources prefer dumps for
  full snapshots.
- Do not assume open metadata means open media. The catalog repeatedly separates metadata
  license, image availability, and image reuse rights.
- Do not build a common abstraction from one source. Require at least two source families or
  one current source plus a verified near-term source with the same shape.
- Keep import-time behavior side-effect-free. Network, Snowflake, dbt, cache, and credential
  work belongs in explicit commands.
- Prefer typed config, injected collaborators, and small protocols over inheritance-heavy
  frameworks.

## Current Local Evidence

The existing repository already shows three reusable source shapes.

### Bulk Snapshot Source

Observed in AIC and relevant to CMA, NGA, MoMA, Tate, Mia, and many aggregator or GitHub
datasets.

Typical behavior:

- Download or reuse a dump.
- Read an archive or repository snapshot.
- Convert source records to gzipped NDJSON.
- Stage files to Snowflake.
- `COPY` into temporary or target tables.
- `MERGE` into Bronze.
- Track batch ID and extraction timestamp.
- Optionally soft-delete rows not seen in the current snapshot.

### Hybrid Dump Plus API Enrichment Source

Observed in Met and relevant to sources that have a broad dump but require bounded API
calls for images, manifests, current details, or updated records.

Typical behavior:

- Land a source snapshot first.
- Seed a control table from the snapshot.
- Claim a bounded worklist slice.
- Call a rate-limited API for enrichment.
- Write raw data and outcome state separately.
- Reclaim abandoned leases.
- Retry transient failures without repeating completed work.

### API Or Feed Crawling Source

Not yet fully implemented as a local generic pattern, but repeatedly visible in the catalog.

Relevant mechanisms:

- Offset or page pagination.
- Cursor or page-token pagination.
- OAI-PMH resumption tokens.
- ActivityStreams change feeds.
- SPARQL result paging.
- GraphQL pagination.
- Search endpoints with filters and changed-since parameters.

## External Research Added In This Pass

The following standards and official documentation validate that several opportunities are
real reusable mechanics, not just local project accidents.

| Area | Source | Reusable fact |
| --- | --- | --- |
| HTTP retry and throttle response | [RFC 9110 Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after) and [RFC 6585 429](https://www.rfc-editor.org/rfc/rfc6585#section-4) | `Retry-After` can be either delay seconds or an HTTP date; `429` is the standard rate-limit status and may include `Retry-After`. |
| API auth shapes | [OpenAPI Security Scheme Object](https://spec.openapis.org/oas/v3.1.0.html#security-scheme-object) | Common HTTP API auth categories include `apiKey`, `http`, `oauth2`, `openIdConnect`, and `mutualTLS`; API keys can be placed in query, header, or cookie. |
| Bearer auth | [RFC 6750](https://www.rfc-editor.org/rfc/rfc6750) | Bearer tokens should normally be transmitted in the `Authorization: Bearer` header; URI query tokens are documented but not recommended. |
| Basic auth | [RFC 7617](https://www.rfc-editor.org/rfc/rfc7617) | Basic auth is username/password scoped by server realm; api.data.gov also documents API-key-as-username for some services. |
| API-key placement and rate-limit headers | [api.data.gov developer manual](https://api.data.gov/docs/developer-manual/) | Supports `X-Api-Key`, `api_key`, or Basic username placement; default key limit is 1,000/hour, `DEMO_KEY` is lower, and responses expose `X-RateLimit-Limit` and `X-RateLimit-Remaining`. |
| Provider User-Agent policy | [Wikimedia User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy) and [AIC docs](https://api.artic.edu/docs/) | Automated clients may need descriptive User-Agent or provider-specific contact headers; generic library defaults can be rejected. |
| OAI-PMH pagination | [OAI-PMH 2.0](https://www.openarchives.org/OAI/openarchivesprotocol.html) | `resumptionToken` is opaque, must be reused as the next request argument, may expire, and an empty token marks completion. |
| ActivityStreams pagination | [ActivityStreams 2.0](https://www.w3.org/TR/activitystreams-core/) | Collection pages can link via `first`, `next`, `prev`, and `last`; ordered reconstruction should follow page links rather than assuming arbitrary page processing order. |
| GraphQL cursor pagination | [GraphQL Cursor Connections Specification](https://relay.dev/graphql/connections.htm) | Connection-style pagination uses `edges`, per-edge opaque `cursor`, `pageInfo`, `hasNextPage`, and `first`/`after` style arguments. |
| IIIF Image API | [IIIF Image API 3.0](https://iiif.io/api/image/3.0/) | Image requests have a standard URI shape with `region`, `size`, `rotation`, `quality`, and `format`; `info.json` describes service capabilities. |
| IIIF Presentation API | [IIIF Presentation API 3.0](https://iiif.io/api/presentation/3.0/) | A Manifest describes a compound object, has `items`, and each item is a Canvas with content resources. |
| Snowflake staged loading | [Snowflake PUT](https://docs.snowflake.com/en/sql-reference/sql/put), [COPY INTO table](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table), and [MERGE](https://docs.snowflake.com/en/sql-reference/sql/merge) | Local files are staged with `PUT`, loaded with `COPY INTO`, and reconciled with `MERGE`; Snowflake does not support tar files directly in `PUT`, `COPY` can validate files and purge successfully loaded files, and `MERGE` handles matched and unmatched rows. |
| GitHub release snapshots | [GitHub releases API](https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28) | Public latest-release metadata can be fetched without authentication; latest means latest non-draft, non-prerelease release by `created_at`, not necessarily publish time. |

## Highest-Leverage Validated Opportunities

These items look high leverage because they appear in local code, provider research, or both.
They are still not implementation decisions.

| ID | Opportunity | Validation | Caution |
| --- | --- | --- | --- |
| 1 | HTTP client base | Met, AIC, and many catalog providers require HTTPS requests. | Must support per-provider headers, throttling, and auth without source branches. |
| 2 | Authentication strategies | Catalog includes no auth, query key, header key, bearer or token, Basic-style, and GraphQL-token flows. | Secrets must be source-configured and validated at command edges. |
| 3 | Rate-limit handling | Met handles 403 and 429 throttle signals; AIC, LOC, Wikimedia, api.data.gov, and others document limits. | Retry policy must not hide permanent authorization or license errors. |
| 4 | Pagination strategies | Catalog includes offset, page, cursor, pageToken, token, shard, dump, and feed models. | Pagination must preserve source order and resume state where the source supports it. |
| 5 | Bulk download helpers | AIC tarball, Smithsonian S3, GitHub CSV/JSON datasets, and DPLA/Europeana downloads motivate this. | Cache and resume behavior must avoid stale data being mistaken for fresh extraction. |
| 6 | NDJSON chunk writer | AIC and legacy Met load paths use staged NDJSON-like patterns. | Chunk identity, row counts, compression, and temp cleanup are operationally important. |
| 7 | Snowflake raw loader | Existing loaders use stage, `COPY`, and `MERGE` patterns into Bronze. | It must not know source table names except through explicit caller configuration. |
| 8 | Extraction logging | `EXTRACTION_LOG` exists and local READMEs refer to batch observability. | Logging should be run-level or batch-level, not row-by-row control state. |
| 9 | Raw record model | Bronze tables consistently carry natural key, raw payload, batch ID, source system, and extracted time. | This is a storage convention, not a shared artwork schema. |
| 10 | Watermark/change model | AIC has `AIC_LOAD_WATERMARK`; providers expose updated timestamps, hashes, signatures, releases, and feeds. | Different sources need different change evidence; no single field is authoritative. |
| 11 | Worklist/leasing model | Met has control, worklist, claim, lease, callback, and lease-reclaim behavior. | Generalize only if a second API-enrichment source needs bounded claims. |
| 12 | Rights/media classifier | Every provider section distinguishes metadata, media availability, and reuse rights. | Classifier should record evidence and confidence, not erase provider nuance. |
| 13 | IIIF/media helpers | AIC, V&A, Rijksmuseum, Europeana, Wellcome, Harvard, Getty, SMK, and Smithsonian have media URL patterns. | IIIF, IDS, thumbnails, and provider download URLs are related but not identical. |
| 14 | CLI contract | Existing sources use `snapshot`, `status`, `seed-control`, and enrichment commands. | Keep command contracts simple enough for YAML orchestration to express generically. |
| 15 | Test harness | Met has throttle tests; future helpers need fake APIs, dumps, Snowflake SQL assertions, and retry tests. | Tests should validate contracts without requiring live provider calls. |

## Reviewed Additional Opportunities

These are credible reuse candidates, but some are lower-level utilities while others are
documentation, modeling, or testing conventions.

| ID | Opportunity | Assessment |
| --- | --- | --- |
| 16 | Provider capability model | Useful for docs and planning; dangerous if it becomes a Python switchboard. Keep capability declarations data-driven if implemented. |
| 17 | Source configuration dataclasses for extractor packages | Already visible in Met and AIC. A shared pattern could reduce repeated env parsing and validation. |
| 18 | Common downloader cache | Useful for AIC, Met CSV, GitHub datasets, and archive downloads. Needs freshness evidence such as ETag, Last-Modified, file hash, or explicit `--no-refresh`. |
| 19 | Archive readers | Strong candidate. Catalog includes tar.bz2, zip-like dumps, gzip, CSV, JSON arrays, and JSON lines. |
| 20 | CSV-to-raw-payload mapper | Strong candidate because Met, NGA, MoMA, Tate, and exports use CSV. Preserve raw strings and source headers. |
| 21 | JSON array streaming reader | Useful for large JSON files that should not be loaded fully into memory. |
| 22 | JSONL shard reader | Useful for Smithsonian S3 and other sharded JSON-line datasets. |
| 23 | GitHub release/dataset fetcher | Useful for NGA, MoMA, Tate, Mia, Met CSV, and CMA GitHub data. Must distinguish releases from branch snapshots. |
| 24 | S3 public bucket lister | Useful for Smithsonian and AIC-like public object storage. Must support no-sign-request and HTTPS index alternatives. |
| 25 | Metadata SQL snippets | Existing YAML supports metadata SQL. Reusable snippets could be docs or generated SQL, but should avoid hardcoded table names. |
| 26 | Generic nonempty/freshness checks | Already partly represented in orchestration YAML. Future work should prefer dbt data-quality tests where possible. |
| 27 | Generic soft-delete/stale-record handler | AIC uses soft deletion. Dump-based sources may need last-seen-batch or anti-join behavior. |
| 28 | Entity mapping conventions | Useful naming convention: artworks, agents/artists, images/media, exhibitions, departments, terms. Keep source payloads raw. |
| 29 | Error taxonomy | Strong candidate for consistent retry and observability. Categories should separate transient, permanent, auth, rate, decode, and rights/media errors. |
| 30 | Retry policy config bridge | Useful to align extractor behavior and orchestration retry expectations. Avoid pushing provider-specific retry rules into framework code. |
| 31 | Structured provider documentation template | Strong docs-only win. The catalog already follows scope, license, auth, endpoints, pagination, media, rights, and questions. |
| 32 | dbt staging conventions | Useful for consistency but belongs in dbt model design, not extractor framework Python. |
| 33 | dbt source generation or documentation checks | Plausible, especially to keep YAML-produced tables and dbt source names aligned. Needs careful repo-wide design. |
| 34 | Secret/env var registry | Useful for source config and missing-secret errors. Must avoid central source-specific branches. |
| 35 | Partition discovery helpers | Useful for departments, units, categories, and terms endpoints. Static versus discovered partitions should remain explicit. |
| 36 | Incremental planning helpers | Useful research tool: full snapshot, delta, changed-since, feed, or full reload only. Should not silently choose strategy. |
| 37 | Media URL validation/enrichment utilities | Useful later for HEAD/GET checks, content type, dimensions, and liveness. Avoid in initial loads unless needed. |
| 38 | Aggregator duplicate/reconciliation helpers | Important for Europeana, DPLA, DigitalNZ, Trove, MDS, and direct source overlap. High semantic risk; probably dbt or mart-layer concern. |
| 39 | External identifier handling | Useful for Wikidata QID, Getty ULAN, VIAF, accession numbers, source URLs, and IIIF IDs. Preserve all source identifiers. |
| 40 | Source-agnostic fixture generator | Strong test-support candidate. Fixtures can exercise raw payloads, paginated APIs, dumps, throttles, rights, and media cases. |

## Expanded Opportunities From The Research Pass

These additional opportunities were not in the original list but are visible from the
expanded catalog and local patterns.

| ID | Opportunity | Why It Matters |
| --- | --- | --- |
| 41 | OAI-PMH harvester | Rijksmuseum, Europeana, and other cultural sources expose OAI-PMH-style feeds. Resumption-token handling is reusable. |
| 42 | ActivityStreams crawler | Getty uses ActivityStreams for created, edited, and deleted records. This is a distinct change-feed pattern. |
| 43 | GraphQL client helper | Paris Musees exposes GraphQL after authentication. GraphQL pagination, variables, and token handling differ from REST. |
| 44 | SPARQL query helper | Getty, Wikidata, Europeana, and other linked-data providers expose SPARQL. Query paging and throttling can be reusable. |
| 45 | Linked Art / JSON-LD preservation helper | Getty and Rijksmuseum use Linked Art or JSON-LD-style records. Bronze may need to preserve contexts and linked entity references exactly. |
| 46 | OpenAPI/Swagger inspection notes | SMK exposes OpenAPI. A docs helper could record endpoints, parameters, and schemas, but generated clients are a later design choice. |
| 47 | Provider terms evidence capture | For rights-sensitive sources, capture source license URL, inspected date, and relevant rights fields alongside extractor docs. |
| 48 | Source freshness evidence model | Datasets expose Git commit SHA, release tag, S3 object metadata, dump timestamp, API updated fields, hashes, or signatures. |
| 49 | Extraction manifest artifact | Each run could record input URLs, versions, row counts, file hashes, and loaded tables for audit. This is separate from raw data. |
| 50 | Large-file streaming utilities | AIC tarball, Met CSV, and other dumps can be large enough to require streaming download and streaming parse. |
| 51 | Provider health probe | A lightweight command or docs pattern could test auth, endpoint availability, and expected response shape without loading data. |
| 52 | Partition slugging and label validation | Static partitions, departments, Smithsonian units, and provider categories need stable CLI-safe slugs mapped to exact source labels. |
| 53 | SQL identifier and object-name validation | Raw loaders need table, stage, and temp-object names. Validation should prevent injection and accidental invalid identifiers. |
| 54 | Local temp directory lifecycle | Dump extraction, NDJSON writing, and staged artifacts need predictable cleanup, retention for debugging, and crash-safe temp paths. |
| 55 | Provider contact/User-Agent policy | AIC and Wikimedia explicitly ask for descriptive headers; Met uses a configurable User-Agent. This should be visible per source. |
| 56 | Sample-record capture for docs and tests | Research can capture small sanitized payloads or payload-shape summaries for future fixtures without doing full ingestion. |
| 57 | Payload-size and row-count budgeting | Sources range from thousands to millions of records. Planning helpers can estimate disk, stage, and API volume before extraction. |
| 58 | Capability-to-orchestration fit check | A docs or validation checklist can ask whether current YAML supports a source shape before proposing framework changes. |
| 59 | Raw-field path inventory | For a provider, record candidate raw JSON paths for IDs, titles, dates, rights, media, agents, and timestamps before dbt work. |
| 60 | Source overlap register | Track whether an institution also appears through an aggregator, so duplicate/reconciliation work is explicit and delayed. |

## Additional Reusable Opportunities From This Pass

| ID | Opportunity | Why It Matters |
| --- | --- | --- |
| 61 | HTTP response evidence capture | Store status, selected headers, content type, elapsed time, retry count, and response byte count for logs and tests without storing secrets. |
| 62 | Retry-After parser | Standards allow both seconds and HTTP-date values. A common parser would avoid subtly different throttle waits in each extractor. |
| 63 | Rate-limit header observer | Providers such as api.data.gov expose limit and remaining headers. Observing them can improve logs even if throttling stays provider-configured. |
| 64 | Secret redaction utility | Error messages, manifests, and debug logs need consistent redaction for query-string API keys, Authorization headers, and Basic credentials. |
| 65 | Content-type and decode guard | HTTP helpers should distinguish JSON decode failure, XML feed parsing, CSV body handling, gzip body handling, and unexpected HTML error pages. |
| 66 | Resumable cursor state envelope | Opaque cursors, OAI-PMH tokens, ActivityStreams page URLs, and GraphQL end cursors need a shared way to persist token, issue time, scope, and expiry. |
| 67 | Staged-file manifest | Record each generated file path, row count, compressed size, content hash, target table, and stage prefix for audit and retry diagnosis. |
| 68 | Snowflake COPY result parser | COPY returns operational detail that should be parsed by column names or stable adapters, not brittle positional assumptions. |
| 69 | SQL file/template loader | Existing extractors externalize SQL. A common loader could keep SQL separate while validating expected template variables. |
| 70 | Identifier validation for SQL objects | Stage, table, schema, temp table, and file-format names need validation or quoting discipline before string templating. |
| 71 | Raw payload schema profiler | A docs or test helper could summarize observed keys, missingness, and type drift from fixtures or sampled dumps without changing load behavior. |
| 72 | Provider scope estimator | Before extraction, estimate row count, API calls, local disk, staged bytes, and runtime from provider metadata or dry-run probes. |
| 73 | Change-feed walker | ActivityStreams, OAI-PMH datestamps, API `updated_since`, and GitHub release tags all need source-specific walkers with common checkpoint metadata. |
| 74 | IIIF capability inspector | Fetch `info.json` or manifest metadata to record service profile, sizes, tiles, rights, and dimensions without deciding derivative policy. |
| 75 | Fixture sanitization and minimization | Real provider payloads need repeatable shrinking, secret removal, and license-safe storage before becoming source-agnostic fixtures. |

## Reusable Functionality Drill-Down

This section describes concrete contracts an AI might consider later. They are sketches for
future design discussion, not instructions to implement now.

### HTTP Transport

Potential common inputs:

- `method`: usually `GET`, but some search APIs support `POST`.
- `url`: fully resolved URL after source-specific endpoint choice.
- `params`: query parameters after source-specific filters are chosen.
- `headers`: User-Agent, contact, auth, and provider-specific advisory headers.
- `json_body` or `data_body`: request body for POST searches or GraphQL.
- `timeout_seconds`: connect/read or total timeout.
- `expected_content`: JSON, XML, CSV, bytes, gzip, or archive.
- `retry_profile`: max tries, base delay, max delay, jitter, and retryable classes.

Potential common outputs:

- `status_code`
- `headers`
- `content_type`
- `decoded_body` or `bytes_path`
- `elapsed_ms`
- `attempt_count`
- `retry_after_seconds`
- `request_url_redacted`
- `error_category`

Reusable rules to validate later:

- Parse `Retry-After` as either non-negative seconds or HTTP-date.
- Treat `429` and temporary `503` as retry candidates by default.
- Treat `401` and most `403` responses as non-retryable unless source configuration says
  a provider uses `403` as a throttle signal.
- Keep User-Agent/contact headers source-configurable.
- Redact auth values before logging request URLs, headers, exceptions, or manifests.
- Preserve unexpected content type as evidence instead of collapsing everything into
  `JSONDecodeError`.

### Authentication Strategies

Potential common strategy names:

- `none`
- `api_key_query`
- `api_key_header`
- `api_key_basic_username`
- `bearer_header`
- `basic`
- `graphql_token_header`

Potential fields:

- `secret_env_var`
- `header_name`
- `query_param_name`
- `username_env_var`
- `password_env_var`
- `token_prefix`
- `required`
- `redaction_label`

Research-backed cautions:

- Header placement is usually preferable for bearer tokens.
- Query-string keys are common in provider docs, but they leak more easily through logs and
  URLs.
- api.data.gov explicitly supports multiple key placement methods, so a strategy model
  should not assume one location.
- Authentication setup belongs at extractor command edges, not import time.

### Pagination And Feed Walking

Potential common page result fields:

- `records`
- `next_token`
- `next_url`
- `cursor`
- `complete`
- `reported_total`
- `page_number`
- `raw_page_metadata`

Potential strategy variants:

| Strategy | Config knobs | Stop condition | Important evidence |
| --- | --- | --- | --- |
| Offset/limit | offset param, limit param, start offset, page size, max offset. | Empty page, fewer than limit, reported total reached, or explicit cap. | Offset, limit, total, page record count. |
| Page/limit | page param, first page number, page size, total pages path. | Last page by total pages or empty/fewer-than-limit page. | Page number, page size, next page. |
| Cursor/page token | token param, token response path, first request params. | Missing or null next token. | Opaque token, token issue scope, response path. |
| OAI-PMH | verb, metadataPrefix, set, from/until, resumptionToken. | Empty resumption token after a list response. | Token, expirationDate, cursor, completeListSize. |
| ActivityStreams | collection URL, first page URL, next path. | Missing next link after page traversal. | Page URL, next URL, ordered/unordered flag. |
| GraphQL connection | query, variables, first, after, pageInfo path. | `hasNextPage` false or null `endCursor`. | End cursor, hasNextPage, result path. |
| Shard/index | index URL or object listing, shard path pattern. | All listed shards consumed. | Index version, shard URL, shard count. |

Rules to validate later:

- Treat OAI-PMH `resumptionToken` and GraphQL cursors as opaque strings.
- Store cursor state with the request scope that produced it, because filters and cursors
  are usually inseparable.
- Do not assume OAI-PMH incomplete lists are sorted just because they are split into pages.
- For ActivityStreams ordering, follow page links from `first` or `last`; do not process
  arbitrary pages and infer order.

### Bulk Download, Cache, And Archive Handling

Potential common download fields:

- `source_url`
- `destination_path`
- `cache_policy`
- `refresh`
- `expected_content_type`
- `expected_size_bytes`
- `etag`
- `last_modified`
- `sha256`
- `resume_supported`

Potential common archive reader fields:

- `archive_type`: tar, zip, gzip, bz2, plain directory, CSV, JSON array, JSONL.
- `member_filter`: path prefix, suffix, or explicit file list.
- `entity_type`: caller-supplied label for the records being emitted.
- `record_count`
- `source_member_path`
- `source_member_modified_at`

Research-backed cautions:

- Snowflake `PUT` stages files, but it does not support tar archives as loadable compressed
  data files; extractors must unpack tar-based provider dumps before staging records.
- `--no-refresh` and cache reuse should be explicit in CLI behavior and visible in run
  manifests.
- GitHub branch snapshots, release archives, and raw files have different freshness
  evidence. Do not treat them as equivalent.
- Preserve CSV headers and raw strings before applying optional null coercion or header
  normalization.

### Snowflake Raw Loading

Potential common load-plan fields:

- `database`
- `schema`
- `stage`
- `stage_prefix`
- `target_table`
- `staging_table`
- `file_format`
- `key_columns`
- `copy_columns`
- `merge_update_columns`
- `purge_after_copy`
- `validation_mode`
- `source_system`
- `batch_id`

Potential common output fields:

- `files_staged`
- `rows_scanned`
- `rows_loaded`
- `rows_parsed`
- `copy_errors`
- `merge_inserted`
- `merge_updated`
- `merge_deleted`
- `stage_prefix`

Rules to validate later:

- Validate SQL identifiers before templating them into SQL files.
- Keep SQL files externalized so source-specific SQL remains reviewable.
- Prefer set-based `COPY` and `MERGE` over row-by-row inserts or callbacks.
- Use `COPY` validation mode for smoke tests where possible.
- Treat `PURGE=TRUE` as best-effort cleanup, not proof that stage files are gone.
- Capture staged-file manifests before `COPY` so retries can be diagnosed.

### Worklist And Lease Control

Potential common state fields:

- `natural_key`
- `work_status`
- `attempt_count`
- `last_attempt_at`
- `last_success_at`
- `last_error_code`
- `last_error_message`
- `claimed_by_batch`
- `claimed_at`
- `lease_expires_at` or configured TTL
- `source_changed_at`
- `last_seen_batch_id`

Possible common transitions:

- `pending -> claimed -> done`
- `pending -> claimed -> no_data`
- `pending -> claimed -> retryable_error -> pending`
- `pending -> claimed -> terminal_error`
- `claimed -> pending` when lease expires
- `done -> pending` when source change evidence is newer than success evidence

Scope cautions:

- This should not become universal until another provider needs bounded API enrichment.
- Worklist state is control state, not raw data.
- Descriptive truth should stay in raw snapshot tables or source payloads, not be copied
  widely into control tables.
- Batch callbacks should remain set-based.

### Rights And Media Evidence

Potential common rights evidence envelope:

- `metadata_rights_text`
- `metadata_license_url`
- `metadata_license_code`
- `metadata_public_domain_flag`
- `media_rights_text`
- `media_license_url`
- `media_license_code`
- `media_public_domain_flag`
- `rights_source_paths`
- `provider_policy_url`
- `verified_on`
- `classifier_result`
- `classifier_confidence`
- `classifier_notes`

Potential common media evidence envelope:

- `media_id`
- `provider_media_id`
- `iiif_service_url`
- `iiif_info_url`
- `iiif_manifest_url`
- `thumbnail_url`
- `download_url`
- `width`
- `height`
- `format`
- `is_primary`
- `source_payload_path`

Rules to validate later:

- Store provider evidence even if downstream classifiers produce convenient booleans.
- Keep metadata rights and media rights separate.
- Distinguish image availability from image reuse rights.
- Distinguish IIIF Image API services from IIIF Presentation manifests and non-IIIF
  thumbnail endpoints.
- Treat media liveness checks as optional enrichment unless the source requires them.

### IIIF Helpers

Potential Image API helper inputs:

- `service_base_url`
- `identifier`
- `region`
- `size`
- `rotation`
- `quality`
- `format`

Potential Image API helper outputs:

- `image_url`
- `info_url`
- `normalized_service_url`
- `requested_derivative`

Potential Presentation API helper fields:

- `manifest_id`
- `manifest_type`
- `label`
- `items`
- `canvas_ids`
- `homepage`
- `see_also`
- `rendering`

Research-backed cautions:

- IIIF Image API URI components must be path segments, not arbitrary query parameters.
- `info.json` is the right place to inspect service capabilities.
- A Presentation Manifest can duplicate metadata already available from a provider API; it
  should not automatically become the source of truth.
- Some provider thumbnails look IIIF-like operationally but are not full IIIF services.

### Test Harness Specificity

Reusable fixtures and fakes should cover:

- HTTP success, 429, 503 with `Retry-After`, provider-specific 403 throttle, 401/403 auth
  failure, malformed JSON, unexpected HTML, timeout, and connection reset.
- Offset, page, cursor, OAI-PMH, ActivityStreams, GraphQL, shard, and dump pagination.
- Archive types: tar.bz2, zip, gzip, plain CSV, JSON array, JSONL, and directory tree.
- Snowflake SQL rendering with safe identifiers and expected template variables.
- `COPY`/`MERGE` result parsing.
- Batch manifest creation and secret redaction.
- Rights/media evidence cases: open metadata with restricted media, missing media, public
  domain media, ambiguous rights text, aggregator-provided rights.
- Worklist lease reclaim and retry transitions if worklist behavior is generalized.

## Common Behavior Boundaries

The table below separates reusable mechanics from source-specific meaning.

| Area | Common Candidate | Source-Specific Responsibility |
| --- | --- | --- |
| HTTP | Sessions, timeouts, retries, response decoding, headers. | Endpoint paths, query fields, provider-specific status interpretation. |
| Auth | Strategy types and missing-secret errors. | Env var names, token source, account setup, provider key limits. |
| Pagination | Iterator contracts and resume tokens. | Which endpoint to call, which filters are valid, stop conditions. |
| Bulk files | Download, cache, archive read, file hash, chunking. | Which files in the dump matter, source entity semantics. |
| Raw load | Stage, `COPY`, `MERGE`, temp table lifecycle, row counts. | Target tables, natural keys, merge keys, soft-delete rules. |
| State | Batch IDs, watermarks, leases, status callbacks. | What counts as changed, deleted, done, no image, or retryable. |
| Rights | Evidence fields, classifier result envelope, provenance. | Provider-specific legal interpretation and downstream eligibility rules. |
| Media | IIIF/service URL parsing, dimensions, thumbnail derivation helpers. | Which image is primary, allowed derivative sizes, reuse rights. |
| CLI | Common flags and exit-code expectations. | Subcommands needed for the source's actual extraction strategy. |
| Tests | Fake APIs, fake dumps, Snowflake SQL assertion helpers. | Provider-specific payload fixtures and edge cases. |

## Anti-Patterns An AI Should Avoid

- Creating `if source == "met"` or similar branches in orchestration framework Python.
- Adding a new source by editing a hand-maintained Python list.
- Converting every provider into the same API-crawl shape when a dump is documented and
  better suited for full snapshots.
- Treating `has_image`, `public_domain`, `cc0`, `rights`, or `license` as interchangeable.
- Dropping provider payload details because they do not fit a universal raw model.
- Introducing a common base class that forces unrelated providers into the same lifecycle.
- Adding hidden network or Snowflake calls at import time.
- Making a helper that owns both source transport and downstream domain mapping.
- Treating aggregators as direct museum sources without duplicate and attribution planning.
- Implementing media URL validation as part of a first snapshot unless the source requires
  it for correctness.

## Research Questions Before Any Implementation

These questions should be answered in a future design task before code is changed.

- Which two or more current or planned sources prove each common helper is needed?
- Is the behavior transport-level, storage-level, orchestration-level, dbt-level, or
  domain-semantics-level?
- Can the orchestration YAML express the behavior today?
- If YAML cannot express it, is the missing concept generic across sources?
- What typed dataclass or enum would validate the behavior at load time?
- What source-specific facts must remain in per-source config or extractor packages?
- What fixtures prove the helper works without live network calls?
- How will the helper expose actionable, file- and field-scoped errors?
- What failure modes are retryable, and which should fail fast?
- What evidence proves a batch is fresh, complete, and reproducible?
- Does the helper preserve raw source payloads and rights evidence?
- What is the smallest future PR that could add the helper without changing source
  behavior?

## Suggested Documentation Template For Future Sources

This template is reusable for research docs. It is not an extractor interface.

```markdown
# <Source Name> Programmatic Access Notes

Verified on YYYY-MM-DD.

## Primary Links

- <official docs>
- <policy or license docs>
- <bulk/API endpoint docs>

## Access Modes

- API:
- Bulk:
- Feed:
- IIIF/media:

## Authentication

- Key required:
- Auth placement:
- Secret/env vars to consider:

## Scope And License

- Record count:
- Metadata license:
- Media license:
- Attribution:
- Restrictions:

## Endpoint Or Dump Shape

- Endpoints/files:
- Pagination/shards:
- Entity types:
- Natural keys:
- Update fields:

## Media And Rights

- Image fields:
- IIIF/service URLs:
- Rights fields:
- Open questions:

## Local Mapping Questions

- Bronze entity tables:
- Batch and freshness evidence:
- Soft-delete/stale detection:
- YAML fit:
- Tests and fixtures:
```

## Practical Prioritization For Future Design

If this research becomes implementation work later, the first design candidates should
probably be the mechanics already repeated by local sources:

- Source config/env validation pattern.
- Download/cache/archive/streaming helpers.
- NDJSON chunk writer.
- Snowflake stage/COPY/MERGE helper.
- Batch/extraction logging envelope.
- Fake API and fake dump test harness.

The highest-risk candidates should remain research-only until specific source work demands
them:

- Rights/media classifier.
- Aggregator duplicate reconciliation.
- External identifier authority model.
- dbt source generation.
- Universal worklist/leasing model.
- Linked-data/SPARQL abstractions.
