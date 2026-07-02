-- Mark a row enriched: store the API-sourced image URLs and clear any prior error.
UPDATE met_artworks
SET primary_image_url       = :primary_image_url,
    primary_image_small_url = :primary_image_small_url,
    additional_image_urls   = :additional_image_urls,
    enrichment_status       = 'done',
    enrichment_error        = NULL,
    enriched_at             = :enriched_at
WHERE object_id = :object_id;
