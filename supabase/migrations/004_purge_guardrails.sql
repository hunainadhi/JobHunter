-- Track purged job keys to prevent re-ingestion
CREATE TABLE IF NOT EXISTS purged_jobs (
    ats_platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    purged_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ats_platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_purged_jobs_lookup
ON purged_jobs(ats_platform, external_id);

-- Replace the two separate cron jobs with a unified one that records purged keys
SELECT cron.unschedule('purge-raw-jobs');
SELECT cron.unschedule('purge-matched-jobs');

SELECT cron.schedule(
    'purge-old-jobs',
    '0 2 * * *',
    $$
    -- Record keys before deleting
    INSERT INTO purged_jobs (ats_platform, external_id)
    SELECT ats_platform, external_id FROM jobs
    WHERE (status NOT IN ('matched') AND first_seen_at < now() - INTERVAL '72 hours')
       OR (status = 'matched' AND first_seen_at < now() - INTERVAL '2 weeks')
    ON CONFLICT DO NOTHING;

    -- Then delete
    DELETE FROM jobs
    WHERE (status NOT IN ('matched') AND first_seen_at < now() - INTERVAL '72 hours')
       OR (status = 'matched' AND first_seen_at < now() - INTERVAL '2 weeks');

    -- Clean up purged_jobs older than 6 months
    DELETE FROM purged_jobs WHERE purged_at < now() - INTERVAL '6 months';
    $$
);
