-- One-time cleanup: remove title-only scores and backfill posted_at
-- Run this in the Supabase SQL Editor

-- 1. Delete all title-only scores
DELETE FROM scores WHERE model = 'title-only';

-- 2. Demote jobs that were only "matched" due to title-only scoring
UPDATE jobs
SET status = 'scored'
WHERE status = 'matched'
  AND id NOT IN (SELECT job_id FROM scores WHERE score >= 60);

-- 3. Backfill posted_at for existing jobs that lack it
UPDATE jobs
SET posted_at = first_seen_at
WHERE posted_at IS NULL;
