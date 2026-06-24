-- Drop old purge job
SELECT cron.unschedule('purge-old-jobs');

-- New purge job: runs daily at 2am UTC
SELECT cron.schedule('purge-stale-jobs', '0 2 * * *', $$
  -- 1. Mark jobs not seen for 3+ days as expired (soft delete)
  UPDATE jobs
  SET status = 'expired'
  WHERE last_seen_at < now() - INTERVAL '3 days'
    AND status != 'expired';

  -- 2. Record and hard-delete jobs not seen for 7+ days
  INSERT INTO purged_jobs (ats_platform, external_id)
  SELECT ats_platform, external_id FROM jobs
  WHERE last_seen_at < now() - INTERVAL '7 days'
  ON CONFLICT DO NOTHING;

  DELETE FROM jobs
  WHERE last_seen_at < now() - INTERVAL '7 days';

  -- 3. Also keep the 4-week max retention as a safety net
  INSERT INTO purged_jobs (ats_platform, external_id)
  SELECT ats_platform, external_id FROM jobs
  WHERE first_seen_at < now() - INTERVAL '4 weeks'
  ON CONFLICT DO NOTHING;

  DELETE FROM jobs
  WHERE first_seen_at < now() - INTERVAL '4 weeks';

  -- 4. Clean up old purge records
  DELETE FROM purged_jobs
  WHERE purged_at < now() - INTERVAL '6 months';
$$);
