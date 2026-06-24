-- Update purge policy: keep ALL jobs for 4 weeks regardless of status
-- Previously: non-matched deleted after 72h, matched after 2 weeks

SELECT cron.unschedule('purge-old-jobs');

SELECT cron.schedule(
    'purge-old-jobs',
    '0 2 * * *',
    $$
    INSERT INTO purged_jobs (ats_platform, external_id)
    SELECT ats_platform, external_id FROM jobs
    WHERE first_seen_at < now() - INTERVAL '4 weeks'
    ON CONFLICT DO NOTHING;

    DELETE FROM jobs
    WHERE first_seen_at < now() - INTERVAL '4 weeks';

    DELETE FROM purged_jobs WHERE purged_at < now() - INTERVAL '6 months';
    $$
);

-- Clear purged_jobs so previously deleted jobs get re-ingested
TRUNCATE purged_jobs;
