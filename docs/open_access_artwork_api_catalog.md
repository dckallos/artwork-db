# Public Open Access Artwork API Catalog

Verified on 2026-07-04.

This catalog summarizes public APIs, bulk datasets, and documentation sources that are
relevant to open access artwork or museum collection ingestion. It is intended for AI and
human implementers. It does not choose an implementation design for this repository.

## How To Use This Catalog

For each provider, inspect:

- Whether API key authentication is required.
- Whether bulk data exists and is preferred for full snapshots.
- Whether media rights differ from metadata rights.
- Whether images use IIIF or provider-specific delivery URLs.
- Whether pagination is offset-based, cursor-based, token-based, or dump-based.
- Whether rate limits are documented.
- Whether records include stable IDs and update timestamps.
- Whether object, person/agent, and image data are separate resources or embedded payloads.

## Smithsonian Institution Open Access

Primary links:

- [AWS Registry entry](https://registry.opendata.aws/smithsonian-open-access/)
- [Smithsonian Dev Tools](https://www.si.edu/openaccess/devtools)
- [EDAN API docs](https://edan.si.edu/openaccess/apidocs/)
- [EDAN docs](https://edan.si.edu/openaccess/docs/)
- [EDAN data model notes](https://edan.si.edu/openaccess/docs/more.html)
- [S3 metadata index](https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/index.txt)
- [OpenAccess GitHub repository](https://github.com/Smithsonian/OpenAccess)

Access modes:

- Public S3 bucket: `s3://smithsonian-open-access/`
- HTTPS S3 object access.
- EDAN API through `https://api.si.edu/openaccess`.

Authentication:

- S3 bulk data can be read without AWS credentials.
- API access requires an api.data.gov API key.

Documented or observed API endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1.0/search` | Search EDAN records. |
| `GET /api/v1.0/category/:cat/search` | Search within `art_design`, `history_culture`, or `science_technology`. |
| `GET /api/v1.0/content/:id` | Fetch one record by row ID or URL. |
| `GET /api/v1.0/terms/:category` | Discover terms for unit, topic, object type, media type, and related categories. |
| `GET /api/v1.0/stats` | Fetch CC0 object and media statistics. |

Important API parameters:

- `q`: required query string for search endpoints.
- `start`: offset, default `0`.
- `rows`: result count, documented up to `1000`.
- `sort`: values include `id`, `newest`, `updated`, and `random`.
- `type`: values include `edanmdm`, `ead_collection`, `ead_component`, and `all`.
- `row_group`: values include `objects` and `archives`.
- `api_key`: api.data.gov key when not sent by header.

Bulk data notes:

- Metadata is organized by Smithsonian unit.
- Unit shard indexes have files such as `00.txt` through `ff.txt`.
- Shards contain line-delimited JSON.
- Records include fields such as `id`, `unitCode`, `type`, `content`, `hash`,
  `docSignature`, `timestamp`, and `lastTimeUpdated`.

Media notes:

- Online media is commonly embedded under
  `content.descriptiveNonRepeating.online_media.media`.
- Smithsonian image delivery URLs often use `https://ids.si.edu/ids/deliveryService`.
- Download resource URLs often use `https://ids.si.edu/ids/download`.
- Media usage can be per-media, while metadata usage can appear separately.

Rate limit notes:

- API access uses api.data.gov.
- api.data.gov documents a default limit of 1,000 requests per hour per key.
- `DEMO_KEY` is much more limited.
- Implementation needs to inspect rate-limit headers and 429 responses.

Implementation research questions:

- S3 bulk or EDAN API as primary source.
- Full Smithsonian scope or selected art/design units.
- Treatment of archive record types.
- Natural-key choice among EDAN `id`, `url`, unit `record_ID`, and `guid`.
- Handling of records without media.
- Mapping of Smithsonian units into downstream conformed museum dimensions.

## The Metropolitan Museum Of Art Collection API

Primary links:

- [Met Collection API documentation](https://metmuseum.github.io/)
- [Met Open Access CSV repository](https://github.com/metmuseum/openaccess)
- [Met Open Access policy](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access)

Access modes:

- REST API at `https://collectionapi.metmuseum.org/public/collection/v1`.
- Public CSV dataset through GitHub.

Authentication:

- No API key required.

Documented endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /objects` | List object IDs. |
| `GET /objects/{objectID}` | Fetch one object. |
| `GET /departments` | List departments. |
| `GET /search` | Search object IDs with filters. |

Important API parameters:

- `metadataDate` on `/objects`.
- `departmentIds` on `/objects`.
- `q` on `/search`.
- `isHighlight`, `title`, `tags`, `departmentId`, `isOnView`, `artistOrCulture`,
  `medium`, `hasImages`, `geoLocation`, `dateBegin`, and `dateEnd` on `/search`.

Rate limit notes:

- The Met docs ask clients to limit requests to 80 requests per second.
- Local repository code treats 403 and 429 as throttle signals.

Media notes:

- Object payloads include `primaryImage`, `primaryImageSmall`, and `additionalImages`.
- Public domain status is exposed on object records.

Local repository relevance:

- The current Met extractor loads the CSV snapshot first, then enriches image fields through
  the object API.
- This is the main local example of a bounded, resumable, rate-limited API enrichment flow.

## Art Institute Of Chicago API

Primary links:

- [AIC API documentation](https://api.artic.edu/docs/)
- [AIC image licensing and IIIF docs](https://api.artic.edu/docs/#images)
- [AIC data dumps documentation](https://api.artic.edu/docs/#data-dumps)

Access modes:

- REST API at `https://api.artic.edu/api/v1`.
- Public data dumps at `https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2`.
- IIIF image service at `https://www.artic.edu/iiif/2`.

Authentication:

- No API key required.

Documented API behavior:

- JSON responses.
- Pagination uses `page` and `limit`.
- `limit` maximum is documented as 100.
- Deep pagination is capped at 10,000 records.
- The docs recommend selecting only needed fields with the `fields` parameter.

Rate limit notes:

- Anonymous users are throttled to 60 requests per minute.
- The docs ask high-volume users to scrape no more than one request per second, single
  threaded.
- The docs request an `AIC-User-Agent` header with contact information.

Bulk data notes:

- Dumps are updated nightly.
- Dumps contain the same schema as the API.
- Dumps are recommended for full snapshots, archival use, analysis, and more than 10,000
  records.

Media notes:

- Artworks expose image identifiers.
- Image URLs are constructed with IIIF, for example:

```text
https://www.artic.edu/iiif/2/<identifier>/full/843,/0/default.jpg
```

Local repository relevance:

- The current AIC extractor uses the dump, not a full API crawl.
- This is the main local example of a one-step bulk snapshot that produces multiple raw
  tables.

## Cleveland Museum Of Art Open Access API

Primary links:

- [CMA Open Access API](https://openaccess-api.clevelandart.org/)
- [CMA GitHub Open Access repository](https://github.com/ClevelandMuseumArt/openaccess)

Access modes:

- REST API at `https://openaccess-api.clevelandart.org/api`.
- GitHub data repository.

Authentication:

- No API key is indicated in the public docs.

Documented endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/artworks/` | Search and list artworks. |
| `GET /api/artworks/{id}` | Fetch one artwork by Athena ID or accession number. |

Important API parameters on artwork search:

- `q`
- `cc0`
- `copyrighted`
- `department`
- `type`
- `orderby`
- `has_image`
- `skip`
- `limit`
- `updated_since`
- `fields`
- date and accession-related filters documented by CMA.

Pagination notes:

- `skip` and `limit` are used.
- The documented default and maximum limit is 1000.

Data and media notes:

- CMA describes more than 64,000 artwork records and images for more than 37,000 works.
- Metadata is CC0.
- Image availability depends on image rights.
- Image URLs can appear under `images.web`, `images.print`, and `images.full`.
- The docs distinguish records with copyrighted images from public-domain image access.

Update notes:

- CMA says API and GitHub data are updated daily.
- The docs include filters for updated records and recently added Open Access records.

Implementation research questions:

- Whether to use API, GitHub bulk data, or both.
- How to represent copyrighted image records versus CC0 image records.
- Whether `updated_since` is sufficient for incremental sync.

## Harvard Art Museums API

Primary links:

- [Harvard Art Museums API docs](https://github.com/harvardartmuseums/api-docs)
- [Harvard API key request](https://harvardartmuseums.org/collections/api)

Access mode:

- REST API at `https://api.harvardartmuseums.org`.

Authentication:

- API key required.
- The key is passed as the `apikey` query parameter.

Response shape:

- JSON responses commonly include `info`, `records`, and `aggregations`.
- Pagination metadata includes page counts and next/previous links.

Important resources:

- `Object`
- `Person`
- `Exhibition`
- `Gallery`
- `Image`
- Other vocabulary and authority resources documented in the repo.

Pagination notes:

- Default page size is 10.
- Maximum documented page size is 100.
- Page-based pagination is used.

Update notes:

- The docs describe a daily refresh schedule.

Media notes:

- Image records can include `baseimageurl` and `primaryimageurl`.
- The docs indicate that restricted image URLs may not be exposed to most users.
- IIIF-style image derivation is supported through image base URLs.

Implementation research questions:

- How API key management works.
- Whether object records or image records drive media extraction.
- How restricted image omissions are represented.

## Victoria And Albert Museum APIs

Primary links:

- [V&A developer portal](https://developers.vam.ac.uk/)
- [V&A API guide](https://developers.vam.ac.uk/guide/v2/welcome.html)
- [V&A collections site](https://collections.vam.ac.uk/)

Access modes:

- Public collection APIs documented by the developer portal.
- JSON and CSV formats.
- IIIF image access.

Authentication:

- No API key requirement was visible in the inspected public guide.

Data scope:

- The portal describes over one million collection records.
- The portal describes more than 500,000 images.

Implementation-relevant docs sections:

- Search
- Filters
- Results
- Restrictions
- Images
- IIIF image access

Bulk notes:

- The V&A guide says a compressed export can be more efficient than repeated API calls for
  bulk use, and points users toward contacting the maintainers or filing an issue.

Implementation research questions:

- Whether a current official bulk export is available for the desired records.
- How restrictions and image rights are encoded.
- Whether CSV format is suitable for Bronze storage or whether JSON API records are needed.

## Rijksmuseum Data Services

Primary links:

- [Rijksmuseum Data Services](https://data.rijksmuseum.nl/)
- [Rijksmuseum API and download docs](https://data.rijksmuseum.nl/docs/)
- [Rijksmuseum Search API docs](https://data.rijksmuseum.nl/docs/search)

Access modes:

- Search API.
- OAI-PMH API.
- LDES API.
- Downloads.
- Persistent identifier resolver.

Authentication:

- The current Data Services Search API docs do not indicate an API key requirement.

Data scope:

- The portal describes metadata for about 800,000 objects.
- The portal describes high-resolution photographs for about 600,000 objects.

Search endpoint:

```text
GET https://data.rijksmuseum.nl/search/collection
```

Important Search API parameters:

- `aboutActor`
- `creator`
- `creationDate`
- `description`
- `imageAvailable`
- `material`
- `memberOfSetId`
- `objectNumber`
- `pageToken`
- `technique`
- `title`
- `type`

Pagination notes:

- Responses use the Linked Art Search model.
- Each page contains up to 100 results.
- The next page URL appears in `next.id`.
- The docs say all pages can be retrieved in theory.

Data model notes:

- Rijksmuseum references Europeana Data Model and Linked Art.
- Search results contain references to object URLs and LOD identifiers.

Implementation research questions:

- Which access mode is best for full snapshots.
- Whether Linked Art JSON is preserved directly in Bronze.
- How IIIF or high-resolution image URLs are represented for selected objects.

## Europeana APIs

Primary links:

- [Europeana APIs overview](https://pro.europeana.eu/discover-the-data/apis)
- [Europeana Search API](https://pro.europeana.eu/page/search)
- [Europeana Record API](https://pro.europeana.eu/page/record)
- [Europeana IIIF API](https://pro.europeana.eu/page/iiif)
- [Europeana Dataset Download and OAI-PMH](https://pro.europeana.eu/page/intro)

Access modes:

- Search API.
- Record API.
- Entity API.
- Annotations API.
- IIIF API.
- SPARQL endpoint.
- Dataset Download.
- OAI-PMH.
- Thumbnail API.

Authentication:

- API key required for core API access.

Data scope:

- Europeana aggregates cultural heritage records from thousands of institutions.
- Rights and media availability vary by record and provider.

Implementation-relevant behavior:

- Search API finds metadata and media across providers.
- Record API fetches one full metadata record.
- EDM is the central data model.
- Provider attribution and rights statements are essential fields.

Implementation research questions:

- Whether Europeana is a primary source or enrichment/aggregation source.
- How to avoid duplicating records already ingested from original institutions.
- How rights statements are filtered.
- Whether Dataset Download or OAI-PMH is better than API pagination for large loads.

## Digital Public Library Of America API

Primary links:

- [DPLA API Codex](https://pro.dp.la/developers/api-codex)
- [DPLA API policies](https://pro.dp.la/developers/policies)

Access mode:

- REST API at `https://api.dp.la/v2`.

Authentication:

- API key required.
- The documented key parameter is `api_key`.

Resources:

- `items`
- `collections`

Data model notes:

- Responses are JSON-LD.
- DPLA aggregates records from many contributing institutions.
- Rights and media access vary by source provider.

Implementation research questions:

- Whether DPLA is used as a primary source or aggregator.
- How to manage duplicate records across DPLA and direct museum APIs.
- How to filter by rights and provider.
- Whether bulk download is preferable to API extraction.

## Library Of Congress JSON/YAML API

Primary links:

- [LOC JSON and YAML API](https://www.loc.gov/apis/json-and-yaml/)
- [LOC API basics](https://www.loc.gov/apis/)

Access modes:

- JSON API over loc.gov search and collection pages.
- YAML output also supported.

Authentication:

- No API key required.

Data scope:

- The API exposes structured data for loc.gov collections.
- The docs distinguish this from complete catalog-record access.
- Useful resources include items, collections, images, and metadata.

Pagination notes:

- Deep paging past 100,000 records is not supported.
- The docs recommend facets for narrowing large result sets.

Rate limit notes:

- LOC says rate limits are enforced.

Implementation research questions:

- Whether the desired scope is visual artwork, photographs, prints, posters, or broader
  cultural objects.
- How to handle non-art collection materials.
- How rights statements and image URLs are filtered.

## Cooper Hewitt Collection API

Primary links:

- [Cooper Hewitt Collection API](https://collection.cooperhewitt.org/api/)
- [Cooper Hewitt collection site](https://collection.cooperhewitt.org/)

Access mode:

- REST-style API at `https://api.collection.cooperhewitt.org/rest/`.

Authentication:

- The API docs describe access tokens, API keys, and OAuth.

Data scope:

- Cooper Hewitt is also represented in Smithsonian Open Access under unit code `CHNDM`.
- The separate Cooper Hewitt API may expose museum-specific methods and shapes.

Implementation research questions:

- Whether to use Smithsonian Open Access `CHNDM` records, Cooper Hewitt's own API, or both.
- Whether separate APIs produce duplicate or richer records.
- How source identity is represented if the same institution is available through
  multiple endpoints.

## Wellcome Collection APIs

Primary links:

- [Wellcome Collection developer docs](https://developers.wellcomecollection.org/)
- [Wellcome Collection API docs](https://developers.wellcomecollection.org/api)
- [Wellcome Collection IIIF docs](https://developers.wellcomecollection.org/iiif)

Access modes:

- Catalogue API.
- IIIF APIs.

Authentication:

- Public docs do not indicate a standard API key requirement for basic catalogue access.

Data scope:

- Visual culture, books, journals, archives, manuscripts, objects, and other collection
  material.
- Not artwork-only, but relevant to public-domain and open cultural heritage extraction.

Implementation research questions:

- Whether scope includes medical history and archival objects.
- How rights and license fields are filtered.
- Whether IIIF manifests or catalogue records are the primary media source.

## Wikimedia Commons And Wikidata

Primary links:

- [Wikimedia APIs overview](https://www.mediawiki.org/wiki/Wikimedia_APIs)
- [Wikidata data access](https://www.wikidata.org/wiki/Wikidata:Data_access)
- [Wikidata Query Service](https://query.wikidata.org/)
- [Wikimedia Commons API help](https://commons.wikimedia.org/w/api.php?action=help)

Access modes:

- MediaWiki Action API.
- MediaWiki REST API.
- Wikidata REST API.
- Wikidata Query Service SPARQL.
- Dumps.
- Linked Data interface.

Authentication:

- Public read access generally does not require an API key.
- Auth is needed for user-specific or write operations.

Data and rights notes:

- Wikidata data is CC0.
- Wikimedia Commons media licenses vary by file.
- Wikimedia records can be useful for enrichment, identifiers, creator metadata, and public
  media links.

Rate and usage notes:

- Wikimedia asks clients to use a descriptive User-Agent.
- Implementations need to handle 429 and `Retry-After`.
- Large queries and bulk extraction need dumps or appropriate batch mechanisms.

Implementation research questions:

- Whether Wikimedia is an enrichment source or a primary artwork/media source.
- How to filter Commons files by license.
- How to reconcile external IDs with museum source records.

## IIIF As A Cross-Provider Theme

Many museum APIs expose image media through IIIF or IIIF-like image services.

Providers in this catalog with explicit IIIF relevance:

- AIC
- V&A
- Rijksmuseum
- Europeana
- Wellcome
- Harvard Art Museums
- Smithsonian, through Smithsonian image delivery URLs and downloadable media resources, even
  though the observed EDAN payloads use Smithsonian IDS URLs rather than a simple IIIF
  pattern in the sampled records.

Implementation-relevant questions:

- Whether to preserve provider image URLs exactly.
- Whether to normalize image derivatives in dbt.
- Whether to store IIIF manifest URLs, image service URLs, or rendered image URLs.
- Whether to generate thumbnail and display URLs downstream from stable image IDs.

## Common Extraction Considerations Across Providers

These are considerations for later design, not decisions.

### Authentication

| Provider | Key required? |
| --- | --- |
| Smithsonian API | Yes, via api.data.gov. |
| Smithsonian S3 | No AWS credentials required for public reads. |
| Met | No. |
| AIC | No. |
| CMA | No key indicated in public docs. |
| Harvard | Yes. |
| V&A | No key observed in inspected docs. |
| Rijksmuseum Data Services Search API | No key observed in inspected current docs. |
| Europeana | Yes. |
| DPLA | Yes. |
| LOC | No. |
| Cooper Hewitt | API key or OAuth-style access described. |
| Wellcome | No standard key observed for basic catalogue docs. |
| Wikimedia/Wikidata | No key for public read APIs. |

### Bulk Data Versus API Crawling

Providers with documented bulk or dump access:

- Smithsonian S3 Open Access bucket.
- Met Open Access CSV.
- AIC nightly dump.
- CMA GitHub Open Access data.
- Rijksmuseum downloads and OAI-PMH/LDES options.
- Europeana Dataset Download and OAI-PMH.
- DPLA bulk download.
- Wikimedia/Wikidata dumps.

API crawling may be most useful for:

- Small scopes.
- Targeted enrichment.
- Search-driven discovery.
- Delta checks where the API exposes updated filters.

Bulk data may be most useful for:

- Full snapshots.
- Reproducibility.
- Large record counts.
- Avoiding deep pagination caps.
- Avoiding API rate pressure.

### Rights And Media

Common rights fields or concepts:

- Public-domain flags.
- CC0 metadata flags.
- Per-image rights.
- Provider-specific image availability fields.
- Rights statements from aggregators.
- Restrictions or takedown fields.

Important distinction:

- A record can have open metadata but restricted media.
- A media URL can exist without reuse rights that match the metadata.
- Aggregators can expose provider-supplied rights that need separate interpretation.

### Pagination And Incremental Updates

Common pagination styles:

- Offset and limit: Smithsonian, CMA, many classic REST APIs.
- Page and limit: AIC, Harvard.
- Cursor or token: Rijksmuseum Search API `pageToken`.
- Shards or dumps: Smithsonian S3, AIC dump, Met CSV, bulk providers.

Common update signals:

- Updated timestamp fields.
- API `updated_since` filters.
- Sort by updated time.
- Record signatures or hashes.
- New dump versions or refreshed archive files.
- Provider-specific change feeds.

### Local Repository Mapping Questions

For any new provider, an implementer needs answers to:

- What is the Bronze natural key?
- Is raw storage one table or several entity tables?
- Are object, artist/agent, and image records embedded or separate?
- Is the source primarily dump-based, API-based, or hybrid?
- Does the source need bounded, rate-limited enrichment?
- Does the source need soft deletion or stale-record detection?
- Which raw fields will be needed by dbt staging models?
- Which fields prove public-domain or open access eligibility?
- How are primary images identified?
- How are alternate images identified?
- What metadata proves freshness or update time?
- Can orchestration express the source using current YAML schema?
- Are any framework changes generic enough to apply to all sources?

## Further Discovery Links

These directories and portals can surface additional APIs, but each candidate needs to be
verified against current official documentation before implementation:

- [IIIF Consortium Community](https://iiif.io/community/)
- [Linked Art](https://linked.art/)
- [OpenGLAM](https://openglam.org/)
- [Wikidata cultural heritage properties](https://www.wikidata.org/wiki/Wikidata:WikiProject_Cultural_heritage)
- [Data.gov](https://data.gov/)
- [AWS Open Data Registry](https://registry.opendata.aws/)
