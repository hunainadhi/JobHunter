import json
import os
import traceback
from datetime import datetime, timezone

import httpx
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
MINIMAX_API_KEY = os.environ["MINIMAX_API_KEY"]
MINIMAX_API_URL = "https://api.minimax.io/v1/chat/completions"
CHUNK_INDEX = int(os.environ.get("CHUNK_INDEX", "0"))
TOTAL_CHUNKS = int(os.environ.get("TOTAL_CHUNKS", "1"))

BATCH_SIZE = 10
MATCH_THRESHOLD = 70

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
  MISMATCH: Java-only, C#/.NET-only, Go-only stacks with nothing else matching

SCORING RUBRIC (score 0-100):
1. ROLE TYPE FIT (35 points): Full-stack (Next.js/React/TS) = 35. AI/LLM app engineer (agents, RAG, embeddings) = 35. Backend/API (Node/Python/Postgres) = 28. Data engineer = 20. Non-dev roles (PM, QA manual, tech writer, DevOps-only, sales engineer) = 0-5.
2. SENIORITY FIT (30 points): 0-4 years experience, junior, new grad, entry level, or no explicit seniority = 30. "2+ years" or "1-3 years" or "3+ years" = 30. "5+ years" = 15. "7+ years", senior, staff, principal, lead, director = 0-5.
3. TECH STACK OVERLAP (20 points): Score based on DREAM TECH STACK tiers. Multiple TOP TIER matches = 20. Mix of GOOD TIER = 12-16. Only ACCEPTABLE TIER or generic = 6-10. No tech mentioned at all = 10 (neutral — don't penalize generic new-grad JDs). MISMATCH stack = 2-4.
4. KEYWORD RELEVANCE (15 points): Alignment with SaaS, full-stack, API development, cloud, CI/CD, AI/ML products, shipping culture, startup pace, greenfield development.

LOCATION RULE: If the role explicitly requires US-only presence or US work authorization with no indication of Canada hiring, deduct 30 points from the total score.

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
    "rationale": "one sentence explaining the score"
  }}
]"""

MUST_HAVE_ONE_OF = {
    "developer", "engineer", "dev", "development", "engineering",
    "full-stack", "fullstack", "full stack", "backend", "back-end",
    "frontend", "front-end", "data engineer", "software", "swe",
    "ai engineer", "ml engineer", "programmer", "platform engineer",
    "machine learning", "llm", "artificial intelligence",
    "generative ai", "genai",
}

NEGATIVE_SIGNALS = {
    "senior staff", "staff engineer", "principal", "director",
    "vp ", "vice president", "head of", "lead architect", "distinguished",
    "10+ years", "10 years", "8+ years", "8 years",
    "7+ years", "7 years",
    "intern", "internship", "co-op", "coop", "co op",
}


def passes_keyword_filter(title: str, description: str) -> bool:
    text = (title + " " + description).lower()
    has_role = any(kw in text for kw in MUST_HAVE_ONE_OF)
    if not has_role:
        return False
    has_negative = any(kw in text for kw in NEGATIVE_SIGNALS)
    if has_negative:
        return False
    return True


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


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Fetch all unscored job IDs to partition
    all_unscored = (
        supabase.table("jobs")
        .select("id")
        .eq("status", "new")
        .not_.is_("description", "null")
        .order("id")
        .limit(10000)
        .execute()
    ).data

    if not all_unscored:
        print(f"[chunk {CHUNK_INDEX}] No unscored jobs.")
        return

    # Partition by chunk
    chunk_size = len(all_unscored) // TOTAL_CHUNKS
    start = CHUNK_INDEX * chunk_size
    end = len(all_unscored) if CHUNK_INDEX == TOTAL_CHUNKS - 1 else start + chunk_size
    my_ids = [j["id"] for j in all_unscored[start:end]]

    if not my_ids:
        print(f"[chunk {CHUNK_INDEX}] No jobs in this chunk.")
        return

    print(f"[chunk {CHUNK_INDEX}] Processing {len(my_ids)} jobs (IDs {start}-{end} of {len(all_unscored)})")

    # Fetch full job data for our chunk
    scored = 0
    matched = 0
    filtered_out = 0
    errors = 0

    # Process in pages of 100
    for page_start in range(0, len(my_ids), 100):
        page_ids = my_ids[page_start:page_start + 100]

        resp = (
            supabase.table("jobs")
            .select("id, title, company_name, location, description")
            .in_("id", page_ids)
            .execute()
        )
        jobs = resp.data

        # Keyword pre-filter
        filtered_jobs = []
        for job in jobs:
            if passes_keyword_filter(job["title"], job.get("description") or ""):
                filtered_jobs.append(job)
            else:
                supabase.table("scores").upsert({
                    "job_id": job["id"],
                    "model": "keyword-filter",
                    "score": 0,
                    "rationale": "Failed keyword pre-filter",
                    "scored_at": datetime.now(timezone.utc).isoformat(),
                }, on_conflict="job_id,model").execute()
                supabase.table("jobs").update({
                    "status": "scored",
                    "description": None,
                }).eq("id", job["id"]).execute()
                filtered_out += 1

        # Score in batches of 10
        for i in range(0, len(filtered_jobs), BATCH_SIZE):
            batch = filtered_jobs[i:i + BATCH_SIZE]
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
                        "scored_at": datetime.now(timezone.utc).isoformat(),
                    }, on_conflict="job_id,model").execute()

                    supabase.table("jobs").update({
                        "status": new_status,
                        "description": None,
                    }).eq("id", job_id).execute()

                    scored += 1
                    if score >= MATCH_THRESHOLD:
                        matched += 1

            except Exception as e:
                errors += 1
                print(f"[chunk {CHUNK_INDEX}] Batch error: {e}")
                traceback.print_exc()

        if (page_start + 100) % 500 == 0:
            print(f"[chunk {CHUNK_INDEX}] Progress: {page_start + 100}/{len(my_ids)} | scored={scored} matched={matched} filtered={filtered_out}")

    print(f"[chunk {CHUNK_INDEX}] Done! scored={scored} matched={matched} filtered={filtered_out} errors={errors}")


if __name__ == "__main__":
    main()
