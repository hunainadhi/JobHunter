-- Remove public (anon) write access to blacklisted_companies.
-- The anon key ships to every browser, so these policies let any visitor
-- insert/delete blacklist rows and wipe the dashboard. Writes now go through
-- server-side code using the service-role key (which bypasses RLS).

DROP POLICY IF EXISTS "Allow public insert" ON blacklisted_companies;
DROP POLICY IF EXISTS "Allow public delete" ON blacklisted_companies;
