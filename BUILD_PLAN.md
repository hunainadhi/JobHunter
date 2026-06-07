# JobHunter — Build Plan

5 iterations, each ending with a manually testable checkpoint.

---

## Iteration 1: Foundation
**Goal:** Skeleton is alive. Supabase has the schema. Next.js loads dark.

### Tasks
- [ ] Initialize Next.js 14 project in `app/` (App Router, TypeScript, Tailwind)
- [ ] Install and configure shadcn/ui + next-themes (forced dark mode)
- [ ] Create `.env` + `.env.example` with all required keys
- [ ] Write `supabase/migrations/001_initial_schema.sql` (jobs, scores, blacklisted_companies, scrape_runs)
- [ ] Run migration against Supabase project
- [ ] Set up pg_cron cleanup jobs in Supabase
- [ ] Scaffold Lambda directory structure (`lambdas/ingestion/`, `lambdas/scoring/`)
- [ ] Write `deploy.sh` (zip + aws lambda update-function-code for each function)
- [ ] Create both Lambda functions in AWS console (Python 3.12, ARM64, correct memory/timeout)
- [ ] Create Lambda layer with dependencies (httpx, jobhive, rapidfuzz, supabase)

### ✅ Checkpoint 1 Test
- `npm run dev` → `localhost:3000` loads with black background, no errors
- Supabase dashboard shows all 4 tables with correct columns
- `./deploy.sh` runs without errors (even with empty Lambda handlers)
- Both Lambda functions visible in AWS console

---

## Iteration 2: Ingestion Pipeline
**Goal:** Lambda scrapes real Canadian jobs into Supabase. Verifiable in the DB.

### Tasks
- [ ] Implement ingestion Lambda handler (`lambdas/ingestion/handler.py`)
  - Read `blacklisted_companies` from Supabase at startup
  - Iterate jobhive scrapers for Greenhouse, Lever, Ashby
  - Apply Canadian location filter (`country_iso` → string match fallback)
  - Skip blacklisted companies
  - Upsert jobs to Supabase `jobs` table (UNIQUE on ats_platform + external_id)
  - Write a `scrape_runs` record (started_at, completed_at, status, jobs_found, jobs_new)
  - Fire Scoring Lambda via boto3 async invoke
- [ ] Write `scripts/run_ingestion_local.py` — invoke ingestion locally for testing
- [ ] Deploy ingestion Lambda via `deploy.sh`

### ✅ Checkpoint 2 Test
- Run `python scripts/run_ingestion_local.py`
- Check Supabase `jobs` table: rows exist, all locations are Canadian
- Check `scrape_runs` table: one row with `status = 'success'`, `jobs_found > 0`
- Re-run: `jobs_new = 0` (dedup working — no duplicates inserted)
- Spot-check 5 random jobs: open `apply_url` — they all load real job pages

---

## Iteration 3: Scoring Pipeline
**Goal:** Unscored jobs get MiniMax scores. Descriptions get nulled. Matched jobs flagged.

### Tasks
- [ ] Implement scoring Lambda handler (`lambdas/scoring/handler.py`)
  - Read unscored jobs (status='new') from Supabase
  - Run keyword pre-filter — skip obvious non-matches
  - Batch 15 jobs → MiniMax-M3 (`thinking: {"type": "disabled"}`)
  - Write scores to `scores` table
  - NULL out `description` on each scored job
  - Set `status = 'matched'` on jobs with score >= 70, `status = 'scored'` otherwise
- [ ] Write `scripts/run_scoring_local.py` — invoke scoring locally for testing
- [ ] Deploy scoring Lambda via `deploy.sh`

### ✅ Checkpoint 3 Test
- After Checkpoint 2 ingestion run, trigger `python scripts/run_scoring_local.py`
- Check `scores` table: rows exist, scores are between 0-100
- Check `jobs` table: `description` column is NULL on scored rows
- Check `jobs` table: jobs with score >= 70 have `status = 'matched'`
- Spot-check 5 matched jobs manually: do the scores make sense? (Junior dev roles should be 75+, senior roles should be <30)
- Confirm job-002-style (Senior Staff) scores are below 40

---

## Iteration 4: Dashboard
**Goal:** Open a URL and see your matched jobs. Block a company. Browse the blacklist.

### Tasks
- [ ] Build main dashboard page (`app/page.tsx`) — Server Component
  - Query Supabase: jobs JOIN scores WHERE score >= 70, not blacklisted, first_seen_at within 2 weeks
  - Sort by first_seen_at DESC
  - shadcn DataTable: Title, Company, Score, Location, Apply columns
  - Score color coding (70-79 muted, 80-89 blue, 90+ green)
  - Pagination (25/page)
  - "Apply" button opens apply_url in new tab
- [ ] Add health banner (queries `scrape_runs` — last success per ATS, green/yellow/red pills)
- [ ] Add hover "Block" button on company column → Server Action → inserts to `blacklisted_companies`
- [ ] Build blacklist page (`app/blacklist/page.tsx`) — list of blocked companies with "Unblock" button
- [ ] Add `/api/health` route (lightweight Supabase ping for keep-alive)
- [ ] Deploy to Vercel, enable password protection

### ✅ Checkpoint 4 Test
- Open Vercel URL → password prompt → enter password → dashboard loads
- Jobs table shows matched jobs sorted by newest first
- Click "Apply" on any job → correct ATS page opens in new tab
- Click "Block" on a company → page refreshes → company gone from results
- Visit `/blacklist` → blocked company appears with "Unblock" button
- Click "Unblock" → company reappears in main dashboard
- Health banner shows last scrape time and green pills for each ATS

---

## Iteration 5: Full Automation
**Goal:** You do nothing. Cron fires 4x/day. Dashboard updates itself.

### Tasks
- [ ] Add `/api/trigger-sync` Vercel route (validates auth header, invokes Ingestion Lambda via boto3)
- [ ] Set `LAMBDA_FUNCTION_URL` / `SCORING_FUNCTION_NAME` env vars in Vercel dashboard
- [ ] Create 4 cron jobs on cron-jobs.org (9am/12pm/4pm/8pm ET) pointing to `/api/trigger-sync`
- [ ] Create keep-alive cron job on cron-jobs.org (6am daily → `/api/health`)
- [ ] Configure cron-jobs.org auth header (`Authorization: Bearer {SYNC_SECRET}`)
- [ ] Set failure email alerts on cron-jobs.org (3+ consecutive failures)
- [ ] Verify Vercel route returns immediately (fire-and-forget, <30s response)
- [ ] Run 48 hours unattended

### ✅ Checkpoint 5 Test
- Wait for the 9am cron to fire
- Check cron-jobs.org logs: HTTP 200, response < 5 seconds
- Check `scrape_runs` table: new row with today's timestamp
- Check dashboard: new jobs appeared since yesterday
- Manually break the MiniMax API key temporarily → health banner turns yellow/red
- Restore key → next run turns green again
- **Done:** Tool runs fully unattended. Just check the dashboard.

---

## Summary

| Iteration | What You Build | How You Test |
|---|---|---|
| 1 | Schema + scaffolding | Dashboard loads, tables exist in Supabase |
| 2 | Ingestion Lambda | Real Canadian jobs appear in DB |
| 3 | Scoring Lambda | Jobs get scored, descriptions nulled |
| 4 | Next.js dashboard | See jobs, block companies, check health |
| 5 | Cron automation | Sits unattended for 48h, works on its own |
