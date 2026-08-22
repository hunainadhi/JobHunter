-- Application ledger for autonomous JobHunter workflows.
-- Sensitive candidate profile data deliberately does not live in this schema.
-- The server-side service key is required for all reads and writes.

CREATE TABLE IF NOT EXISTS application_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    apply_url TEXT NOT NULL,
    source_url TEXT,
    match_score INTEGER CHECK (match_score >= 0 AND match_score <= 100),
    status TEXT NOT NULL DEFAULT 'discovered' CHECK (status IN (
        'discovered',
        'scored',
        'ready_to_apply',
        'submitted',
        'confirmation_uncertain',
        'assessment_requested',
        'interviewing',
        'rejected',
        'offer',
        'withdrawn',
        'blocked',
        'deferred'
    )),
    policy_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    application_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_materials JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_responses JSONB NOT NULL DEFAULT '{}'::jsonb,
    terms_url TEXT,
    terms_snapshot TEXT,
    submission_confirmation TEXT,
    submitted_at TIMESTAMPTZ,
    next_action_at TIMESTAMPTZ,
    next_action TEXT,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(job_id)
);

CREATE TABLE IF NOT EXISTS application_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES application_ledger(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_application_ledger_status_next_action
    ON application_ledger(status, next_action_at NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_application_ledger_company
    ON application_ledger(company_name);
CREATE INDEX IF NOT EXISTS idx_application_events_application
    ON application_events(application_id, created_at DESC);

ALTER TABLE application_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_events ENABLE ROW LEVEL SECURITY;

-- No anon policies. The application dashboard uses server actions with the
-- service-role key, keeping submitted materials and application history private.
