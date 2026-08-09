import json
import os
import traceback
from datetime import datetime, timezone

import boto3
import httpx
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
SCORING_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3-30b-a3b")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
BATCH_SIZE = 10
MATCH_THRESHOLD = 25
# 10 jobs x (scores + skills + rationale + category) can exceed 2000 tokens and
# truncate the JSON array, failing the whole batch — keep generous headroom.
MAX_COMPLETION_TOKENS = 4000
# Safety valve: stop self-chaining after this many chained invocations even if
# jobs remain, so a persistent failure can't re-bill the model API + Lambda forever.
MAX_CHAIN_DEPTH = 30

SYSTEM_PROMPT = """You are a precise job-resume matching engine. Score each job independently against the candidate profile and the rubric below. Use evidence from the job description; do not invent requirements or skills.

CANDIDATE PROFILE:
- Location and work authorization: Waterloo, Ontario, Canada. Holds a PGWP open work permit. Eligible for Canadian roles and Canada-eligible remote roles; not eligible for US-only roles or roles requiring US work authorization without explicit Canadian eligibility.
- Professional experience: 2 years as a Software Engineer at Barclays in Pune, India (Aug 2021-Aug 2023), plus Canadian Software Developer experience at Enzuzo in Waterloo, Ontario (Nov-Dec 2025). This is real professional experience, not only academic work. Target roles requiring 0-3 years or 1-3 years; 4 years can still be plausible when the fit is strong.
- Barclays: Built Ab Initio ETL plans and graphs, Oracle SQL, TWS scheduling, Jenkins CI/testing, and Hive migrations. Processed 5M+ daily records and $4B+ credit-card transactions. Reduced batch processing by 33% and latency to under one hour.
- Enzuzo: Refactored TypeScript consent-management logic and internal REST APIs in a privacy-compliance SaaS. Reduced regression defects 30% and incorrect production script execution 80%. Wrote TypeScript unit/integration tests; supported Docker deployments and Git releases.
- Canadian experience: Instructor Assistant at Wilfrid Laurier University, teaching/grading HTML, CSS, JavaScript, and ARM assembly coursework.
- Education: Master of Applied Computing, Wilfrid Laurier University, Waterloo; B.Tech in Information Technology, Mumbai University.
- Core skills: TypeScript, JavaScript, Python, Next.js, React, Node.js, FastAPI, PostgreSQL, SQL, Ab Initio, Docker, AWS, Jenkins, Git.
- Certification: AWS Certified Cloud Practitioner (CLF-C02).
- Relevant projects: JobHunter (AWS Lambda, Supabase/PostgreSQL, Next.js, pgvector, OpenAI embeddings, LLM classification); MirrorAgent (Electron, React, TypeScript, Claude Vision, Chrome extension, WebSockets); WorkVibe (Python NLP and SQL pipeline over 289K posts); Lex Harvester (FastAPI, PostgreSQL, pgvector, MiniLM embeddings, hybrid retrieval, Claude integration; EvenUp hackathon runner-up).
- Awards: Amazon Robotics Day winner for Python navigation/collision-avoidance agent; EvenUp x OpenClaw hackathon runner-up.

ROLE PRIORITY:
1. Full-stack software engineering: TypeScript, React, Next.js, Node.js, product/SaaS development.
2. AI/LLM application engineering: agents, RAG, retrieval, embeddings, vector databases, AI product integrations.
3. Backend/API engineering: Python, FastAPI, Node.js, PostgreSQL, distributed data/API systems.
4. Data engineering: ETL, SQL, pipelines, orchestration, data platforms. This is a credible fit due to Barclays, but lower priority than the three categories above.

TECHNICAL FIT GUIDANCE:
- Highest overlap: TypeScript, React, Next.js, Node.js, Python, FastAPI, PostgreSQL, LLM APIs, RAG, embeddings, vector databases, agents, AWS, Docker.
- Strong relevant overlap: REST APIs, SaaS, SQL, data pipelines, ETL, CI/CD, Jenkins, cloud, testing, Electron, WebSockets.
- Transferable frameworks: Vue, Angular, Svelte, Django, Flask, Ruby on Rails, Laravel. Award meaningful but not full overlap credit.
- A Java-only, C#/.NET-only, Go-only, mobile-native-only, or infrastructure-only role is weak unless it also materially uses the candidate's demonstrated skills.

SCORING RUBRIC (score 0-100):
1. ROLE TYPE FIT (35): 32-35 for priority 1 or 2 roles; 26-31 for backend/API; 20-26 for data engineering; 15-22 for code-heavy QA/SDET; 0-8 for non-engineering, pure manual QA, sales, support, DevOps-only, or management roles. Use the job duties, not title alone.
2. SENIORITY FIT (30): 28-30 for new grad, junior, entry, 0-3 years, 1-3 years, or no stated experience; 23-27 for 3-4 years; 12-18 for 5+ years; 0-8 for senior, staff, principal, lead, architect, manager, director, or 7+ years. Do not penalize the candidate because Barclays experience was in India; it counts as professional experience.
3. TECH STACK OVERLAP (20): 17-20 for multiple highest-overlap skills; 12-16 for several strong relevant or transferable skills; 7-11 for a partial match; 2-6 for a mostly mismatched stack. A vague JD with no stack information earns 10, not zero.
4. OPPORTUNITY QUALITY (15): Reward product/SaaS building, API development, AI products, cloud, CI/CD, data scale, greenfield work, and shipping ownership. Deduct for requirements that materially conflict with the profile.

LOCATION AND ELIGIBILITY RULES:
- Explicitly US-only location, US citizenship, US work authorization, security clearance, or relocation to the US with no Canadian option: deduct 30 points.
- Explicitly Canadian, Ontario, Waterloo/Toronto, or remote-in-Canada: no location penalty.
- Remote location unspecified: do not assume US-only; do not apply a penalty.
- Apply any location deduction after summing the four component scores. Keep the final score between 0 and 100.

JOB CATEGORY — classify into exactly one:
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

EXPERIENCE LEVEL — classify into exactly one:
- intern (internship, co-op, work term, practicum)
- entry (new grad, junior, 0-2 years, entry-level, associate, no experience required)
- mid (intermediate, 2-5 years, or some professional experience required)
- senior (senior, staff, lead, principal, architect, director, head, VP, 5+ years, manager-level IC or above)

Return every requested job exactly once. The component scores must be integers within their stated ranges, their sum must equal score before any location deduction, and the rationale must name the strongest fit and any material limitation. You MUST respond ONLY with a valid JSON array. No other text."""

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

def build_embed_text(job: dict) -> str:
    parts = [job["title"]]
    if job.get("company_name"):
        parts.append(f"at {job['company_name']}")
    if job.get("location"):
        parts.append(f"in {job['location']}")
    return " ".join(parts)


def generate_embeddings(jobs: list[dict]) -> dict[str, list[float]]:
    texts = [build_embed_text(j) for j in jobs]
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "text-embedding-3-small", "input": texts, "dimensions": 256},
        )
        resp.raise_for_status()
    data = resp.json()["data"]
    sorted_embeddings = [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
    return {str(job["id"]): emb for job, emb in zip(jobs, sorted_embeddings)}


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
        "model": SCORING_MODEL,
        "max_tokens": MAX_COMPLETION_TOKENS,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": BATCH_USER_PROMPT.format(jobs_block=jobs_block)},
        ],
    }

    with httpx.Client(timeout=90) as client:
        response = client.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/hunainadhikari/JobHunter",
                "X-Title": "JobHunter",
            },
            json=payload,
        )
        response.raise_for_status()

    result = response.json()
    text = result["choices"][0]["message"]["content"]
    clean = text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(clean)


MAX_RUNTIME_SECONDS = 14 * 60


def claim_jobs(supabase, count: int = 100) -> list[dict]:
    """Atomically flip up to `count` new jobs to 'scoring' and return them.

    Uses the claim_jobs_for_scoring RPC (migration 014) so overlapping
    invocations claim disjoint sets. Falls back to the legacy non-atomic
    select+update if the RPC isn't deployed yet.
    """
    try:
        resp = supabase.rpc("claim_jobs_for_scoring", {"claim_count": count}).execute()
        return resp.data or []
    except Exception as e:
        print(f"claim_jobs_for_scoring RPC unavailable, falling back to legacy claim: {e}")

    resp = (
        supabase.table("jobs")
        .select("id, title, company_name, location, description")
        .eq("status", "new")
        .not_.is_("description", "null")
        .order("first_seen_at", desc=True)
        .limit(count)
        .execute()
    )
    all_jobs = resp.data
    if all_jobs:
        claimed_ids = [job["id"] for job in all_jobs]
        supabase.table("jobs").update({"status": "scoring"}).eq("status", "new").in_("id", claimed_ids).execute()
    return all_jobs


def score_round(supabase, failed_ids: set) -> dict:
    claimed = claim_jobs(supabase, 100)

    # Skip jobs that already failed this invocation — retrying them in a tight
    # loop just re-bills the same failure. They're reset to 'new' at round end
    # and get another shot on the next scheduled/chained invocation.
    all_jobs = [j for j in claimed if str(j["id"]) not in failed_ids]

    claimed_ids = [job["id"] for job in claimed]

    null_desc_resp = (
        supabase.table("jobs")
        .select("id")
        .eq("status", "new")
        .is_("description", "null")
        .limit(500)
        .execute()
    )
    discarded = len(null_desc_resp.data)
    if null_desc_resp.data:
        null_ids = [job["id"] for job in null_desc_resp.data]
        supabase.table("jobs").update({"status": "scored"}).in_("id", null_ids).execute()

    stats = {"scored": 0, "matched": 0, "errors": [], "discarded": discarded}

    if not all_jobs:
        # Release anything claimed but skipped (all-failed claim). Scope to our
        # claim so we don't release jobs held by a concurrent invocation.
        if claimed_ids:
            supabase.table("jobs").update({"status": "new"}).eq("status", "scoring").in_("id", claimed_ids).execute()
        return stats

    for i in range(0, len(all_jobs), BATCH_SIZE):
        batch = all_jobs[i : i + BATCH_SIZE]
        batch_ids = {str(j["id"]) for j in batch}
        try:
            results = score_batch(batch)

            try:
                embeddings = generate_embeddings(batch)
            except Exception as e:
                print(f"Embedding generation failed (non-fatal): {e}")
                embeddings = {}

            job_id_map = {str(j["id"]): j for j in batch}
            returned_ids = set()

            for result in results:
                job_id = result.get("job_id")
                if job_id not in job_id_map:
                    continue

                score = result.get("score")
                if not isinstance(score, (int, float)):
                    # Don't persist a fake 0 for a job the model didn't score —
                    # leave it unreturned so it's retried later with its description intact.
                    continue
                returned_ids.add(job_id)

                new_status = "matched" if score >= MATCH_THRESHOLD else "scored"

                supabase.table("scores").upsert({
                    "job_id": job_id,
                    "model": SCORING_MODEL,
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

                job_update = {"status": new_status, "description": None}
                if job_id in embeddings:
                    job_update["embedding"] = embeddings[job_id]
                supabase.table("jobs").update(job_update).eq("id", job_id).execute()

                stats["scored"] += 1
                if score >= MATCH_THRESHOLD:
                    stats["matched"] += 1

            missing = batch_ids - returned_ids
            if missing:
                failed_ids.update(missing)
                stats["errors"].append(f"Batch {i//BATCH_SIZE}: model omitted {len(missing)} job(s)")
                print(f"Batch {i//BATCH_SIZE}: {len(missing)} claimed job(s) missing from model response, will retry next invocation")

        except Exception as e:
            failed_ids.update(batch_ids)
            stats["errors"].append(f"Batch {i//BATCH_SIZE}: {str(e)[:200]}")
            print(f"Scoring batch failed: {e}")
            traceback.print_exc()

    supabase.table("jobs").update({"status": "new"}).eq("status", "scoring").in_("id", claimed_ids).execute()

    return stats


def lambda_handler(event, context):
    import time
    start_time = time.time()
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    chain_depth = (event or {}).get("chain_depth", 0)
    total_stats = {"scored": 0, "matched": 0, "errors": [], "discarded": 0, "rounds": 0}
    failed_ids: set = set()

    while True:
        elapsed = time.time() - start_time
        if elapsed >= MAX_RUNTIME_SECONDS:
            break

        round_stats = score_round(supabase, failed_ids)
        if round_stats["scored"] == 0 and round_stats["discarded"] == 0:
            break

        total_stats["scored"] += round_stats["scored"]
        total_stats["matched"] += round_stats["matched"]
        total_stats["discarded"] += round_stats["discarded"]
        total_stats["errors"].extend(round_stats["errors"])
        total_stats["rounds"] += 1

        print(f"Round {total_stats['rounds']}: scored={round_stats['scored']} matched={round_stats['matched']} errors={len(round_stats['errors'])} elapsed={int(elapsed)}s")

    remaining = (
        supabase.table("jobs")
        .select("id", count="exact")
        .eq("status", "new")
        .not_.is_("description", "null")
        .limit(1)
        .execute()
    )
    remaining_count = remaining.count or 0
    elapsed = int(time.time() - start_time)
    print(f"Scoring complete. rounds={total_stats['rounds']} scored={total_stats['scored']} matched={total_stats['matched']} discarded={total_stats['discarded']} remaining={remaining_count} elapsed={elapsed}s")

    made_progress = total_stats["scored"] > 0 or total_stats["discarded"] > 0
    if remaining_count > 0 and made_progress and chain_depth < MAX_CHAIN_DEPTH:
        print(f"Self-chaining (depth {chain_depth + 1}) for {remaining_count} remaining jobs")
        boto3.client("lambda", region_name="ca-central-1").invoke(
            FunctionName=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "jobhunter-scoring"),
            InvocationType="Event",
            Payload=json.dumps({"chain_depth": chain_depth + 1}),
        )
    elif remaining_count > 0:
        # Zero progress or depth cap hit: stop chaining so a poisoned batch or
        # persistent API failure can't loop forever. Next scheduled run retries.
        print(f"NOT self-chaining: remaining={remaining_count} progress={made_progress} depth={chain_depth} failed={len(failed_ids)}")

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "complete", "stats": total_stats, "remaining": remaining_count}, default=str),
    }
