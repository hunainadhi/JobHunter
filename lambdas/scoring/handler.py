import json
import os
import traceback
from datetime import datetime, timezone

import boto3
import httpx
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
MINIMAX_API_KEY = os.environ["MINIMAX_API_KEY"]
MINIMAX_API_URL = "https://api.minimax.io/v1/chat/completions"
BATCH_SIZE = 10
MATCH_THRESHOLD = 25

SYSTEM_PROMPT = """You are a job-resume matching engine. You score how well a job posting matches a candidate's profile.

CANDIDATE PROFILE:
- Name: Hunain Adhikari
- Location: Waterloo, Ontario, Canada
- Work Authorization: PGWP open work permit (CANADA ONLY — cannot work for US-only employers)
- Experience: ~2.5 years professional (targeting 0-4 year roles)
- Education: Master of Applied Computing (WLU, 2025, 4.0 GPA), B.Tech IT (Mumbai University, 2021)
- Certifications: AWS Certified Cloud Practitioner (CLF-C02)
- Identity: AI Engineer | Software Developer | Solo SaaS Builder | 2x Hackathon Winner
- Work History:
  - Software Developer at Enzuzo (TypeScript, REST APIs, Docker, privacy-compliance SaaS — cut incorrect script executions by 80%)
  - Software Engineer at Barclays (2 years, Ab Initio ETL pipelines, Oracle SQL, Jenkins, TWS — $4B+ credit card transactions, 5M+ daily records, cut batch processing by 33%)
  - Instructor Assistant at WLU (HTML/CSS/JS, ARM assembly)
- Shipped Products (live, not homework):
  - MirrorLog (mirrorlog.org): Live SaaS — Next.js, TypeScript, Supabase, Prisma, Stripe, Clerk, Claude API
  - MirrorAgent: Shipped macOS desktop app — Electron, React, TypeScript, Claude Vision, Chrome extensions, WebSocket
  - Lex Harvester: Legal research agent — FastAPI, PostgreSQL, pgvector, MiniLM embeddings (EvenUp hackathon runner-up)
- Hackathon Wins: EvenUp x OpenClaw runner-up, Amazon Robotics Day 1st place (beat 15+ teams)
- Skills: TypeScript, JavaScript, Python, C++, Next.js, React, Node.js, FastAPI, PostgreSQL, Ab Initio, Docker, AWS, Jenkins, Git

ROLE PRIORITY (what the candidate wants most):
1. Full-stack developer (Next.js/React/TypeScript) — TOP PRIORITY
2. AI/LLM application engineer (agents, RAG, embeddings, LLM API integrations) — TOP PRIORITY (equal to full-stack)
3. Backend/API engineer (Node.js, Python/FastAPI, PostgreSQL)
4. Data engineer (ETL pipelines, SQL — acceptable but not preferred)

DREAM TECH STACK (use for TECH STACK OVERLAP scoring):
  TOP TIER: LLM APIs, vector databases, RAG, embeddings, agents, TypeScript, Next.js, React
  GOOD TIER: Python, FastAPI, Django, Node.js, AWS, GCP, PostgreSQL, Docker
  ACCEPTABLE TIER: Ab Initio, ETL pipelines, generic cloud mentions
  TRANSFERABLE: Vue.js, Angular, Svelte, Flask, Ruby on Rails, PHP/Laravel (similar paradigms to candidate's stack)
  MISMATCH: Java-only, C#/.NET-only, Go-only stacks with nothing else matching

SCORING RUBRIC (score 0-100):
1. ROLE TYPE FIT (35 points): Full-stack (Next.js/React/TS) = 35. AI/LLM app engineer (agents, RAG, embeddings) = 35. Backend/API (Node/Python/Postgres) = 28. Data engineer = 20. QA/test developer or SDET (writes code, automates tests) = 18-22. Non-dev roles (PM, tech writer, DevOps-only, sales engineer, pure manual QA with no coding) = 0-5.
2. SENIORITY FIT (30 points): 0-4 years experience, junior, new grad, entry level, or no explicit seniority = 30. "2+ years" or "1-3 years" or "3+ years" = 30. "5+ years" = 15. "7+ years", senior, staff, principal, lead, director = 0-5.
3. TECH STACK OVERLAP (20 points): Score based on DREAM TECH STACK tiers. Multiple TOP TIER matches = 20. Mix of GOOD TIER = 12-16. TRANSFERABLE frameworks (Vue.js, Angular, etc.) = 10-14 (skills transfer easily). Only ACCEPTABLE TIER or generic = 6-10. No tech mentioned at all = 10 (neutral — don't penalize generic new-grad JDs). MISMATCH stack = 2-4.
4. KEYWORD RELEVANCE (15 points): Alignment with SaaS, full-stack, API development, cloud, CI/CD, AI/ML products, shipping culture, startup pace, greenfield development.

LOCATION RULE: If the role explicitly requires US-only presence or US work authorization with no indication of Canada hiring, deduct 30 points from the total score.

JOB CATEGORY — Classify each job into exactly ONE of these categories based on the title and description:
- Software & Engineering
- Data & Analytics
- Design & Creative
- Product & Project Management
- Business & Operations
- Sales & Marketing
- Finance & Accounting
- Healthcare
- Human Resources
- Skilled Trades & Labor
- Education & Research
- Other

EXPERIENCE LEVEL — Classify each job into exactly ONE level based on title, description, and years of experience required:
- intern (internship, co-op, work term, practicum)
- entry (new grad, junior, 0-2 years, entry-level, associate, no experience required)
- mid (intermediate, 2-5 years, no explicit seniority mentioned but requires some experience)
- senior (senior, staff, lead, principal, architect, director, head, VP, 5+ years, manager-level IC or above)

You MUST respond ONLY with a valid JSON array. No other text."""

BATCH_USER_PROMPT = """Score these job postings:

{jobs_block}

Respond with ONLY a JSON array:
[
  {{
    "job_id": "the job id",
    "score": 0-100,
    "role_fit": 0-35,
    "seniority_fit": 0-30,
    "stack_overlap": 0-20,
    "keyword_match": 0-15,
    "matched_skills": ["skill1", "skill2"],
    "rationale": "one sentence explaining the score",
    "category": "one of the 12 categories from JOB CATEGORY list",
    "level": "one of: intern, entry, mid, senior"
  }}
]"""

def build_jobs_block(jobs: list[dict]) -> str:
    block = ""
    for job in jobs:
        desc = (job.get("description") or "")[:6000]
        block += f"""
[JOB {job['id']}]
Title: {job['title']}
Company: {job['company_name']}
Location: {job.get('location', 'Unknown')}
Description: {desc}
---
"""
    return block


def score_batch(jobs: list[dict]) -> list[dict]:
    jobs_block = build_jobs_block(jobs)
    payload = {
        "model": "MiniMax-M3",
        "max_tokens": 2000,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": BATCH_USER_PROMPT.format(jobs_block=jobs_block)},
        ],
        "thinking": {"type": "disabled"},
    }

    with httpx.Client(timeout=90) as client:
        response = client.post(
            MINIMAX_API_URL,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    result = response.json()
    text = result["choices"][0]["message"]["content"]
    clean = text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(clean)


def lambda_handler(event, context):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Fetch unscored jobs
    resp = (
        supabase.table("jobs")
        .select("id, title, company_name, location, description")
        .eq("status", "new")
        .not_.is_("description", "null")
        .order("first_seen_at", desc=True)
        .limit(500)
        .execute()
    )

    all_jobs = resp.data

    # Claim this batch by marking as 'scoring' so other instances skip them
    if all_jobs:
        claimed_ids = [job["id"] for job in all_jobs]
        for job_id in claimed_ids:
            supabase.table("jobs").update({"status": "scoring"}).eq("id", job_id).eq("status", "new").execute()

    # Discard jobs with no description — mark as scored so they get purged
    null_desc_resp = (
        supabase.table("jobs")
        .select("id")
        .eq("status", "new")
        .is_("description", "null")
        .limit(500)
        .execute()
    )
    discarded_count = len(null_desc_resp.data)
    for job in null_desc_resp.data:
        supabase.table("jobs").update({"status": "scored"}).eq("id", job["id"]).execute()

    if discarded_count > 0:
        print(f"Discarded {discarded_count} jobs with no description")

    if not all_jobs and not null_desc_resp.data:
        return {"statusCode": 200, "body": json.dumps({"status": "no unscored jobs"})}

    stats = {
        "total_unscored": len(all_jobs),
        "scored": 0,
        "matched": 0,
        "errors": [],
    }

    for i in range(0, len(all_jobs), BATCH_SIZE):
        batch = all_jobs[i : i + BATCH_SIZE]
        try:
            results = score_batch(batch)

            job_id_map = {str(j["id"]): j for j in batch}

            for result in results:
                job_id = result.get("job_id")
                if job_id not in job_id_map:
                    continue

                score = result.get("score", 0)
                new_status = "matched" if score >= MATCH_THRESHOLD else "scored"

                supabase.table("scores").upsert({
                    "job_id": job_id,
                    "model": "MiniMax-M3",
                    "score": score,
                    "role_fit_score": result.get("role_fit"),
                    "seniority_fit_score": result.get("seniority_fit"),
                    "stack_overlap_score": result.get("stack_overlap"),
                    "keyword_score": result.get("keyword_match"),
                    "matched_skills": result.get("matched_skills", []),
                    "rationale": result.get("rationale"),
                    "category": result.get("category"),
                    "level": result.get("level"),
                    "scored_at": datetime.now(timezone.utc).isoformat(),
                }, on_conflict="job_id,model").execute()

                supabase.table("jobs").update({
                    "status": new_status,
                    "description": None,
                }).eq("id", job_id).execute()

                stats["scored"] += 1
                if score >= MATCH_THRESHOLD:
                    stats["matched"] += 1

        except Exception as e:
            stats["errors"].append(f"Batch {i//BATCH_SIZE}: {str(e)[:200]}")
            print(f"Scoring batch failed: {e}")
            traceback.print_exc()

    # Reset any claimed jobs that weren't scored (failed batches or early exit)
    claimed_ids = [job["id"] for job in all_jobs]
    if claimed_ids:
        supabase.table("jobs").update({"status": "new"}).eq("status", "scoring").in_("id", claimed_ids).execute()

    # Self-chain if there are more unscored jobs
    remaining = (
        supabase.table("jobs")
        .select("id", count="exact")
        .eq("status", "new")
        .not_.is_("description", "null")
        .limit(1)
        .execute()
    )
    remaining_count = remaining.count or 0
    print(f"Scoring complete. matched={stats['matched']} scored={stats['scored']} discarded_no_desc={discarded_count} remaining={remaining_count}")

    if remaining_count > 0:
        print(f"Re-invoking scoring for {remaining_count} remaining jobs")
        boto3.client("lambda", region_name="ca-central-1").invoke(
            FunctionName=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "jobhunter-scoring"),
            InvocationType="Event",
        )

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "complete", "stats": stats, "remaining": remaining_count}, default=str),
    }
