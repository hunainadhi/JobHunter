-- Enable pg_cron extension (run as superuser in Supabase SQL editor)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Purge unmatched raw jobs older than 72 hours (runs daily at 2am UTC)
SELECT cron.schedule(
    'purge-raw-jobs',
    '0 2 * * *',
    $$
    DELETE FROM jobs
    WHERE status != 'matched'
      AND first_seen_at < now() - INTERVAL '72 hours';
    $$
);

-- Purge matched jobs older than 2 weeks (runs daily at 2am UTC)
SELECT cron.schedule(
    'purge-matched-jobs',
    '0 2 * * *',
    $$
    DELETE FROM jobs
    WHERE status = 'matched'
      AND first_seen_at < now() - INTERVAL '2 weeks';
    $$
);
