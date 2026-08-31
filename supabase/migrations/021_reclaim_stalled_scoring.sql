-- Reclaim jobs stranded in 'scoring' by a hard Lambda timeout.
--
-- claim_jobs_for_scoring flips jobs to 'scoring', and the scoring Lambda
-- releases them back to 'new' at the end of a round. When the Lambda is killed
-- by its 900s wall clock mid-round, that release never runs and the claim
-- leaks: 778 jobs had accumulated this way, the oldest from 2026-08-17. They
-- are never retried, so they never reach the dashboard.
--
-- A timestamp on the claim makes the leak detectable, and the sweeper below
-- returns anything held too long. Scoped by age rather than blanket-resetting
-- every 'scoring' row, so a concurrently running invocation keeps its claim.

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS scoring_claimed_at timestamptz;

-- Partial index: the sweeper only ever looks at rows in this one status, which
-- is a tiny slice of the table.
CREATE INDEX IF NOT EXISTS idx_jobs_scoring_claimed_at
    ON jobs (scoring_claimed_at)
    WHERE status = 'scoring';

-- Stamp the claim time. Same body as migration 014 otherwise.
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
    SET status = 'scoring',
        scoring_claimed_at = now()
    WHERE jobs.id IN (
        SELECT j.id FROM jobs j
        WHERE j.status = 'new' AND j.description IS NOT NULL
        ORDER BY j.first_seen_at DESC
        LIMIT claim_count
        FOR UPDATE SKIP LOCKED
    )
    RETURNING jobs.id, jobs.title, jobs.company_name, jobs.location, jobs.description;
$$;

-- Return long-held claims to the pool. NULL scoring_claimed_at means the row
-- was claimed before this migration, which can only be a pre-existing leak.
CREATE OR REPLACE FUNCTION reclaim_stalled_scoring_jobs(stale_minutes integer DEFAULT 30)
RETURNS integer
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    reclaimed integer;
BEGIN
    UPDATE jobs
    SET status = 'new',
        scoring_claimed_at = NULL
    WHERE status = 'scoring'
      AND (scoring_claimed_at IS NULL
           OR scoring_claimed_at < now() - make_interval(mins => stale_minutes));
    GET DIAGNOSTICS reclaimed = ROW_COUNT;
    RETURN reclaimed;
END;
$$;

-- Clear the stamp when a job leaves 'scoring' through the normal path, so a
-- later re-claim can't be judged against a stale timestamp.
CREATE OR REPLACE FUNCTION clear_scoring_claimed_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    IF NEW.status <> 'scoring' AND NEW.scoring_claimed_at IS NOT NULL THEN
        NEW.scoring_claimed_at := NULL;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_clear_scoring_claimed_at ON jobs;
CREATE TRIGGER trg_clear_scoring_claimed_at
    BEFORE UPDATE OF status ON jobs
    FOR EACH ROW
    WHEN (NEW.status <> 'scoring')
    EXECUTE FUNCTION clear_scoring_claimed_at();

REVOKE ALL ON FUNCTION reclaim_stalled_scoring_jobs(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION reclaim_stalled_scoring_jobs(integer) FROM anon;
GRANT EXECUTE ON FUNCTION reclaim_stalled_scoring_jobs(integer) TO service_role;
