-- Enable RLS on all tables
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE blacklisted_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE scrape_runs ENABLE ROW LEVEL SECURITY;

-- Allow public read access (personal tool, no auth needed)
CREATE POLICY "Allow public read" ON jobs FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON scores FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON blacklisted_companies FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON scrape_runs FOR SELECT USING (true);

-- Allow public insert/delete on blacklisted_companies (for Block/Unblock from dashboard)
CREATE POLICY "Allow public insert" ON blacklisted_companies FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public delete" ON blacklisted_companies FOR DELETE USING (true);
