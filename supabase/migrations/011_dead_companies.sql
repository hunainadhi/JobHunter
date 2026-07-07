CREATE TABLE IF NOT EXISTS dead_companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ats_platform TEXT NOT NULL,
    ats_token TEXT NOT NULL,
    error_type TEXT NOT NULL CHECK (error_type IN ('not_found', 'server_error')),
    fail_count INTEGER DEFAULT 1,
    last_error TEXT,
    last_failed_at TIMESTAMPTZ DEFAULT now(),
    retry_after TIMESTAMPTZ,
    UNIQUE(ats_platform, ats_token)
);
CREATE INDEX IF NOT EXISTS idx_dead_companies_lookup ON dead_companies(ats_platform, ats_token);
