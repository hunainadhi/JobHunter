-- JobHunter initial schema

-- Raw scraped jobs
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ats_platform TEXT NOT NULL,
    ats_token TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    location TEXT,
    is_remote BOOLEAN DEFAULT false,
    description TEXT,
    apply_url TEXT NOT NULL,
    source_url TEXT,
    posted_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    content_hash TEXT,
    status TEXT DEFAULT 'new' CHECK (status IN ('new', 'scored', 'matched', 'expired')),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(ats_platform, external_id)
);

-- LLM match scores
CREATE TABLE IF NOT EXISTS scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    model TEXT DEFAULT 'MiniMax-M3',
    score INTEGER CHECK (score >= 0 AND score <= 100),
    role_fit_score INTEGER,
    seniority_fit_score INTEGER,
    stack_overlap_score INTEGER,
    keyword_score INTEGER,
    matched_skills JSONB,
    rationale TEXT,
    scored_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(job_id, model)
);

-- Blacklisted companies
CREATE TABLE IF NOT EXISTS blacklisted_companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL,
    ats_token TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(company_name)
);

-- Scrape run health tracking
CREATE TABLE IF NOT EXISTS scrape_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ats_platform TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT CHECK (status IN ('running', 'success', 'partial_failure', 'failure')),
    companies_scraped INTEGER DEFAULT 0,
    jobs_found INTEGER DEFAULT 0,
    jobs_new INTEGER DEFAULT 0,
    error_log TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_scores_score ON scores(score DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_platform ON scrape_runs(ats_platform, started_at DESC);
