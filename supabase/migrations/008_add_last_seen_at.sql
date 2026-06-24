ALTER TABLE jobs ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT now();

-- Backfill: set last_seen_at = first_seen_at for existing jobs
UPDATE jobs SET last_seen_at = first_seen_at WHERE last_seen_at IS NULL;
