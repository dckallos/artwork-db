You are continuing work in /Users/daniel/dev/artwork-db.

Your task is to continue and deepen the open-access artwork data-source research started in the previous context. The prior assistant created two Markdown files that should remain available and should be reviewed first:

- /Users/daniel/dev/artwork-db/docs/smithsonian_open_access_implementation_notes.md
- /Users/daniel/dev/artwork-db/docs/open_access_artwork_api_catalog.md

Your job is to make the research more exhaustive. We are interested in sources where artworks or museum/cultural collection records have both:

1. Open access, public-domain, CC0, public metadata, or otherwise reusable collection data.
2. An API, data dump, GitHub repository, S3 bucket, OAI-PMH feed, IIIF/Linked Art endpoint, GraphQL endpoint, CSV/JSON export, or other easily programmatic retrieval layer.

Do not limit the search to APIs. Data dumps are fine. Programmatic metadata access is what matters.

Important repo rule: do not make design decisions yet. Gather facts, source links, endpoint shapes, bulk data paths, authentication/rate-limit details, data model notes, media rights notes, and implementation considerations. Keep architecture choices as open questions unless they are already established repo rules.

Previous outputs already created:

1. docs/smithsonian_open_access_implementation_notes.md
   - Smithsonian-focused implementation briefing.
   - Covers EDAN API endpoints, S3 bulk metadata layout, record/media shapes, rate-limit concerns, Met/AIC extraction patterns, local Bronze/dbt/orchestration context, and implementation questions.

2. docs/open_access_artwork_api_catalog.md
   - Initial public open-access artwork API/data catalog.
   - Covers Smithsonian, Met, AIC, CMA, Harvard, V&A, Rijksmuseum, Europeana, DPLA, LOC, Cooper Hewitt, Wellcome, Wikimedia/Wikidata, and common extraction considerations.

The previous assistant concluded that the current catalog is broad but not exhaustive. Treat it as v1, not final.

Sources already found and worth preserving or expanding:

High-confidence sources already documented in the catalog:

- Smithsonian Institution Open Access
  - Links:
    - https://registry.opendata.aws/smithsonian-open-access/
    - https://www.si.edu/openaccess/devtools
    - https://edan.si.edu/openaccess/apidocs/
    - https://edan.si.edu/openaccess/docs/
    - https://edan.si.edu/openaccess/docs/more.html
    - https://github.com/Smithsonian/OpenAccess
    - https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/index.txt
  - Programmatic access:
    - Public S3 bucket: s3://smithsonian-open-access/
    - HTTPS S3 object access.
    - EDAN API at https://api.si.edu/openaccess.
  - API endpoints found:
    - GET /api/v1.0/search
    - GET /api/v1.0/category/:cat/search
    - GET /api/v1.0/content/:id
    - GET /api/v1.0/terms/:category
    - GET /api/v1.0/stats
  - API key:
    - Required for EDAN API through api.data.gov.
    - S3 bulk access does not require AWS credentials.
  - Notes:
    - S3 metadata organized by Smithsonian unit, then shard files such as 00.txt through ff.txt.
    - Shards are line-delimited JSON.
    - EDAN fields include id, unitCode, type, content, hash, docSignature, timestamp, lastTimeUpdated, title.
    - Common content sections: descriptiveNonRepeating, indexedStructured, freetext.
    - Media appears under content.descriptiveNonRepeating.online_media.media.
    - Image URLs often use https://ids.si.edu/ids/deliveryService or https://ids.si.edu/ids/download.
    - The GitHub repo was observed as archived/read-only in May 2026 and points toward S3 for current bulk access.
    - api.data.gov default rate limit found: 1,000 requests/hour per key; DEMO_KEY is lower.

- The Metropolitan Museum of Art
  - Links:
    - https://metmuseum.github.io/
    - https://github.com/metmuseum/openaccess
    - https://www.metmuseum.org/about-the-met/policies-and-documents/open-access
  - Programmatic access:
    - REST API at https://collectionapi.metmuseum.org/public/collection/v1
    - Public Open Access CSV dataset on GitHub.
  - API endpoints:
    - GET /objects
    - GET /objects/{objectID}
    - GET /departments
    - GET /search
  - Auth:
    - No API key required.
  - Rate:
    - Docs ask clients to limit to 80 requests/sec.
  - Local repo relevance:
    - Current extractor loads Met CSV snapshot first, then performs bounded API enrichment for image fields.
    - Good example of hybrid dump plus API enrichment.

- Art Institute of Chicago
  - Links:
    - https://api.artic.edu/docs/
    - https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2
  - Programmatic access:
    - REST API at https://api.artic.edu/api/v1
    - Public nightly data dump tarball.
    - IIIF images at https://www.artic.edu/iiif/2
  - Auth:
    - No API key required.
  - Rate:
    - Anonymous users throttled to 60 requests/minute.
    - Docs ask high-volume users to scrape no more than one request/sec, single-threaded.
    - Docs request AIC-User-Agent header.
  - Notes:
    - API deep pagination capped at 10,000 records.
    - Dump recommended for full snapshots and large extraction.
  - Local repo relevance:
    - Current extractor uses dump, not full API crawl.
    - Good example of one-step bulk snapshot producing multiple raw tables.

- Cleveland Museum of Art
  - Links:
    - https://openaccess-api.clevelandart.org/
    - https://github.com/ClevelandMuseumArt/openaccess
  - Programmatic access:
    - REST API at https://openaccess-api.clevelandart.org/api
    - GitHub open-access data.
  - Endpoints found:
    - GET /api/artworks/
    - GET /api/artworks/{id}
  - Auth:
    - No key indicated in public docs.
  - Notes:
    - Metadata CC0.
    - Images depend on image rights.
    - API/GitHub data updated daily.
    - Supports filters such as q, cc0, copyrighted, department, type, orderby, has_image, skip, limit, updated_since, fields.
    - Limit default/max observed: 1000.
  - Local repo:
    - There is an extraction/cma/run.py placeholder/demo and orchestration/artwork_orchestration/sources/cma.yaml in the repo.

- Harvard Art Museums
  - Links:
    - https://github.com/harvardartmuseums/api-docs
    - https://harvardartmuseums.org/collections/api
  - Programmatic access:
    - REST API at https://api.harvardartmuseums.org
  - Auth:
    - API key required as apikey query parameter.
  - Notes:
    - Resources include Object, Person, Exhibition, Gallery, Image, etc.
    - JSON responses include info, records, aggregations.
    - Pagination default size 10, max size 100.
    - Dataset refreshed daily around 6am.
    - Image records can include baseimageurl and primaryimageurl; restricted images may be omitted.

- Victoria and Albert Museum
  - Links:
    - https://developers.vam.ac.uk/
    - https://developers.vam.ac.uk/guide/v2/welcome.html
  - Programmatic access:
    - Public collection APIs.
    - JSON and CSV.
    - IIIF image access.
  - Auth:
    - No key observed in inspected docs.
  - Notes:
    - Portal describes more than 1 million collection records and more than 500,000 images.
    - Docs sections to inspect: Search, Filters, Results, Restrictions, Images, IIIF.
    - Guide says compressed export can be more efficient for bulk use; verify current official bulk export path.

- Rijksmuseum Data Services
  - Links:
    - https://data.rijksmuseum.nl/
    - https://data.rijksmuseum.nl/docs/
    - https://data.rijksmuseum.nl/docs/search
  - Programmatic access:
    - Search API.
    - OAI-PMH API.
    - LDES API.
    - Downloads.
    - Persistent identifier resolver.
  - Search endpoint:
    - GET https://data.rijksmuseum.nl/search/collection
  - Auth:
    - Current Data Services Search API docs did not indicate an API key.
  - Notes:
    - Metadata for about 800,000 objects.
    - High-resolution photographs for about 600,000 objects.
    - Search response uses Linked Art Search model.
    - Pagination uses pageToken; each page up to 100 results.

- Europeana
  - Links:
    - https://pro.europeana.eu/discover-the-data/apis
    - https://pro.europeana.eu/page/search
    - https://pro.europeana.eu/page/record
    - https://pro.europeana.eu/page/iiif
  - Programmatic access:
    - Search API, Record API, Entity API, Annotations API, IIIF API, SPARQL, Dataset Download, OAI-PMH, Thumbnail API.
  - Auth:
    - API key required for core API access.
  - Notes:
    - Aggregates cultural heritage records from thousands of institutions.
    - Rights and media availability vary by record/provider.
    - EDM is central data model.
    - Need duplicate handling if direct museum APIs are also ingested.

- Digital Public Library of America
  - Link:
    - https://pro.dp.la/developers/api-codex
  - Programmatic access:
    - REST API at https://api.dp.la/v2
    - Bulk download also exists.
  - Auth:
    - API key required as api_key.
  - Resources:
    - items
    - collections
  - Notes:
    - JSON-LD aggregator.
    - Rights/media vary by provider.
    - Duplicate risk with direct museum APIs.

- Library of Congress
  - Links:
    - https://www.loc.gov/apis/json-and-yaml/
    - https://www.loc.gov/apis/
  - Programmatic access:
    - JSON/YAML API over loc.gov search and collection pages.
  - Auth:
    - No API key required.
  - Notes:
    - Structured data for loc.gov collections: items, collections, images, metadata.
    - Not a full catalog-record API unless digitized.
    - Deep paging past 100,000 not supported; use facets.
    - Rate limits enforced.

- Cooper Hewitt Collection API
  - Links:
    - https://collection.cooperhewitt.org/api/
    - https://collection.cooperhewitt.org/
  - Programmatic access:
    - REST-style API at https://api.collection.cooperhewitt.org/rest/
  - Auth:
    - API docs describe access tokens, API keys, OAuth.
  - Notes:
    - Cooper Hewitt is also available through Smithsonian Open Access unit CHNDM.
    - Need duplicate/source identity handling if both are used.

- Wellcome Collection
  - Links:
    - https://developers.wellcomecollection.org/
    - https://developers.wellcomecollection.org/api
    - https://developers.wellcomecollection.org/iiif
  - Programmatic access:
    - Catalogue API.
    - IIIF APIs.
  - Auth:
    - No standard key observed for basic catalogue docs.
  - Notes:
    - Not artwork-only; includes visual culture, books, journals, archives, manuscripts, objects.
    - Rights/license filtering important.

- Wikimedia Commons and Wikidata
  - Links:
    - https://www.mediawiki.org/wiki/Wikimedia_APIs
    - https://www.wikidata.org/wiki/Wikidata:Data_access
    - https://query.wikidata.org/
    - https://commons.wikimedia.org/w/api.php?action=help
  - Programmatic access:
    - MediaWiki Action API.
    - MediaWiki REST API.
    - Wikidata REST API.
    - Wikidata Query Service SPARQL.
    - Dumps.
    - Linked Data interface.
  - Auth:
    - Public read access generally does not require an API key.
  - Notes:
    - Wikidata data is CC0.
    - Commons media licenses vary by file.
    - Useful for enrichment, identifiers, creator metadata, public media links.
    - Use descriptive User-Agent; handle 429 and Retry-After.

Additional sources found after the initial docs, not yet fully folded into the catalog:

- National Gallery of Art Open Data
  - Links:
    - https://github.com/NationalGalleryOfArt/opendata
    - https://www.nga.gov/open-access-images.html redirects to https://www.nga.gov/artworks/free-images-and-open-access
  - Programmatic access:
    - GitHub CSV dataset.
  - Auth:
    - No authorization needed for dataset download.
  - Notes found:
    - Dataset is under CC0.
    - Records cover 130,000+ artworks and artists.
    - Published in CSV with UTF-8.
    - Data dictionary exists in repo.
    - Images/media files are not included, though links/references to images are present.
    - Dataset updated frequently, usually once a day.
    - Includes Wikidata identifiers.

- Museum of Modern Art Collection
  - Link:
    - https://github.com/MuseumofModernArt/collection
  - Programmatic access:
    - GitHub CSV and JSON datasets.
  - Auth:
    - No API key for GitHub dataset.
  - Notes found:
    - CC0 dataset.
    - MoMA website has 107,903 artworks from 28,369 artists.
    - Research dataset contains 160,597 artwork records.
    - Artists dataset contains 15,927 records.
    - Fields include title, artist, date made, medium, dimensions, date acquired, artist nationality/gender/birth/death/Wikidata QID/Getty ULAN.
    - Images are not included.
    - Latest release observed: v2026-06-30.
    - Regular updates planned.

- Tate Collection
  - Link:
    - https://github.com/tategallery/collection
  - Programmatic access:
    - GitHub JSON and CSV dataset.
  - Auth:
    - No API key for GitHub dataset.
  - Notes found:
    - CC0 metadata.
    - Around 70,000 artworks and 3,500 associated artists.
    - JSON organized by folders; CSV has artist_data.csv and artwork_data.csv.
    - Images are not included and not part of dataset.
    - Important caveat: repository is no longer actively maintained; last updated October 2014.
    - Useful for historical/stale data or model-shape examples, not current ingestion unless staleness is acceptable.

- Minneapolis Institute of Art
  - Link:
    - https://github.com/artsmia/collection
  - Programmatic access:
    - GitHub JSON metadata repository.
    - Image thumbnail endpoints by object ID.
  - Auth:
    - No API key for GitHub dataset.
  - Notes found:
    - CC0 metadata.
    - Objects live at objects/$bucket/$id.json where bucket is object id / 1000.
    - Fields observed in sample include accession_number, artist, continent, country, creditline, culture, dated, description, dimension, id, image, image_copyright, image_height, image_width, life_date, medium, nationality, provenance, restricted, role, room, style, text, title.
    - Image field valid|invalid.
    - Restricted field 0|1.
    - Thumbnails available at http://api.artsmia.org/images/$id/{small,medium,large}.jpg.
    - Small 100px, medium 600px, large 800px.
    - Records updated and added; changes committed approximately once per day.
    - Image rights are not the same as metadata rights.

- Paris Musées API
  - Link:
    - https://apicollections.parismusees.paris.fr/
  - Programmatic access:
    - JSON/API access; GraphQL explorer mentioned.
  - Auth:
    - Account creation required.
    - Authentication token required for requests.
  - Notes found:
    - API lets third parties retrieve part of Paris Musées collection data as JSON.
    - Paris Musées covers 14 City of Paris museums.
    - Portal has more than 280,000 object notices/resources/archives.
    - Goal includes open data and reuse for digital projects.
    - Documentation link on site points to API documentation.
    - Need inspect GraphQL docs and endpoint details further.

- DigitalNZ
  - Links:
    - https://digitalnz.org/developers
    - https://digitalnz.org/developers/api-docs-v3
  - Programmatic access:
    - API v3.
    - Search records endpoint.
    - Get metadata endpoint.
  - Auth:
    - API no longer requires a key for public content.
    - API key encouraged for regular/high-volume/application usage.
    - API key header: Authentication-Token.
    - Unauthenticated requests have a shared max rate limit.
  - Notes:
    - Aggregator for New Zealand-related digital items from cultural/government/education/science/community groups.
    - Metadata API returns pointers to items and thumbnail images; DigitalNZ does not hold copies of collection items.
    - OpenAPI spec on SwaggerHub linked from docs.
    - Good aggregator candidate; rights vary by partner.

- Trove API
  - Link:
    - https://trove.nla.gov.au/about/create-something/using-api
  - Programmatic access:
    - Trove API v3.
    - Bulk download also linked in footer/navigation.
  - Auth:
    - Active API key required for ongoing use.
    - User needs Trove account and API key application.
  - Notes found:
    - API supports complex search queries and machine-readable results.
    - Categories include images, maps, artefacts, and more.
    - Application asks for desired call rate and intended use.
    - Review tiers mention AI modelling/machine learning and training generative AI as higher-review/exemption-related uses.
    - Version 2 discontinued September 2024.
    - Need review API v3 technical guide for endpoint details.

- Statens Museum for Kunst / SMK
  - Link:
    - https://api.smk.dk/api/v1/docs/
  - Programmatic access:
    - Swagger UI exists for API docs.
  - Auth:
    - Not verified in detail.
  - Notes found:
    - Search result/background indicates SMK Open has public-domain and open collection access.
    - Need inspect Swagger/OpenAPI directly to capture endpoints, auth, rate limits, data fields, image model.

- Getty Museum Collection API
  - Link:
    - https://data.getty.edu/museum/collection/
  - Programmatic access:
    - Official Getty API Documentation page observed.
    - Page is JS-heavy and did not expose detail through text browser.
  - Auth:
    - Not verified.
  - Notes:
    - Need inspect browser/JS/OpenAPI/network if possible.
    - Likely Linked Art/linked-data shape, but do not assume without verification.

Candidate/verify sources mentioned or lightly found but not yet enough to document as high-confidence ingest sources:

- British Museum collection API/open data.
- National Portrait Gallery London.
- Los Angeles County Museum of Art.
- Dallas Museum of Art.
- Walters Art Museum.
- Yale Center for British Art.
- Yale University Art Gallery.
- Auckland Museum.
- Te Papa.
- Powerhouse Museum.
- National Gallery of Victoria.
- Finnish National Gallery.
- DigitaltMuseum / DIMU.
- Amsterdam or other municipal cultural APIs.
- Other IIIF registries and national aggregators.

Only promote these to catalog entries after verifying official current documentation for open access plus programmatic retrieval.

Local repo files to review before making any changes:

- /Users/daniel/dev/artwork-db/AGENTS.md if present, plus the user-provided AGENTS instructions in context.
- /Users/daniel/dev/artwork-db/CODE_STANDARDS.md
- /Users/daniel/dev/artwork-db/docs/smithsonian_open_access_implementation_notes.md
- /Users/daniel/dev/artwork-db/docs/open_access_artwork_api_catalog.md
- /Users/daniel/dev/artwork-db/extraction/met/README.md
- /Users/daniel/dev/artwork-db/extraction/met/config.py
- /Users/daniel/dev/artwork-db/extraction/met/run.py
- /Users/daniel/dev/artwork-db/extraction/met/snapshot_loader.py
- /Users/daniel/dev/artwork-db/extraction/met/control_seeder.py
- /Users/daniel/dev/artwork-db/extraction/met/control_enricher.py
- /Users/daniel/dev/artwork-db/extraction/met/image_enricher.py
- /Users/daniel/dev/artwork-db/extraction/met/sql/
- /Users/daniel/dev/artwork-db/extraction/met/tests/test_throttle_gate.py
- /Users/daniel/dev/artwork-db/extraction/aic/README.md
- /Users/daniel/dev/artwork-db/extraction/aic/config.py
- /Users/daniel/dev/artwork-db/extraction/aic/loader.py
- /Users/daniel/dev/artwork-db/extraction/aic/run.py
- /Users/daniel/dev/artwork-db/extraction/aic/sql/
- /Users/daniel/dev/artwork-db/extraction/cma/run.py
- /Users/daniel/dev/artwork-db/infrastructure/create_bronze_tables.sql
- /Users/daniel/dev/artwork-db/Makefile
- /Users/daniel/dev/artwork-db/env.template if present, noting it was untracked in the previous context
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/ADDING_A_SOURCE.md
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/SCHEMA.md
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/framework.yaml
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/model.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/spec.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/enums.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/loader.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/policies.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/factories/assets.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/factories/checks.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/factories/jobs.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/factories/schedules.py
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/sources/met.yaml
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/sources/aic.yaml
- /Users/daniel/dev/artwork-db/orchestration/artwork_orchestration/sources/cma.yaml
- dbt model directories if present. The prior context expected transform/dbt/models/staging/met, transform/dbt/models/staging/aic, and transform/dbt/models/marts, but a later rg said transform/dbt/models did not exist in that working tree. Verify current paths with rg --files.

Local patterns already found:

- Met extractor pattern:
  - Hybrid CSV snapshot plus API image enrichment.
  - snapshot loads MetObjects.csv into MET_CSV_SNAPSHOT.
  - seed-control builds MET_ENRICHMENT_CONTROL.
  - enrich-met leases worklist rows, calls API, stages image blocks, assembles RAW_MET_OBJECTS.
  - Rate-limited, resumable, batch-bounded.
  - Handles 403 and 429 as throttle signals.
  - Uses adaptive RateLimiter and ThrottleGate.
  - Good model for sources requiring API enrichment after cheap bulk snapshot.

- AIC extractor pattern:
  - Public dump-first snapshot.
  - Downloads tar.bz2, extracts selected entities, transforms to gzipped NDJSON, PUT/COPY/MERGE into Bronze.
  - Produces RAW_AIC_ARTWORKS and RAW_AIC_AGENTS.
  - Soft-deletes stale/deaccessioned artworks.
  - Good model for sources with complete public data dump.

- Orchestration pattern:
  - YAML-driven and source-decoupled.
  - Adding a source should be one source YAML plus extractor/dbt/DDL work, with zero source-specific branches in framework Python.
  - sources/met.yaml shows multi-step, batched, rate-limited source.
  - sources/aic.yaml shows single-step, multi-output snapshot.
  - factories consume generic typed config.
  - rate_limited true injects per-worker RPS env and tags.
  - batched mode appends --batch-size and --max-batches.
  - produces maps extraction outputs to physical Bronze tables and dbt source names.

- Bronze/dbt pattern:
  - Bronze stores raw_payload VARIANT plus source/batch metadata.
  - Natural source key identifies each row.
  - Typing and normalization are deferred to dbt staging.
  - Images often become long image staging tables.
  - Gold marts union source-specific staging CTEs.
  - Existing Smithsonian DDL table is RAW_SMITHSONIAN_OBJECTS with object_id, raw_payload, _extracted_at, _source_system, _batch_id.

Common functionality opportunities found so far:

There are roughly 35-40 reusable opportunities across API clients, data-dump loaders, models, and orchestration methods. The highest-leverage 12-15 are obvious now. Do not immediately implement these; document and assess them against the repo’s source-decoupled design.

12-15 obvious high-leverage abstractions:

1. HTTP client base
   - Shared session creation, timeouts, User-Agent/contact header, JSON decoding, status handling, retry hooks.

2. Authentication strategies
   - No auth, query-parameter API key, header API key, bearer/token, Basic auth, GraphQL token.

3. Rate-limit handling
   - 429, Retry-After, provider-specific 403 throttles, exponential/linear backoff, throttle counters.

4. Pagination strategies
   - Offset/limit, page/limit, cursor/pageToken, OAI-PMH resumption token, search-after style, shard iteration.

5. Bulk download helpers
   - S3 public bucket, HTTPS large files, GitHub/raw files, tar/zip extraction, checksum/cache/resume behavior.

6. NDJSON chunk writer
   - Gzipped chunks, stable batch IDs, temp directory lifecycle, row counts, source key extraction.

7. Snowflake raw loader
   - PUT/COPY/MERGE pattern, temp staging tables, target table abstraction, row counts, purge behavior.

8. Extraction logging
   - Start/finish/error rows, batch metadata, records loaded, elapsed time, error truncation.

9. Raw record model
   - Source, entity_type, natural_key, raw_payload, batch_id, extracted_at, source_system.

10. Watermark/change model
   - updated_since, metadata date, content hash/signature, dump version, last seen batch, stale detection.

11. Worklist/leasing model
   - Generic API enrichment control table behavior: seed, claim, lease TTL, callback, retry, release unfinished.

12. Rights/media classifier
   - CC0/public-domain/open metadata/restricted media distinctions; media rights separate from metadata rights.

13. IIIF/media helpers
   - Manifest URL, image service URL, derivative URL, thumbnail URL, dimensions, provider-specific delivery services.

14. CLI contract
   - Common subcommands such as snapshot, status, seed-control, enrich, enrich-next-batch; common flags like --limit, --batch-size, --max-batches, --partition.

15. Test harness
   - Fake paginated API, fake bulk archive, fake S3/GitHub fixture, Snowflake SQL assertion fixtures, throttling tests.

Additional reusable opportunities to consider, bringing total toward 35-40:

16. Provider capability model
   - has_bulk_dump, has_api_delta, has_iiif, has_agents, has_media_records, has_rights_filter.

17. Source configuration dataclasses for extractor packages
   - Environment parsing, required secrets, defaults, validation errors.

18. Common downloader cache
   - Reuse already-downloaded archives, TTLs, content length validation, temp cleanup.

19. Archive readers
   - tar.bz2, zip, gzip, plain CSV, JSON array, JSON lines.

20. CSV-to-raw-payload mapper
   - Header normalization, null coercion, raw string preservation, optional schema hints.

21. JSON array streaming reader
   - For large JSON files without loading whole file into memory.

22. JSONL shard reader
   - Useful for Smithsonian, Mia-style data, and many dump sources.

23. GitHub release/dataset fetcher
   - Raw file download, latest release detection, repo snapshot retrieval.

24. S3 public bucket lister
   - No-sign-request listing, HTTPS index reading, shard enumeration.

25. Metadata SQL snippets
   - Row count, latest extraction, pending worklist count, stale row count.

26. Generic nonempty/freshness checks
   - Already partly in orchestration; document extension opportunities.

27. Generic soft-delete/stale-record handler
   - Dump-based sources that need _is_deleted and _last_seen_batch_id.

28. Entity mapping conventions
   - artworks, agents/artists, images/media, exhibitions, departments, terms/vocabularies.

29. Error taxonomy
   - Network, timeout, rate limit, decode, validation, missing key, forbidden, unavailable media.

30. Retry policy config bridge
   - Align extractor HTTP retries with orchestration retry policy, without hardcoding per source.

31. Structured provider documentation template
   - Scope, license, auth, endpoints, pagination, media, rights, update strategy, local mapping questions.

32. dbt staging conventions
   - Raw VARIANT field extraction, source-specific staging, long image table, rights mapping.

33. dbt source generation or documentation checks
   - Ensure YAML produces tables line up with dbt source names.

34. Secret/env var registry
   - Source key to env vars, docs, validation, missing-secret messaging.

35. Partition discovery helpers
   - Departments, units, categories, terms endpoints, static vs discovered partitions.

36. Incremental planning helpers
   - Decide whether a source supports full snapshot, delta by updated_since, or only full reload.

37. Media URL validation/enrichment utilities
   - Optional HEAD/GET checks, content type, dimensions, not for initial design unless needed.

38. Aggregator duplicate/reconciliation helpers
   - Europeana/DPLA/DigitalNZ/Trove vs direct museum source overlap.

39. External identifier handling
   - Wikidata QID, ULAN, VIAF, accession number, source URL, IIIF IDs.

40. Source-agnostic fixture generator
   - Small realistic raw payloads for tests and dbt staging development.

Boundary guidance from the prior context:

- Commonize transport, batching, staging, logging, and orchestration mechanics.
- Be cautious about commonizing museum semantics too early.
- Terms like artist, agent, constituent, maker, sitter, culture, department, rights, and media vary materially across providers.
- Preserve source-specific raw payloads in Bronze and normalize later in staging/marts.
- Do not put museum names, table names, or source-specific branches into orchestration framework Python.
- The repo grep gate for framework Python must remain zero for source-specific museum literals:
  \b(met|aic|cma)\b|metropolitan|art institute|chicago|cleveland

Requested next-context work:

1. Read the two Markdown files already created.
2. Review the local repo files listed above.
3. Continue a more exhaustive search for open-access artwork/cultural collection data sources with programmatic retrieval.
4. Expand the catalog with verified sources only.
5. Clearly separate:
   - true APIs,
   - authenticated APIs,
   - unauthenticated APIs,
   - data dumps,
   - GitHub datasets,
   - S3/public object storage,
   - IIIF-only or media endpoints,
   - aggregators,
   - stale datasets,
   - candidate sources needing verification.
6. For each source, capture:
   - official links,
   - access mode,
   - auth/key requirements,
   - rate limits if documented,
   - pagination or bulk layout,
   - update frequency,
   - license/reuse status,
   - media/image rights distinction,
   - entity shapes if available,
   - endpoint examples or file paths,
   - downstream implementation considerations,
   - open questions.
7. Do not make design decisions. Provide facts and implementation questions.
8. If editing docs, use apply_patch, keep Markdown, and avoid unrelated code changes.