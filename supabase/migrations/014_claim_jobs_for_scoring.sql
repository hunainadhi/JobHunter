-- Atomic job claim for the scoring Lambda.
-- Replaces the SELECT-then-UPDATE pattern that let overlapping invocations
-- claim (and pay to score) the same jobs twice. FOR UPDATE SKIP LOCKED makes
-- concurrent callers claim disjoint sets.

CREATE OR REPLACE FUNCTION claim_jobs_for_scoring(claim_count integer DEFAULT 100)
RETURNS TABLE (
    id uuid,
    title text,
    company_name text,
    location text,
    description text
)
LANGUAGE sql
SET search_path = public
AS $$
    UPDATE jobs
    SET status = 'scoring'
    WHERE jobs.id IN (
        SELECT j.id FROM jobs j
        WHERE j.status = 'new' AND j.description IS NOT NULL
        ORDER BY j.first_seen_at DESC
        LIMIT claim_count
        FOR UPDATE SKIP LOCKED
    )
    RETURNING jobs.id, jobs.title, jobs.company_name, jobs.location, jobs.description;
$$;

-- Only the service role (scoring Lambda) may claim jobs.
REVOKE ALL ON FUNCTION claim_jobs_for_scoring(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION claim_jobs_for_scoring(integer) FROM anon;
GRANT EXECUTE ON FUNCTION claim_jobs_for_scoring(integer) TO service_role;
