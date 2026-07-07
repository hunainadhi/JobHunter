-- Fixes three problems from migration 012 plus ongoing maintenance gaps:
--   1. match_jobs ordered by posted_at, never by vector distance, so results
--      weren't actually similarity-ranked and the IVFFlat index was never used.
--      The index was also built on an empty table (degenerate centroids). At
--      free-tier scale an exact scan is fast and always correct, so the index
--      is dropped rather than rebuilt (rebuild also risks the 32MB
--      maintenance_work_mem limit that forced 256 dims in the first place).
--   2. count_matched_jobs re-ran the whole cosine scan a second time per
--      search. match_jobs now returns total_count via a window function.
--   3. scores join was unscoped: with multiple models per job (MiniMax-M3,
--      keyword-filter) the join could duplicate rows. Now pinned to MiniMax-M3.
-- Plus: missing btree indexes for hot query patterns, and a purge cron for
-- scrape_runs (~1,600 rows/day, previously never cleaned up).

-- ============ 1. Semantic search rewrite ============

DROP INDEX IF EXISTS idx_jobs_embedding;

-- Signature changes (new sort_by param, new total_count column) require drops.
DROP FUNCTION IF EXISTS match_jobs(vector(256), float, int, int, text, text, text, text, text, timestamptz);
DROP FUNCTION IF EXISTS count_matched_jobs(vector(256), float, text, text, text, text, text, timestamptz);

CREATE OR REPLACE FUNCTION match_jobs(
  query_embedding vector(256),
  match_threshold float DEFAULT 0.3,
  match_count int DEFAULT 30,
  offset_val int DEFAULT 0,
  sort_by text DEFAULT 'similarity',  -- 'similarity' | 'posted_at' | 'title'
  filter_location text DEFAULT NULL,
  filter_company text DEFAULT NULL,
  filter_platform text DEFAULT NULL,
  filter_category text DEFAULT NULL,
  filter_level text DEFAULT NULL,
  filter_date_cutoff timestamptz DEFAULT NULL
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
  similarity float,
  total_count bigint
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions
AS $$
  SELECT
    j.id, j.title, j.company_name, j.location, j.is_remote,
    j.apply_url, j.source_url, j.posted_at, j.first_seen_at, j.ats_platform,
    s.category,
    (1 - (j.embedding <=> query_embedding))::float AS similarity,
    count(*) OVER () AS total_count
  FROM jobs j
  LEFT JOIN scores s ON s.job_id = j.id AND s.model = 'MiniMax-M3'
  WHERE j.status != 'expired'
    AND j.embedding IS NOT NULL
    AND 1 - (j.embedding <=> query_embedding) > match_threshold
    AND (filter_location IS NULL OR j.location ILIKE '%' || filter_location || '%'
         OR (LOWER(filter_location) = 'remote' AND j.is_remote = true))
    AND (filter_company IS NULL OR j.company_name ILIKE '%' || filter_company || '%')
    AND (filter_platform IS NULL OR j.ats_platform = filter_platform)
    AND (filter_category IS NULL OR s.category = filter_category)
    AND (filter_level IS NULL OR s.level = filter_level)
    AND (filter_date_cutoff IS NULL OR j.posted_at >= filter_date_cutoff
         OR (j.posted_at IS NULL AND j.first_seen_at >= filter_date_cutoff))
  ORDER BY
    CASE WHEN sort_by = 'similarity' THEN j.embedding <=> query_embedding END ASC,
    CASE WHEN sort_by = 'posted_at' THEN COALESCE(j.posted_at, j.first_seen_at) END DESC,
    CASE WHEN sort_by = 'title' THEN j.title END ASC,
    j.id
  LIMIT match_count
  OFFSET offset_val;
$$;

GRANT EXECUTE ON FUNCTION match_jobs TO anon;

-- ============ 2. Missing btree indexes ============

CREATE INDEX IF NOT EXISTS idx_scores_job_id ON scores(job_id);
CREATE INDEX IF NOT EXISTS idx_scores_category ON scores(category);
CREATE INDEX IF NOT EXISTS idx_scores_level ON scores(level);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(ats_platform);

-- ============ 3. scrape_runs retention ============

-- Idempotent unschedule (cron.unschedule throws if the job doesn't exist).
DO $$
BEGIN
  PERFORM cron.unschedule('purge-scrape-runs');
EXCEPTION WHEN OTHERS THEN
  NULL;
END $$;

SELECT cron.schedule('purge-scrape-runs', '30 2 * * *', $$
  DELETE FROM scrape_runs
  WHERE started_at < now() - INTERVAL '14 days';
$$);
