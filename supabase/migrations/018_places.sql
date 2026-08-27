-- Canadian gazetteer, seeded from GeoNames (CC-BY 4.0) via
-- scripts/build_gazetteer.py -> data/places_ca.csv -> scripts/seed_places.py.
--
-- Jobs inherit a place centroid rather than carrying their own coordinates, so
-- "within 25 km" is a distance between a few thousand places, not per-job
-- geometry over every row. That keeps this free of PostGIS, earthdistance, and
-- any spatial index — relevant on a free tier whose 32MB maintenance_work_mem
-- already forced embeddings down to 256 dimensions.

CREATE TABLE IF NOT EXISTS places (
    slug          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    province      TEXT NOT NULL,
    province_name TEXT NOT NULL,
    latitude      DOUBLE PRECISION NOT NULL,
    longitude     DOUBLE PRECISION NOT NULL,
    population    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_places_province ON places (province);
CREATE INDEX IF NOT EXISTS idx_places_population ON places (population DESC);

-- Great-circle distance in kilometres. IMMUTABLE so it can be used in indexes
-- and inlined into the planner's estimates.
CREATE OR REPLACE FUNCTION km_between(
    lat1 DOUBLE PRECISION, lng1 DOUBLE PRECISION,
    lat2 DOUBLE PRECISION, lng2 DOUBLE PRECISION
) RETURNS DOUBLE PRECISION
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT 6371.0 * 2 * asin(sqrt(
      power(sin(radians(lat2 - lat1) / 2), 2)
    + cos(radians(lat1)) * cos(radians(lat2))
    * power(sin(radians(lng2 - lng1) / 2), 2)
  ));
$$;

ALTER TABLE places ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public read" ON places;
CREATE POLICY "Allow public read" ON places FOR SELECT USING (true);
