# JobHunter

An automated job discovery and AI scoring platform that scrapes thousands of job postings across 9 sources, scores them against a candidate profile using an OpenRouter model, and surfaces the best matches on a live dashboard. Infrastructure runs on free tiers; AI usage is pay-as-you-go.

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
                                                  │  (OpenRouter)    │
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
4. The **Scoring Lambda** picks up unscored jobs, sends them in batches of 10 to OpenRouter, writes scores, nulls descriptions (to save storage), and self-chains until all jobs are processed
5. The **Next.js dashboard** queries Supabase in real time and displays matched jobs with scores

## Features

- **12 job sources**: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Rippling, iCIMS, Pinpoint, Teamtailor, Breezy, YC Work at a Startup, WeWorkRemotely
- **16,700+ companies** tracked via curated CSV lists (expanded using Common Crawl index API)
- **AI scoring**: Every job scored 0-100 across 4 categories using an OpenRouter LLM
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
| **AI Scoring** | OpenRouter (`qwen/qwen3-30b-a3b` by default) |
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
│   │   └── handler.py            # OpenRouter scoring with detailed rubric
│   └── layer/                    # Lambda layer (dependencies)
├── supabase/
│   └── migrations/
│       ├── 001_initial_schema.sql
│       ├── 002_pg_cron_cleanup.sql
│       ├── 003_rls_policies.sql
│       └── 004_purge_guardrails.sql
├── scripts/
│   ├── discover_companies.py     # Company discovery agent (Common Crawl + ATS API validation)
│   ├── ingest.py                 # Local ingestion (chunked)
│   ├── score.py                   # Local scoring with keyword pre-filter
│   ├── backfill_embeddings.py     # Embedding backfill (90 RPM rate-limited)
│   ├── backfill_descriptions.py  # Re-fetch missing descriptions
│   ├── run_ingestion_local.py    # Local ingestion testing
│   ├── run_scoring_local.py      # Local scoring testing
│   └── test_openrouter.py        # OpenRouter API testing
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
- OpenRouter API key

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
OPENROUTER_API_KEY=your-openrouter-key  # scoring only
OPENROUTER_MODEL=qwen/qwen3-30b-a3b
```

Set the same `OPENROUTER_MODEL` value in the dashboard environment if you change it, so score and category filters continue to target the active scorer.

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

#### Company Discovery Agent

The discovery agent (`scripts/discover_companies.py`) automatically finds new companies hiring in Canada across all ATS platforms. It works in two phases:

1. **Discovery** — Queries the [Common Crawl Index API](https://index.commoncrawl.org/) to find company slugs from crawled ATS career page URLs (e.g., `boards.greenhouse.io/{slug}`, `jobs.lever.co/{slug}`, `{slug}.breezy.hr`)
2. **Validation** — For each new slug, queries the platform's public ATS API to verify the company board is active and checks for Canadian job postings using the same location filter as the ingestion pipeline

Supported platforms and discovery methods:

| Platform | Slug Source | Validation API | Canada Check |
|---|---|---|---|
| Greenhouse | URL path (`boards.greenhouse.io/{slug}`) | Board Jobs API | Yes |
| Lever | URL path (`jobs.lever.co/{slug}`) | Postings API | Yes |
| Ashby | URL path (`jobs.ashbyhq.com/{slug}`) | Posting API (POST) | Yes |
| SmartRecruiters | URL path (`careers.smartrecruiters.com/{slug}`) | Jobs API | Yes |
| Workable | URL path (`apply.workable.com/{slug}`) | Jobs API | Yes |
| Teamtailor | Subdomain (`{slug}.teamtailor.com`) | Board page check | No |
| Breezy | Subdomain (`{slug}.breezy.hr`) | Board page check | No |
| Pinpoint | Subdomain (`{slug}.pinpointhq.com`) | Board page check | No |
| iCIMS | Subdomain (`careers-{slug}.icims.com`) | Board page check | No |

Usage:

```bash
# Discover + validate all platforms (appends new companies to CSVs)
python scripts/discover_companies.py

# Only discover specific platforms
python scripts/discover_companies.py --platforms greenhouse,lever,ashby

# Preview without modifying CSVs
python scripts/discover_companies.py --dry-run

# Add all discovered slugs without validation (faster, less targeted)
python scripts/discover_companies.py --skip-validation

# Limit URLs processed per domain (useful for testing)
python scripts/discover_companies.py --limit 500 --max-pages 3

# Show every company validation result
python scripts/discover_companies.py --verbose
```

The agent uses the latest Common Crawl index automatically. Coverage varies by crawl — run periodically to catch new companies as indexes are published. Companies with Canadian job postings are flagged in the output summary.

You can also discover companies manually using Common Crawl:

```bash
# Example: find Greenhouse companies
curl "https://index.commoncrawl.org/CC-MAIN-2025-08-index?url=boards.greenhouse.io/*&output=json&fl=url" \
  | jq -r '.url' | sed 's|https://boards.greenhouse.io/||' | sort -u
```

### Dashboard Threshold

The dashboard shows jobs with an overall AI score > 60. Change this in `app/app/page.tsx`:

```typescript
.gt("score", 60)  // adjust threshold here
```

## How Scoring Works

Each job is sent to the configured OpenRouter model with the candidate's full profile. The LLM returns a structured JSON response:

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
| OpenRouter | Pay-as-you-go | Varies by model and usage |
| **Total** | | Infrastructure $0; AI usage varies |

## License

MIT
