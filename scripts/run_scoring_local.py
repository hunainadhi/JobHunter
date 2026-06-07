#!/usr/bin/env python3
"""Run scoring locally against unscored jobs in Supabase.
Usage: python scripts/run_scoring_local.py
"""

import json
import os
import sys
from pathlib import Path

# Load env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

if "NEXT_PUBLIC_SUPABASE_URL" in os.environ and "SUPABASE_URL" not in os.environ:
    os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]

sys.path.insert(0, str(Path(__file__).parent.parent / "lambdas" / "scoring"))

from handler import lambda_handler
from supabase import create_client

print("Running scoring pipeline...")
result = lambda_handler({}, None)
body = json.loads(result["body"])
print(json.dumps(body, indent=2))

# Show matched jobs
print("\n=== Matched jobs (score >= 70) ===")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
resp = (
    sb.table("scores")
    .select("score, role_fit_score, seniority_fit_score, stack_overlap_score, keyword_score, rationale, job_id, jobs(title, company_name, location, description)")
    .gte("score", 70)
    .order("score", desc=True)
    .limit(20)
    .execute()
)

for row in resp.data:
    job = row.get("jobs", {})
    print(f"  [{row['score']}] {job.get('title', '?')} @ {job.get('company_name', '?')} — {job.get('location', '?')}")
    print(f"       Role:{row.get('role_fit_score')} Sen:{row.get('seniority_fit_score')} Stack:{row.get('stack_overlap_score')} Kw:{row.get('keyword_score')}")
    print(f"       {row.get('rationale', '')}")
    desc = job.get("description")
    print(f"       Description nulled: {desc is None}")
    print()
