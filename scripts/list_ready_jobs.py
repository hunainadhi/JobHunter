#!/usr/bin/env python3
"""List recent high-scoring JobHunter candidates without exposing credentials."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "app" / ".env.local"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def main() -> int:
    env = load_env()
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("Missing usable Supabase URL or server key.")
        return 1

    params = {
        "select": (
            "score,rationale,matched_skills,scored_at,"
            "jobs!inner(id,title,company_name,location,is_remote,description,apply_url,source_url,posted_at,first_seen_at,status)"
        ),
        "score": "gte.70",
        "order": "score.desc",
        "limit": "200",
    }
    request = urllib.request.Request(
        url.rstrip("/") + "/rest/v1/scores?" + urllib.parse.urlencode(params, safe="(),!"),
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        rows = json.loads(response.read())

    seen: set[str] = set()
    candidates: list[dict[str, object]] = []
    for row in rows:
        job = row.get("jobs")
        if isinstance(job, list):
            job = job[0] if job else None
        if not isinstance(job, dict) or job["id"] in seen:
            continue
        seen.add(job["id"])
        title = str(job.get("title") or "")
        location = str(job.get("location") or "")
        title_lower = title.lower()
        location_lower = location.lower()
        if any(word in title_lower for word in ("senior", "staff", "lead", "principal", "manager", "director", "vice president")):
            continue
        if not job.get("is_remote") and not any(place in location_lower for place in ("canada", "ontario", "toronto", "waterloo", "ottawa", "vancouver", "montreal", "calgary", "edmonton", "winnipeg", "halifax", "victoria", "quebec")):
            continue
        description = str(job.get("description") or "")
        candidates.append(
            {
                "job_id": job["id"],
                "score": row.get("score"),
                "company": job.get("company_name"),
                "title": title,
                "location": location,
                "remote": job.get("is_remote"),
                "posted_at": job.get("posted_at") or job.get("first_seen_at"),
                "apply_url": job.get("apply_url"),
                "source_url": job.get("source_url"),
                "rationale": row.get("rationale"),
                "matched_skills": row.get("matched_skills"),
                "description": description,
            }
        )

    output = ROOT / ".hermes-ready-jobs.json"
    output.write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    print(f"Saved {len(candidates)} eligible 70+ candidates to {output}")
    for candidate in candidates[:20]:
        print(
            f"{candidate['score']:>3} | {candidate['company']} | {candidate['title']} | "
            f"{candidate['location'] or 'remote'} | {candidate['posted_at']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
