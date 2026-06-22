# JobHunter

An automated job discovery and AI scoring platform that scrapes thousands of job postings across 9 sources, scores them against a candidate profile using MiniMax-M3, and surfaces the best matches on a live dashboard. Runs entirely on free-tier infrastructure at **$0/month**.

## Architecture

```
EventBridge (4x/day)
       |
       v
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Orchestrator   │────>│  Ingestion Workers│────>│    Supabase     │
│    (Lambda)      │     │   (Lambda x ~420) │     │  (PostgreSQL)   │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          v
                                                 ┌─────────────────┐
                                                 │  Scoring Lambda  │
                                                 │  (MiniMax-M3)    │
                                                 └────────┬────────┘
                                                          │
                                                          v
                                                 ┌─────────────────┐
                                                 │  Next.js Dashboard│
                                                 │   (Vercel)       │
                                                 └─────────────────┘
```

### Data Flow

1. **EventBridge** triggers the **Orchestrator Lambda** on a schedule (4x/day)
2. The orchestrator reads company CSVs and launches **~420 ingestion workers** asynchronously (batches of 40 companies each)
3. Each worker scrapes jobs using [`jobhive`](https://github.com/kalil0321/ats-scrapers), enriches descriptions, filters for Canadian locations, and upserts to Supabase
4. The **Scoring Lambda** picks up unscored jobs, sends them in batches of 10 to MiniMax-M3, writes scores, nulls descriptions (to save storage), and self-chains until all jobs are processed
5. The **Next.js dashboard** queries Supabase in real time and displays matched jobs with scores

## Features

- **9 job sources**: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Rippling, YC Work at a Startup, TheMuse, WeWorkRemotely
- **16,700+ companies** tracked via curated CSV lists (expanded using Common Crawl index API)
- **AI scoring**: Every job scored 0-100 across 4 categories using MiniMax-M3 LLM
  - **Role Fit** (/35) — how well the role type matches the candidate profile
  - **Seniority Fit** (/30) — experience level alignment
  - **Stack Overlap** (/20) — tech stack match against dream stack
  - **Keyword Relevance** (/15) — alignment with target industries and culture
- **Canada location filter** — only Canadian jobs pass through (respects PGWP work authorization)
- **Company blacklisting** — block companies directly from the dashboard
- **Health monitoring** — per-ATS health indicators with last scrape timestamps
- **Description enrichment** — fallback `enrich_descriptions()` ensures no job is scored without context
- **Self-healing scoring** — Lambda self-chains to process all unscored jobs automatically
- **Automatic cleanup** — pg_cron purges expired jobs and old scrape runs

## Tech Stack

| Layer | Technology |
|---|---|
| **Scraping** | Python, [jobhive](https://github.com/kalil0321/ats-scrapers), httpx |
| **AI Scoring** | MiniMax-M3 (chat completions API) |
| **Compute** | AWS Lambda (Python 3.12, ARM64), EventBridge |
| **Database** | Supabase (PostgreSQL), pg_cron |
| **Dashboard** | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| **Hosting** | Vercel (dashboard), AWS Lambda (backend) |
| **Company Discovery** | Common Crawl Index API |

## Project Structure

```
JobHunter/
├── app/                          # Next.js dashboard (Vercel)
│   ├── app/
│   │   ├── page.tsx              # Main dashboard — jobs table with scores
│   │   ├── layout.tsx            # Root layout (dark theme)
│   │   ├── stats/                # Pipeline statistics page
│   │   └── blacklist/            # Blocked companies management
│   ├── components/
│   │   ├── job-table.tsx         # Sortable, paginated job table with 5 score columns
│   │   ├── health-banner.tsx     # Per-ATS health status indicators
│   │   ├── block-button.tsx      # Company block action
│   │   └── unblock-button.tsx    # Company unblock action
│   └── lib/
│       ├── supabase.ts           # Supabase client
│       └── actions.ts            # Server actions (block/unblock)
├── lambdas/
│   ├── ingestion/
│   │   ├── handler.py            # Ingestion worker — scrapes a batch of companies
│   │   ├── orchestrator.py       # Launches all ingestion workers
│   │   ├── location_filter.py    # Canadian location detection
│   │   └── data/                 # Company slug CSVs per ATS platform
│   │       ├── greenhouse.csv    # 4,983 companies
│   │       ├── workable.csv      # 4,304 companies
│   │       ├── ashby.csv         # 2,877 companies
│   │       ├── smartrecruiters.csv # 2,275 companies
│   │       ├── lever.csv         # 2,118 companies
│   │       └── rippling.csv      # 196 companies
│   ├── scoring/
│   │   └── handler.py            # MiniMax-M3 scoring with detailed rubric
│   └── layer/                    # Lambda layer (dependencies)
├── supabase/
│   └── migrations/
│       ├── 001_initial_schema.sql
│       ├── 002_pg_cron_cleanup.sql
│       ├── 003_rls_policies.sql
│       └── 004_purge_guardrails.sql
├── scripts/
│   ├── run_ingestion_local.py    # Local ingestion testing
│   ├── run_scoring_local.py      # Local scoring testing
│   └── test_minimax.py           # MiniMax API testing
├── deploy.sh                     # Build layer + deploy all Lambdas
└── BUILD_PLAN.md                 # Original 5-iteration build plan
```

## Database Schema

**4 tables** in Supabase:

- **`jobs`** — scraped job postings (title, company, location, description, status, ATS metadata). Unique on `(ats_platform, external_id)`. Status lifecycle: `new` -> `scored`/`matched` -> `expired`
- **`scores`** — AI scores per job (overall score, 4 sub-scores, matched skills, rationale). Unique on `(job_id, model)`. Cascades on job deletion
- **`blacklisted_companies`** — user-blocked companies, filtered out of dashboard results
- **`scrape_runs`** — health tracking per ingestion run (platform, timing, job counts, errors)

## Setup

### Prerequisites

- Node.js 18+
- Python 3.12+
- AWS CLI configured with appropriate permissions
- Supabase project
- MiniMax API key (Plus tier for free M3 access)

### 1. Database

Create a Supabase project and run the migrations in order:

```bash
# Apply via Supabase dashboard SQL editor or CLI
psql $DATABASE_URL < supabase/migrations/001_initial_schema.sql
psql $DATABASE_URL < supabase/migrations/002_pg_cron_cleanup.sql
psql $DATABASE_URL < supabase/migrations/003_rls_policies.sql
psql $DATABASE_URL < supabase/migrations/004_purge_guardrails.sql
```

### 2. Lambda Functions

Create 3 Lambda functions in AWS (Python 3.12, ARM64):

| Function | Memory | Timeout | Handler |
|---|---|---|---|
| `jobhunter-orchestrator` | 256 MB | 60s | `orchestrator.lambda_handler` |
| `jobhunter-ingestion` | 512 MB | 900s | `handler.lambda_handler` |
| `jobhunter-scoring` | 256 MB | 900s | `handler.lambda_handler` |

Set environment variables on ingestion and scoring Lambdas:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
MINIMAX_API_KEY=your-minimax-key        # scoring only
```

Deploy:

```bash
./deploy.sh
```

### 3. Dashboard

```bash
cd app
npm install
```

Create `app/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-key
```

Run locally:

```bash
npm run dev
```

Deploy to Vercel by connecting the `app/` directory to a Vercel project.

### 4. Scheduling

Set up EventBridge to trigger the orchestrator Lambda on your preferred schedule (e.g., 4x/day):

```
cron(0 13,16,20,0 * * ? *)   # 9am, 12pm, 4pm, 8pm ET
```

## Customization

### Candidate Profile

Edit the `SYSTEM_PROMPT` in `lambdas/scoring/handler.py` to match your own resume, skills, role priorities, and dream tech stack. The scoring rubric is fully customizable:

- **Role Type Fit** (35 pts) — define which role types score highest for you
- **Seniority Fit** (30 pts) — set your experience range
- **Tech Stack Overlap** (20 pts) — define your dream, good, acceptable, and transferable tech tiers
- **Keyword Relevance** (15 pts) — set industry and culture keywords

### Adding Companies

Add company slugs to the CSV files in `lambdas/ingestion/data/`. Each CSV has a `slug` column matching the company's ATS URL identifier.

You can discover new companies programmatically using Common Crawl:

```bash
# Example: find Greenhouse companies
curl "https://index.commoncrawl.org/CC-MAIN-2025-08-index?url=boards.greenhouse.io/*&output=json&fl=url" \
  | jq -r '.url' | sed 's|https://boards.greenhouse.io/||' | sort -u
```

### Dashboard Threshold

The dashboard shows jobs with overall MiniMax score > 60. Change this in `app/app/page.tsx`:

```typescript
.gt("score", 60)  // adjust threshold here
```

## How Scoring Works

Each job is sent to MiniMax-M3 with the candidate's full profile. The LLM returns a structured JSON response:

```json
{
  "job_id": "uuid",
  "score": 82,
  "role_fit": 30,
  "seniority_fit": 28,
  "stack_overlap": 14,
  "keyword_match": 10,
  "matched_skills": ["TypeScript", "React", "Next.js", "AWS"],
  "rationale": "Strong full-stack match with AI features, junior-friendly"
}
```

The dashboard normalizes each sub-score to /100 for easy comparison:
- Role: raw/35 * 100
- Seniority: raw/30 * 100
- Stack: raw/20 * 100
- Keywords: raw/15 * 100

Jobs scoring below 25 overall are marked as `scored` (not shown). Jobs at 25+ are marked `matched`. The dashboard further filters to show only scores > 60.

## Cost

| Service | Tier | Monthly Cost |
|---|---|---|
| AWS Lambda | Free tier (1M requests) | $0 |
| Supabase | Free tier (500 MB, 50K rows) | $0 |
| Vercel | Hobby (100 GB bandwidth) | $0 |
| MiniMax | Plus tier (~1.7B tokens/month) | $0 |
| **Total** | | **$0** |

## License

MIT
