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

## Access Mode Index

This index is a routing aid only. Each provider section below has the source facts and
open questions.

### Unauthenticated APIs Or Public Endpoints

- Met Collection API.
- AIC REST API and IIIF image service.
- CMA Open Access API.
- V&A collection APIs and IIIF access.
- Rijksmuseum Data Services Search API, OAI-PMH, LDES, and downloads.
- LOC JSON/YAML API.
- Wellcome Collection catalogue and IIIF APIs.
- Wikimedia Commons and Wikidata public read APIs and dumps.
- DigitalNZ API v3 public-content access, with optional key for higher-volume use.
- Statens Museum for Kunst API and IIIF endpoints.
- Getty Museum Collection REST records, ActivityStream, IIIF, and SPARQL endpoints.

### Authenticated APIs Or Tokened Access

- Smithsonian EDAN API through api.data.gov.
- Harvard Art Museums API.
- Europeana APIs.
- DPLA API.
- Cooper Hewitt Collection API.
- Paris Musees collections API.
- Trove API v3.
- Museum Data Service API-token export for public search results.

### Bulk Data, Dumps, GitHub Datasets, And Public Object Storage

- Smithsonian public S3 bucket.
- Met Open Access CSV on GitHub.
- AIC nightly S3 tarball.
- CMA GitHub Open Access data.
- Rijksmuseum downloads, OAI-PMH, and LDES options.
- Europeana Dataset Download and OAI-PMH.
- DPLA bulk download.
- Wikimedia and Wikidata dumps.
- National Gallery of Art GitHub CSV dataset.
- MoMA GitHub CSV and JSON datasets.
- Tate GitHub CSV and JSON snapshot, but stale.
- Minneapolis Institute of Art GitHub JSON repository.
- Museum Data Service CSV export and tokened JSON/CSV fetcher flow.

### IIIF Or Media-Focused Endpoints

- AIC IIIF image service.
- V&A IIIF image access.
- Rijksmuseum image and Linked Art access.
- Europeana IIIF API.
- Wellcome IIIF APIs.
- Harvard image base URLs.
- Getty IIIF Image and Presentation APIs.
- SMK IIIF manifest and image fields.
- Smithsonian IDS delivery and download URLs.
- Minneapolis Institute of Art thumbnail endpoints.

### Aggregators And Cross-Institution Sources

- Europeana.
- DPLA.
- DigitalNZ.
- Trove.
- LOC.
- Museum Data Service.
- Wikimedia Commons and Wikidata.

### Stale Or Historical Datasets

- Tate Collection GitHub repository, last updated October 2014.

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

## National Gallery Of Art Open Data

Primary links:

- [NGA Open Data GitHub repository](https://github.com/NationalGalleryOfArt/opendata)
- [NGA free images and open access page](https://www.nga.gov/artworks/free-images-and-open-access)

Access mode:

- GitHub-hosted CSV dataset.
- The repository includes `data/`, `documentation/`, `sql_tables/`, and a data
  dictionary.

Authentication:

- No authorization is needed to download the dataset from GitHub.

Data scope and format:

- NGA describes records for more than 130,000 artworks and artists.
- The dataset is published in CSV format with UTF-8 encoding.
- The repository includes documentation and a data dictionary.
- Wikidata identifiers are included where reconciled.

License and reuse:

- NGA releases the dataset under Creative Commons Zero to the extent permitted by law.
- Attribution or citation is requested but not required as a license condition.

Update notes:

- NGA says the dataset is updated frequently, usually once a day.

Media notes:

- Images and media files are not included in the dataset.
- The dataset can contain links and references to images, but image files are outside the
  open data program.

Implementation research questions:

- Which CSV files become Bronze entities, such as objects, constituents, attribution,
  provenance, and media references.
- Whether daily GitHub updates are treated as snapshots, deltas, or release-like commits.
- How to preserve image references without implying image reuse rights.
- Whether Wikidata IDs are used only as enrichment fields or as reconciliation keys.

## Museum Of Modern Art Collection Dataset

Primary links:

- [MoMA collection GitHub repository](https://github.com/MuseumofModernArt/collection)
- [MoMA collection website](https://www.moma.org/collection/)

Access mode:

- GitHub dataset in CSV and JSON.

Authentication:

- No API key is required for the GitHub dataset.

Data scope and format:

- MoMA describes its website collection as 107,903 artworks from 28,369 artists.
- The research dataset contains 160,597 artwork records.
- The artists dataset contains 15,927 records.
- Files include `Artworks.csv`, `Artworks.json`, `Artists.csv`, and `Artists.json`.
- Artwork fields include basic metadata such as title, artist, date made, medium,
  dimensions, and acquisition date.
- Artist fields include name, nationality, gender, birth and death years, Wikidata QID, and
  Getty ULAN ID.

License and reuse:

- The datasets are placed in the public domain under CC0.
- MoMA requests attribution and asks users not to misrepresent the dataset or imply
  endorsement.

Update notes:

- MoMA says it plans regular updates.
- The GitHub repository showed a latest release `v2026-06-30` during this review.

Media notes:

- Images are not included and are not part of the dataset.
- MoMA directs image licensing through rights-management services.

Implementation research questions:

- Whether CSV or JSON is the preferred Bronze raw format.
- How to represent curator-approved versus research-in-progress records.
- Whether the release tag, Git commit SHA, or file hash is the snapshot version.
- How to model artist records separately from artwork records.

## Tate Collection Dataset

Primary links:

- [Tate collection GitHub repository](https://github.com/tategallery/collection)

Access mode:

- GitHub JSON and CSV dataset.

Authentication:

- No API key is required for the GitHub dataset.

Data scope and format:

- Tate describes metadata for around 70,000 artworks and around 3,500 associated artists.
- JSON is organized by folders.
- CSV files include `artist_data.csv` and `artwork_data.csv`.
- Artwork JSON is filed by accession number.
- Artist JSON is filed by the first letter of the artist surname.

License and reuse:

- Metadata is released under Creative Commons Zero Public Domain Dedication.
- Tate requests attribution where possible.

Staleness note:

- The repository says it is no longer actively maintained.
- The dataset was last updated in October 2014.

Media notes:

- Images are not included and are not part of the dataset.
- Tate image use is covered separately by Tate copyright and permissions or image licensing
  channels.

Implementation research questions:

- Whether this is useful only as a historical fixture or research reference.
- Whether staleness makes it unsuitable for production ingestion.
- How to flag the source as stale if loaded for tests, comparison, or exploration.

## Minneapolis Institute Of Art Collection Metadata

Primary links:

- [Mia collection GitHub repository](https://github.com/artsmia/collection)
- [Mia collections website](https://collections.artsmia.org/)
- [Mia image access policy](https://new.artsmia.org/image-access-use)

Access mode:

- GitHub JSON repository.
- Provider thumbnail endpoints by object ID.

Authentication:

- No API key is required for the GitHub dataset.

Data layout and shape:

- Object records live at `objects/$bucket/$id.json`, where `bucket` is the object ID divided
  by 1000.
- Exhibition records are organized in similar buckets.
- Observed object fields include accession number, artist, continent, country, credit line,
  culture, date, description, dimensions, ID, image state, image copyright, image
  dimensions, life date, medium, nationality, provenance, restricted flag, role, room,
  style, text, and title.

License and reuse:

- Mia publishes artwork metadata as JSON under a CC0 license.
- The repository asks for attribution and for users to obey the separate image policy.

Update notes:

- Mia says records are updated and added constantly, with changes committed approximately
  once per day.

Media notes:

- Images are not under the same license as metadata.
- Object records expose `image: valid|invalid` and `restricted: 0|1`.
- Thumbnail URLs use:

```text
http://api.artsmia.org/images/$id/{small,medium,large}.jpg
```

- Small images are 100px on the long side, medium 600px, and large 800px.
- Unrestricted images are described for limited non-commercial and educational purposes.

Implementation research questions:

- Whether to ingest objects only, or objects plus exhibitions and departments.
- Whether object IDs or accession numbers are the Bronze natural key.
- Whether image thumbnails are stored as source facts only, or separately classified by
  downstream rights logic.
- How to handle `restricted` media separately from CC0 metadata.

## Paris Musees Collections API

Primary links:

- [Paris Musees collections API portal](https://apicollections.parismusees.paris.fr/)
- [Paris Musees collections portal](https://parismuseescollections.paris.fr/)
- [API documentation link from the portal](https://parismuseescollections.paris.fr/fr/api)

Access mode:

- JSON API access.
- GraphQL explorer is linked from the API portal.

Authentication:

- Account creation is required.
- An authentication token is required for requests.

Data scope:

- Paris Musees manages the network of 14 City of Paris museums.
- The collections portal describes more than 280,000 object notices, bibliographic
  resources, and archives.
- The API exists to open part of the institution's data and enable reuse in digital
  projects.

Endpoint and model notes:

- The public landing page does not expose the complete endpoint list in static HTML.
- The portal says users can make GraphQL requests in an explorer after account creation.

Implementation research questions:

- What the current GraphQL endpoint URL and schema look like after authentication.
- Which fields distinguish open data from restricted records.
- How media URLs and media rights are represented.
- Whether the API supports pagination, filtering by museum, and changed-since queries.
- Whether token issuance is stable enough for scheduled extraction.

## DigitalNZ API

Primary links:

- [DigitalNZ developers page](https://digitalnz.org/developers)
- [DigitalNZ API v3 docs](https://digitalnz.org/developers/api-docs-v3)
- [DigitalNZ OpenAPI spec on SwaggerHub](https://app.swaggerhub.com/apis/DigitalNZ/digital-nz_api/3.0.0)
- [DigitalNZ metadata dictionary](https://digitalnz.org/developers/metadata-dictionary)

Access mode:

- API v3.
- Search records endpoint.
- Get metadata endpoint for a specific record.

Authentication:

- Public content no longer requires an API key.
- DigitalNZ encourages a key for regular, high-volume, or application use.
- API keys are sent in the `Authentication-Token` HTTP header.
- Unauthenticated requests share a maximum rate limit.

Data scope and model:

- DigitalNZ aggregates New Zealand-related digital items from contributing cultural,
  government, education, science, and community organizations.
- DigitalNZ holds metadata and pointers to source content; it does not hold copies of the
  collection items.
- The API returns pointers to content objects and thumbnail images.

Implementation research questions:

- Whether DigitalNZ is useful as an aggregator source or only as enrichment/discovery.
- How to filter by rights, provider, collection, and thumbnail availability.
- How to avoid duplicate records if direct New Zealand museum sources are later added.
- What rate limit applies to unauthenticated versus tokened extraction.

## Trove API

Primary links:

- [Trove API overview](https://trove.nla.gov.au/about/create-something/using-api)
- [Trove API v3 interface](https://api.trove.nla.gov.au/v3/)
- [Trove API technical guide](https://trove.nla.gov.au/about/create-something/using-api/api-technical-guide)
- [Trove bulk download](https://trove.nla.gov.au/about/create-something/bulk-download)

Access modes:

- Trove API v3.
- Bulk-download workflows are linked from Trove documentation.

Authentication:

- Ongoing API use requires an active API key.
- Users need a Trove account and must request an API key.
- The application asks for desired call rate and intended use.

Data scope:

- Trove aggregates Australian cultural and research records from partner organizations.
- Relevant categories include images, maps, artefacts, diaries, letters, archives, music,
  audio, video, newspapers, books, and people or organizations.

Rate and policy notes:

- API access is reviewed by intended use.
- The public application table includes a 200 requests per minute call-rate tier.
- AI modelling, machine learning, and generative-AI training uses receive higher review and
  may need exemptions or data-sharing agreements.
- Trove API version 2 was discontinued in September 2024.

Implementation research questions:

- Whether Trove should be treated as an aggregator, enrichment source, or source-specific
  extraction target.
- Which categories and rights filters isolate reusable art or visual-culture records.
- Whether bulk download is more appropriate than API pagination for large analyses.
- How provider attribution and duplicate detection would work.

## Statens Museum For Kunst API

Primary links:

- [SMK API Swagger UI](https://api.smk.dk/api/v1/docs/)
- [SMK Open](https://open.smk.dk/)
- [SMK API article](https://www.smk.dk/article/smk-api/)

Access mode:

- REST API at `https://api.smk.dk/api/v1`.
- Swagger/OpenAPI document at `https://api.smk.dk/api/v1/swagger.json`.
- IIIF manifest and image fields in artwork records.

Authentication:

- The OpenAPI description calls the API free to use.
- No API key requirement was visible in the inspected OpenAPI document.

Documented endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /art` | Fetch one or more artworks by `object_number`. |
| `GET /art/search` | Search artworks with available information. |
| `GET /art/all_ids` | Return all object IDs. |
| `GET /person` | Fetch one person record. |
| `GET /person/search` | Search persons. |
| `GET /iiif/manifest` | Return IIIF Presentation API manifests. |
| `GET /iiif/autocomplete` | Find objects with IIIF links. |
| `GET /art/field_info` | Return artwork field descriptions. |
| `GET /persons/field_info` | Return person field descriptions. |

Important parameters and output formats:

- `keys` is required on `/art/search` and `/person/search`.
- `offset` and `rows` paginate search results.
- `rows` has a documented maximum of 2000.
- Output options include SMK JSON by default, plus `IIIF-Manifest`, `DC-json`, `JSON-LD`,
  and `Mets` in relevant endpoints.
- Language options include Danish and English.

Data and media notes:

- A sampled `/art/search?keys=*&offset=0&rows=1` response reported `found: 200018`.
- Artwork fields include `created`, `modified`, `object_number`, titles, production,
  materials, dimensions, collection, work status, `public_domain`, `rights`, `has_image`,
  `image_hq`, `image_iiif_id`, `image_iiif_info`, `image_thumbnail`, `image_native`,
  `iiif_manifest`, alternative images, and 3D-file flags.
- `/art/field_info` identifies `modified` as useful for updating data.
- Facets include `public_domain`, `has_image`, `image_hq`, `has_3d_file`, collection,
  object names, creator fields, and other classifications.

Implementation research questions:

- Whether `/art/all_ids` or paginated `/art/search` is the better full-snapshot driver.
- Whether to use `modified` range filters for incremental sync.
- How to preserve SMK JSON versus JSON-LD or IIIF manifest forms.
- How to model public-domain flags separately from image availability and 3D files.

## Getty Museum Collection API

Primary links:

- [Getty Museum Collection API documentation](https://data.getty.edu/museum/collection/docs/)
- [Getty Museum Collection API root](https://data.getty.edu/museum/collection/)
- [Getty Museum Collection ActivityStream](https://data.getty.edu/museum/collection/activity-stream)
- [Getty Museum Collection SPARQL endpoint](https://data.getty.edu/museum/collection/sparql)
- [Getty Museum Collection SPARQL UI](https://data.getty.edu/museum/collection/sparql-ui)

Access modes:

- REST-style entity records.
- ActivityStreams change feed.
- SPARQL endpoint.
- IIIF Image API.
- IIIF Presentation API.

Authentication:

- No API key requirement was visible in the inspected documentation.

Data scope:

- Getty describes metadata for more than 250,000 objects in the Getty Museum Collection,
  including current and deaccessioned objects.
- Entity types include `object`, `place`, `document`, `group`, `person`, `exhibition`, and
  `activity`.

Data model:

- The API is based on the Linked Art standard.
- JSON records link to related entities.
- The API uses ActivityStreams to track created, edited, and deleted records.
- Getty explicitly says there is currently no list-all endpoint and no full data download,
  but both are on the roadmap.
- The documentation says the ActivityStream can be crawled to build a list of records and
  track changes.

Endpoint examples:

```text
https://data.getty.edu/museum/collection/object/<ENTITY_ID>
https://data.getty.edu/museum/collection/person/<ENTITY_ID>
https://media.getty.edu/iiif/image/<IMAGE_ID>
https://media.getty.edu/iiif/manifest/<MANIFEST_ID>
```

License and rights:

- Getty says the dataset is CC0 with exceptions.
- Images are linked through IIIF but are not always available under the same terms.
- Image rights are machine-readable under image `subject_to` blocks.
- Written descriptions and artist biographies can have separate rights, often CC BY rather
  than CC0.

Implementation research questions:

- Whether ActivityStream crawling is acceptable for full inventory discovery.
- Whether SPARQL is needed for broad queries before record fetches.
- How to preserve Linked Art JSON-LD in Bronze without premature normalization.
- How to evaluate per-image and per-description rights before downstream reuse.

## Museum Data Service

Primary links:

- [Museum Data Service](https://museumdata.uk/)
- [Object search](https://museumdata.uk/object-search/)
- [Data scope](https://museumdata.uk/using-data/data-scope/)
- [Who can use MDS data?](https://museumdata.uk/using-data/who-can-use-mds-data/)

Access modes:

- Public object-search interface.
- CSV export for search results.
- Tokened API access for public fields from search results.
- MDS Data Fetcher utility can download tokened result sets as CSV or JSON.

Authentication:

- Public search does not require a login.
- API-token export is requested from the search interface.
- Restricted fields may require named-user or accredited-researcher access if museums allow
  it.

Data scope:

- MDS is a joint initiative by Art UK, Collections Trust, and the University of Leicester.
- It aims to connect and share object records across UK museums.
- On the inspected object-search page, MDS reported 7,839,415 object records from 133
  collection datasets, including data from 257 accredited museums.
- The same page reported 1,087,826 records indicating an associated image.
- Records are more-or-less source exports with mapped field names, not deeply harmonized
  cultural-heritage records.

License and reuse:

- MDS explicitly says it is not an open-data initiative.
- Source museums control how much data is visible and set licensing terms.
- Public records can be searched and reused subject to the relevant data licenses.
- MDS notes many UK museums may choose non-commercial or attribution licenses rather than
  CC0.

Media notes:

- MDS does not ingest image files or other digital media.
- Records may include image locations stored elsewhere when museums provide them.

Implementation research questions:

- Whether MDS belongs in scope given its mixed licensing model.
- How to filter records by data-use license before extraction.
- Whether tokened result exports are sufficient for repeatable ingestion.
- How to preserve source museum identity and raw field names.
- How to avoid overlap with Art UK, direct museum APIs, or other UK aggregators.

## IIIF As A Cross-Provider Theme

Many museum APIs expose image media through IIIF or IIIF-like image services.

Providers in this catalog with explicit IIIF relevance:

- AIC
- V&A
- Rijksmuseum
- Europeana
- Wellcome
- Harvard Art Museums
- Getty Museum Collection
- Statens Museum for Kunst
- Minneapolis Institute of Art thumbnail endpoints, though these are not full IIIF in the
  repository docs
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
| National Gallery of Art | No key for GitHub CSV dataset. |
| MoMA | No key for GitHub CSV/JSON dataset. |
| Tate | No key for GitHub CSV/JSON snapshot. |
| Minneapolis Institute of Art | No key for GitHub JSON dataset. |
| Paris Musees | Account and token required. |
| DigitalNZ | No key for public content; key encouraged for regular or high-volume use. |
| Trove | API key required for ongoing API use. |
| SMK | No key observed in OpenAPI document. |
| Getty Museum Collection | No key observed in inspected docs. |
| Museum Data Service | Public search is open; API-token export is requested through search UI. |

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
- National Gallery of Art GitHub CSV dataset.
- MoMA GitHub CSV and JSON datasets.
- Tate GitHub CSV and JSON snapshot, but stale.
- Minneapolis Institute of Art GitHub JSON repository.
- Museum Data Service CSV export and tokened result-fetching flow.

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

## Candidate Sources Needing Verification

Do not treat these as implementation-ready until official current documentation confirms both
reusable metadata and a programmatic retrieval layer.

| Candidate | Current status |
| --- | --- |
| British Museum | Public collection pages exist, but current official API, dump, or licensing docs were not verified in this pass. |
| National Portrait Gallery London | Public collection and image-licensing information exists, but a current open programmatic collection API was not verified. |
| Los Angeles County Museum of Art | Collection search exists, but official reusable data and programmatic access were not verified. |
| Dallas Museum of Art | Public collection exists and appears in aggregator contexts, but direct official API/open-data docs were not verified. |
| Walters Art Museum | Strong open-access history and online collection, but current official API/dump docs were not verified in this pass. |
| Yale Center for British Art and Yale University Art Gallery | Yale LUX exposes Linked Art-style entity data in the app, but public developer docs, bulk access, and reuse terms need verification. |
| Auckland Museum | Candidate cultural collection source; official API or dump docs were not verified. |
| Te Papa | Candidate New Zealand collection source; official API or dump docs were not verified. |
| Powerhouse Museum | Candidate Australian collection source; official API or dump docs were not verified. |
| National Gallery of Victoria | Collection site exists, but current official API/open-data docs were not verified. |
| Finnish National Gallery | Collection site exists, but official API or dump docs were not verified. |
| DigitaltMuseum / DIMU | Search results suggest an API exists, but official current API and licensing docs were not verified. |
| Brooklyn Museum | Historic API paths now redirect or fail in inspected requests; current API status and reuse terms need verification. |
| Art UK | Major UK artwork aggregator and MDS partner, but direct public API/export terms were not verified separately from MDS. |
