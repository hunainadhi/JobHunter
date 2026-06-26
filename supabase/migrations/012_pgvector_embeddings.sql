-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- Add embedding column (768 dimensions for Google text-embedding-005)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS embedding vector(256);

-- HNSW index for cosine similarity
CREATE INDEX IF NOT EXISTS idx_jobs_embedding
ON jobs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 25);

-- Semantic search RPC function
CREATE OR REPLACE FUNCTION match_jobs(
  query_embedding vector(256),
  match_threshold float DEFAULT 0.3,
  match_count int DEFAULT 30,
  offset_val int DEFAULT 0,
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
  similarity float
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  SELECT
    j.id, j.title, j.company_name, j.location, j.is_remote,
    j.apply_url, j.source_url, j.posted_at, j.first_seen_at, j.ats_platform,
    s.category,
    (1 - (j.embedding <=> query_embedding))::float AS similarity
  FROM jobs j
  LEFT JOIN scores s ON s.job_id = j.id
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
  ORDER BY j.posted_at DESC NULLS LAST
  LIMIT match_count
  OFFSET offset_val;
END;
$$;

-- Count companion for pagination
CREATE OR REPLACE FUNCTION count_matched_jobs(
  query_embedding vector(256),
  match_threshold float DEFAULT 0.3,
  filter_location text DEFAULT NULL,
  filter_company text DEFAULT NULL,
  filter_platform text DEFAULT NULL,
  filter_category text DEFAULT NULL,
  filter_level text DEFAULT NULL,
  filter_date_cutoff timestamptz DEFAULT NULL
)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  total int;
BEGIN
  SELECT count(*)::int INTO total
  FROM jobs j
  LEFT JOIN scores s ON s.job_id = j.id
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
         OR (j.posted_at IS NULL AND j.first_seen_at >= filter_date_cutoff));
  RETURN total;
END;
$$;

-- Grant access to anon role (board uses anon key)
GRANT EXECUTE ON FUNCTION match_jobs TO anon;
GRANT EXECUTE ON FUNCTION count_matched_jobs TO anon;
