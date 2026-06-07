#!/usr/bin/env python3
"""Quick validation script for MiniMax-M3 scoring API."""

import json
import os
import sys
import httpx

MINIMAX_API_URL = "https://api.minimax.io/v1/chat/completions"
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")

if not MINIMAX_API_KEY:
    print("ERROR: Set MINIMAX_API_KEY env var first")
    print("  export MINIMAX_API_KEY=your-key-here")
    sys.exit(1)

SYSTEM_PROMPT = """You are a job-resume matching engine. You score how well a job posting matches a candidate's profile.

CANDIDATE PROFILE:
- Name: Hunain Adhikari
- Location: Waterloo, Ontario, Canada
- Experience: 0-3 years
- Education: Master of Applied Computing (WLU, 2025), B.Tech IT (Mumbai University, 2021)
- Work History:
  - Software Developer at Enzuzo (TypeScript, REST APIs, Docker, privacy-compliance SaaS)
  - Software Engineer at Barclays (2 years, Ab Initio ETL pipelines, Oracle SQL, Jenkins, TWS, processing $4B+ credit card transactions)
  - Instructor Assistant at WLU (HTML/CSS/JS, ARM assembly)
- Key Projects:
  - MirrorLog: Full-stack SaaS (Next.js, TypeScript, Supabase, Prisma, Stripe, Clerk, Claude API)
  - MirrorAgent: macOS desktop app (Electron, React, TypeScript, Claude Vision, Chrome extension, WebSocket)
  - Lex Harvester: Legal research agent (FastAPI, PostgreSQL, pgvector, MiniLM embeddings)
- Skills: TypeScript, JavaScript, Python, C++, Next.js, React, Node.js, FastAPI, PostgreSQL, Ab Initio, Docker, AWS, Jenkins, Git
- Certifications: AWS Certified Cloud Practitioner

SCORING RUBRIC (score 0-100):
1. ROLE TYPE FIT (35 points): Is this a software development, engineering, data engineering, AI, or full-stack role? Deduct heavily for non-dev roles (PM, QA manual, tech writer, DevOps-only, sales engineer).
2. SENIORITY FIT (30 points): Does it target 0-3 years experience? Deduct for senior (5+), staff, principal, lead, director roles. "Junior", "New Grad", "Entry Level", or no explicit seniority = full points.
3. TECH STACK OVERLAP (20 points): How many of the candidate's skills appear in the JD? Bonus for exact matches (TypeScript, Next.js, React, Python, FastAPI, PostgreSQL, Docker, AWS).
4. KEYWORD RELEVANCE (15 points): General alignment with ETL, SaaS, full-stack, data pipelines, API development, cloud, CI/CD.

You MUST respond ONLY with a valid JSON array. No other text."""

SAMPLE_JOBS = [
    {
        "id": "job-001",
        "title": "Junior Full Stack Developer",
        "company_name": "Shopify",
        "location": "Toronto, ON (Remote)",
        "description": "We are looking for a Junior Full Stack Developer to join our team. You will work with TypeScript, React, Node.js, and PostgreSQL to build merchant-facing features. 0-2 years of experience required. Experience with Next.js and Docker is a plus. You will work in an agile environment with CI/CD pipelines on AWS."
    },
    {
        "id": "job-002",
        "title": "Senior Staff Engineer",
        "company_name": "RBC",
        "location": "Toronto, ON",
        "description": "We are looking for a Senior Staff Engineer with 10+ years of experience to lead our platform architecture. You will mentor junior engineers and drive technical strategy across multiple teams. Principal-level thinking required. Experience with Java, Kubernetes, and large-scale distributed systems."
    },
    {
        "id": "job-003",
        "title": "Data Engineer",
        "company_name": "Wealthsimple",
        "location": "Remote - Canada",
        "description": "Join our data team as a Data Engineer. You will build and maintain ETL pipelines using Python and Apache Airflow. Experience with PostgreSQL, AWS, and data pipeline development required. 1-3 years of experience. Familiarity with Docker and CI/CD is a plus."
    },
]

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

def build_jobs_block(jobs):
    block = ""
    for job in jobs:
        block += f"""
[JOB {job['id']}]
Title: {job['title']}
Company: {job['company_name']}
Location: {job['location']}
Description: {job['description'][:2000]}
---
"""
    return block

def test_scoring():
    jobs_block = build_jobs_block(SAMPLE_JOBS)
    payload = {
        "model": "MiniMax-M3",
        "max_tokens": 1000,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": BATCH_USER_PROMPT.format(jobs_block=jobs_block)}
        ],
        "thinking": {"type": "disabled"}
    }

    print("Sending 3 sample jobs to MiniMax-M3...")
    print(f"  job-001: Junior Full Stack @ Shopify (expect HIGH score ~85-95)")
    print(f"  job-002: Senior Staff Engineer @ RBC (expect LOW score ~10-30)")
    print(f"  job-003: Data Engineer @ Wealthsimple (expect HIGH score ~80-90)")
    print()

    with httpx.Client(timeout=60) as client:
        response = client.post(
            MINIMAX_API_URL,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload
        )

    print(f"HTTP Status: {response.status_code}")

    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        sys.exit(1)

    result = response.json()
    raw_content = result["choices"][0]["message"]["content"]

    print(f"Raw response:\n{raw_content}\n")

    # Try parsing
    clean = raw_content.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        scores = json.loads(clean)
        print("JSON parsing: OK")
        print()
        for s in scores:
            print(f"  {s['job_id']}: score={s['score']} (role={s.get('role_fit')}, seniority={s.get('seniority_fit')}, stack={s.get('stack_overlap')}, keyword={s.get('keyword_match')})")
            print(f"    Skills: {s.get('matched_skills')}")
            print(f"    Rationale: {s.get('rationale')}")
            print()
    except json.JSONDecodeError as e:
        print(f"JSON parsing FAILED: {e}")
        print("The scoring Lambda will need extra cleanup logic for this response format.")

if __name__ == "__main__":
    test_scoring()
