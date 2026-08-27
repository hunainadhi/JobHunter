-- Resolution cache keyed on the distinct raw location string.
--
-- 1,650 distinct strings back 10,777 jobs, so each string is resolved once and
-- reused. job_locations is a VIEW rather than stored rows: fixing a resolver
-- rule means re-resolving ~1,650 alias rows, and every job follows immediately
-- with no backfill pass and no way for a job to drift out of sync with the
-- alias that produced it.

CREATE TABLE IF NOT EXISTS location_aliases (
    raw_location     TEXT PRIMARY KEY,
    status           TEXT NOT NULL
                     CHECK (status IN ('resolved', 'countrywide', 'foreign', 'unresolved')),
    reason           TEXT,
    resolver_version INTEGER NOT NULL DEFAULT 1,
    resolved_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Many-to-many: one posting can name several places
-- ("Kitchener-Waterloo, ON; Toronto, ON").
CREATE TABLE IF NOT EXISTS location_alias_places (
    raw_location TEXT NOT NULL REFERENCES location_aliases(raw_location) ON DELETE CASCADE,
    place_slug   TEXT NOT NULL REFERENCES places(slug) ON DELETE CASCADE,
    PRIMARY KEY (raw_location, place_slug)
);

CREATE INDEX IF NOT EXISTS idx_location_alias_places_slug
    ON location_alias_places (place_slug);
CREATE INDEX IF NOT EXISTS idx_location_aliases_status
    ON location_aliases (status);

-- The view joins jobs to aliases on the raw text, so this index carries the join.
CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs (location);

CREATE OR REPLACE VIEW job_locations AS
SELECT
    j.id                                AS job_id,
    lap.place_slug                      AS place_slug,
    COALESCE(a.status, 'unresolved')    AS status
FROM jobs j
LEFT JOIN location_aliases a
       ON a.raw_location = j.location
LEFT JOIN location_alias_places lap
       ON lap.raw_location = a.raw_location;

ALTER TABLE location_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE location_alias_places ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public read" ON location_aliases;
CREATE POLICY "Allow public read" ON location_aliases FOR SELECT USING (true);
DROP POLICY IF EXISTS "Allow public read" ON location_alias_places;
CREATE POLICY "Allow public read" ON location_alias_places FOR SELECT USING (true);

-- Place counts for the autocomplete: only places that actually have jobs, so a
-- suggestion never leads to an empty result page.
CREATE OR REPLACE VIEW place_job_counts AS
SELECT
    p.slug, p.name, p.province, p.latitude, p.longitude,
    count(DISTINCT j.id) AS job_count
FROM places p
JOIN location_alias_places lap ON lap.place_slug = p.slug
JOIN location_aliases a        ON a.raw_location = lap.raw_location
JOIN jobs j                    ON j.location = a.raw_location
WHERE j.status <> 'expired'
GROUP BY p.slug, p.name, p.province, p.latitude, p.longitude;
