#!/usr/bin/env python3
"""Emit up to 20 newly discovered, policy-eligible JobHunter roles for daily packages."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "app" / ".env.local"
MAX_PACKAGES = 20
SCORE_FLOOR = 70
EXCLUDED_SENIORITY = re.compile(r"\b(senior|staff|lead|principal|manager|director|vice president|vp)\b", re.I)
CANADA_LOCATIONS = re.compile(
    r"\b(canada|ontario|toronto|waterloo|ottawa|vancouver|montreal|calgary|edmonton|winnipeg|halifax|victoria|quebec)\b",
    re.I,
)
INELIGIBLE = re.compile(
    r"\b(canadian citizen(?:ship)?|canada(?:ian)? permanent resident|security clearance|secret clearance|top secret)\b",
    re.I,
)


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def timestamp(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def materialize_packages(base_url: str, secret: str, candidates: list[dict[str, object]]) -> None:
    if not candidates:
        return
    now = datetime.now(UTC).isoformat()
    records = []
    for candidate in candidates:
        records.append({
            "job_id": candidate["job_id"],
            "company_name": candidate["company"],
            "job_title": candidate["title"],
            "apply_url": candidate["apply_url"],
            "source_url": candidate["source_url"],
            "match_score": candidate["score"],
            "status": "ready_to_apply",
            "policy_reasons": [
                f"JobHunter score: {candidate['score']}/100.",
                "Daily manual application package created.",
            ],
            "application_fields": {
                "package_version": 1,
                "common_answers": {
                    "location": "Waterloo, Ontario, Canada",
                    "work_authorization": "Authorized to work for any Canadian employer through a post-graduation open work permit. No sponsorship required.",
                    "availability": "One week",
                    "salary_default": "CAD 75,000 annual base, flexible based on the overall compensation package.",
                },
                "links": {
                    "linkedin": "https://www.linkedin.com/in/hunainadhikari",
                    "github": "https://github.com/hunainadhi",
                    "portfolio": "https://hunainadhikari.com",
                },
                "form_checklist": [
                    "Attach Hunain Adhikari - SDE.pdf.",
                    "Review the live form for employer-specific questions before submitting.",
                    "Stop for assessments, recorded video, CAPTCHA, MFA, or unusual legal terms.",
                ],
            },
            "submitted_materials": {"resume": "Hunain Adhikari - SDE.pdf"},
            "next_action": "Open the application package and complete the live form manually.",
            "next_action_at": now,
        })
    request = urllib.request.Request(
        base_url.rstrip("/") + "/rest/v1/application_ledger?on_conflict=job_id",
        data=json.dumps(records).encode("utf-8"),
        method="POST",
        headers={
            "apikey": secret,
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        },
    )
    with urllib.request.urlopen(request, timeout=30):
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="Create ready-to-apply ledger packages for selected candidates.",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Emit a concise Telegram-ready daily package notification.",
    )
    args = parser.parse_args()
    env = load_env()
    base_url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    secret = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_KEY")
    if not base_url or not secret:
        raise SystemExit("Missing Supabase server configuration.")

    since = datetime.now(UTC) - timedelta(hours=27)
    params = {
        "select": (
            "score,rationale,matched_skills,scored_at,"
            "jobs!inner(id,title,company_name,location,is_remote,description,apply_url,source_url,posted_at,first_seen_at,status)"
        ),
        "score": f"gte.{SCORE_FLOOR}",
        "jobs.first_seen_at": f"gte.{since.isoformat()}",
        "order": "score.desc",
        "limit": "250",
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/rest/v1/scores?" + urllib.parse.urlencode(params, safe="(),!"),
        headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        rows = json.loads(response.read())

    selected: list[dict[str, object]] = []
    job_ids: set[str] = set()
    company_titles: dict[str, set[str]] = {}
    for row in rows:
        job = row.get("jobs")
        if isinstance(job, list):
            job = job[0] if job else None
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("id") or "")
        title = str(job.get("title") or "")
        company = str(job.get("company_name") or "")
        location = str(job.get("location") or "")
        description = str(job.get("description") or "")
        if not job_id or job_id in job_ids or EXCLUDED_SENIORITY.search(title):
            continue
        if not job.get("is_remote") and not CANADA_LOCATIONS.search(location):
            continue
        if INELIGIBLE.search(f"{title}\n{description}"):
            continue
        normalized_title = re.sub(r"\s+", " ", title.strip().lower())
        titles = company_titles.setdefault(company.lower(), set())
        if normalized_title in titles or len(titles) >= 5:
            continue
        titles.add(normalized_title)
        job_ids.add(job_id)
        selected.append(
            {
                "job_id": job_id,
                "score": row.get("score"),
                "company": company,
                "title": title,
                "location": location or "Remote",
                "remote": bool(job.get("is_remote")),
                "first_seen_at": job.get("first_seen_at"),
                "posted_at": job.get("posted_at"),
                "apply_url": job.get("apply_url"),
                "source_url": job.get("source_url"),
                "rationale": row.get("rationale"),
                "matched_skills": row.get("matched_skills"),
                "description": description[:7000],
            }
        )
        if len(selected) == MAX_PACKAGES:
            break

    if args.materialize:
        materialize_packages(base_url, secret, selected)

    if args.telegram:
        print(f"Daily application packages: {len(selected)} ready")
        if selected:
            for index, candidate in enumerate(selected, start=1):
                print(f"{index}. {candidate['company']} | {candidate['title']} | {candidate['score']}/100")
            print("\nOpen all packages: https://job-hunter-blond-chi.vercel.app/application")
        else:
            print("No new 70+ Canada-eligible roles were added in the last 27 hours.")
        return 0

    print(json.dumps({
        "window_start_utc": since.isoformat(),
        "score_floor": SCORE_FLOOR,
        "materialized": args.materialize,
        "count": len(selected),
        "candidates": selected,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
