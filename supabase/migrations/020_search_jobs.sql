-- One search function for both board paths.
--
-- The board previously ran two independent queries: a PostgREST query-builder
-- path and the match_jobs RPC for semantic search. Radius filtering cannot be
-- expressed in the query builder (it needs an EXISTS against a view, which
-- PostgREST cannot infer a foreign key for), so both converge here.
--
-- Two bugs fixed on the way:
--   * match_jobs pinned the scores join to 'MiniMax-M3' while the query-builder
--     path used the current OPENROUTER_MODEL, so category/level filters returned
--     different results depending on whether the user typed a search term.
--     The model is now a parameter.
--   * A NULL query_embedding now means "no semantic ranking" rather than
--     requiring a separate code path.

DROP FUNCTION IF EXISTS search_jobs(vector(256), float, int, int, text, text, text,
    text, float, boolean, text, text, text, text, timestamptz, text);

CREATE OR REPLACE FUNCTION search_jobs(
  query_embedding    vector(256)  DEFAULT NULL,
  match_threshold    float        DEFAULT 0.3,
  match_count        int          DEFAULT 30,
  offset_val         int          DEFAULT 0,
  sort_by            text         DEFAULT 'posted_at',  -- similarity|posted_at|title|distance
  filter_q           text         DEFAULT NULL,
  filter_location    text         DEFAULT NULL,   -- legacy free-text, kept for old URLs
  filter_place       text         DEFAULT NULL,   -- places.slug anchor
  filter_radius_km   float        DEFAULT 25,
  include_remote     boolean      DEFAULT true,
  filter_company     text         DEFAULT NULL,
  filter_platform    text         DEFAULT NULL,
  filter_category    text         DEFAULT NULL,
  filter_level       text         DEFAULT NULL,
  filter_date_cutoff timestamptz  DEFAULT NULL,
  scoring_model      text         DEFAULT 'qwen/qwen3-30b-a3b'
)
RETURNS TABLE (
  id uuid,
  title text,
  company_name text,
  location text,
  is_remote boolean,
  apply_url text,
  source_url text,
  posted_at timestamptz,
  first_seen_at timestamptz,
  ats_platform text,
  category text,
  location_status text,
  distance_km float,
  similarity float,
  total_count bigint
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions
AS $$
  WITH anchor AS (
    SELECT p.latitude, p.longitude
    FROM places p
    WHERE filter_place IS NOT NULL AND p.slug = filter_place
  ),
  -- Small table (~1,750 rows), so this is a trivial scan with no index needed.
  near AS (
    SELECT p.slug,
           km_between(a.latitude, a.longitude, p.latitude, p.longitude) AS km
    FROM places p
    CROSS JOIN anchor a
    WHERE km_between(a.latitude, a.longitude, p.latitude, p.longitude) <= filter_radius_km
  ),
  -- One row per job, carrying the nearest of its places, so a Toronto-and-
  -- Waterloo posting appears once in a Waterloo search rather than twice.
  in_radius AS (
    SELECT lap.raw_location, MIN(n.km) AS km
    FROM location_alias_places lap
    JOIN near n ON n.slug = lap.place_slug
    GROUP BY lap.raw_location
  )
  SELECT
    j.id, j.title, j.company_name, j.location, j.is_remote,
    j.apply_url, j.source_url, j.posted_at, j.first_seen_at, j.ats_platform,
    s.category,
    COALESCE(la.status, 'unresolved')::text AS location_status,
    r.km::float AS distance_km,
    CASE WHEN query_embedding IS NULL THEN NULL
         ELSE (1 - (j.embedding <=> query_embedding))::float END AS similarity,
    count(*) OVER () AS total_count
  FROM jobs j
  LEFT JOIN scores s          ON s.job_id = j.id AND s.model = scoring_model
  LEFT JOIN location_aliases la ON la.raw_location = j.location
  LEFT JOIN in_radius r       ON r.raw_location = j.location
  WHERE j.status <> 'expired'
    AND (query_embedding IS NULL
         OR (j.embedding IS NOT NULL
             AND 1 - (j.embedding <=> query_embedding) > match_threshold))
    AND (filter_q IS NULL
         OR j.title ILIKE '%' || filter_q || '%'
         OR j.company_name ILIKE '%' || filter_q || '%')
    -- Radius: a job qualifies by distance, or by being remote/Canada-wide when
    -- those are included. A Canada-remote role is genuinely open to someone in
    -- Waterloo, so hiding it would make the board worse at its commonest search.
    AND (filter_place IS NULL
         OR r.km IS NOT NULL
         OR (include_remote AND COALESCE(la.status, '') = 'countrywide'))
    -- Legacy free-text location, still serving old bookmarked URLs and "remote".
    AND (filter_location IS NULL
         OR j.location ILIKE '%' || filter_location || '%'
         OR (LOWER(filter_location) = 'remote'
             AND (j.is_remote = true OR COALESCE(la.status, '') = 'countrywide')))
    -- Unresolved locations are legacy rows only; ingest rejects them now.
    AND (filter_place IS NULL OR COALESCE(la.status, '') <> 'unresolved')
    AND (filter_company IS NULL OR j.company_name ILIKE '%' || filter_company || '%')
    AND (filter_platform IS NULL OR j.ats_platform = filter_platform)
    AND (filter_category IS NULL OR s.category = filter_category)
    AND (filter_level IS NULL OR s.level = filter_level)
    AND (filter_date_cutoff IS NULL OR j.posted_at >= filter_date_cutoff
         OR (j.posted_at IS NULL AND j.first_seen_at >= filter_date_cutoff))
  ORDER BY
    CASE WHEN sort_by = 'similarity' AND query_embedding IS NOT NULL
         THEN j.embedding <=> query_embedding END ASC,
    CASE WHEN sort_by = 'distance' THEN r.km END ASC NULLS LAST,
    CASE WHEN sort_by = 'posted_at' THEN COALESCE(j.posted_at, j.first_seen_at) END DESC,
    CASE WHEN sort_by = 'title' THEN j.title END ASC,
    j.id
  LIMIT match_count
  OFFSET offset_val;
$$;

GRANT EXECUTE ON FUNCTION search_jobs TO anon;

-- Autocomplete source: places with jobs, biggest first.
CREATE OR REPLACE FUNCTION places_with_jobs()
RETURNS TABLE (slug text, name text, province text, job_count bigint)
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = public
AS $$
  SELECT slug, name, province, job_count
  FROM place_job_counts
  ORDER BY job_count DESC, name ASC;
$$;

GRANT EXECUTE ON FUNCTION places_with_jobs TO anon;
