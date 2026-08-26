-- Track how many years of experience a posting demands and how much that
-- moved the final score, so sub-3-year roles can be favoured explicitly.
ALTER TABLE scores ADD COLUMN IF NOT EXISTS min_years_experience INTEGER;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS experience_adjustment INTEGER;

CREATE INDEX IF NOT EXISTS idx_scores_min_years_experience
    ON scores (min_years_experience);
