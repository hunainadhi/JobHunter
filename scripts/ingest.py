import csv
import hashlib
import importlib
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client

sys.path.insert(0, str(Path(__file__).parent.parent / "lambdas" / "ingestion"))
from location_filter import is_canadian_location

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ATS_PLATFORM = os.environ["ATS_PLATFORM"]

DATA_DIR = Path(__file__).parent.parent / "lambdas" / "ingestion" / "data"
SCRAPE_DELAY = 0.3

ATS_SCRAPERS = {
    "greenhouse": "jobhive.scrapers.greenhouse.GreenhouseScraper",
    "lever": "jobhive.scrapers.lever.LeverScraper",
    "ashby": "jobhive.scrapers.ashby.AshbyScraper",
    "icims": "jobhive.scrapers.icims.iCIMSScraper",
    "smartrecruiters": "jobhive.scrapers.smartrecruiters.SmartRecruitersScraper",
    "workable": "jobhive.scrapers.workable.WorkableScraper",
}


def get_scraper_class(ats_platform: str):
    module_path, class_name = ATS_SCRAPERS[ats_platform].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def load_company_slugs(ats_platform: str) -> list[dict]:
    csv_path = DATA_DIR / f"{ats_platform}.csv"
    if not csv_path.exists():
        return []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        return [{"name": row["name"], "slug": row["slug"]} for row in reader]


def compute_content_hash(description: str) -> str:
    normalized = re.sub(r"\s+", " ", description.lower().strip())
    return hashlib.sha256(normalized.encode()).hexdigest()


def load_blacklist(supabase) -> set:
    resp = supabase.table("blacklisted_companies").select("company_name, ats_token").execute()
    blacklisted = set()
    for row in resp.data:
        if row.get("company_name"):
            blacklisted.add(row["company_name"].lower().strip())
        if row.get("ats_token"):
            blacklisted.add(row["ats_token"].lower().strip())
    return blacklisted


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    blacklist = load_blacklist(supabase)

    ScraperClass = get_scraper_class(ATS_PLATFORM)
    companies = load_company_slugs(ATS_PLATFORM)

    if not companies:
        print(f"[{ATS_PLATFORM}] No company CSV found, skipping.")
        return

    run_id = supabase.table("scrape_runs").insert({
        "ats_platform": ATS_PLATFORM,
        "status": "running",
    }).execute().data[0]["id"]

    stats = {
        "companies_scraped": 0,
        "jobs_found": 0,
        "jobs_new": 0,
        "errors": [],
    }

    print(f"[{ATS_PLATFORM}] Starting ingestion for {len(companies)} companies...")

    for i, company in enumerate(companies):
        slug = company["slug"]
        name = company["name"]

        if slug.lower() in blacklist or name.lower().strip() in blacklist:
            continue

        try:
            scraper = ScraperClass(company_slug=slug, timeout=15.0)
            jobs = scraper.fetch()
            stats["companies_scraped"] += 1

            canadian_jobs = []
            for job in jobs:
                country_iso = getattr(job, "country_iso", None)
                if is_canadian_location(job.location, country_iso):
                    canadian_jobs.append(job)

            stats["jobs_found"] += len(canadian_jobs)

            for job in canadian_jobs:
                description = job.description or ""
                content_hash = compute_content_hash(description) if description else None

                row = {
                    "ats_platform": ATS_PLATFORM,
                    "ats_token": slug,
                    "external_id": job.ats_id,
                    "title": job.title,
                    "company_name": job.company or name,
                    "location": job.location,
                    "is_remote": job.is_remote or False,
                    "description": description if description else None,
                    "apply_url": str(job.apply_url) if job.apply_url else str(job.url),
                    "source_url": str(job.url),
                    "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                    "content_hash": content_hash,
                    "status": "new",
                }

                resp = supabase.table("jobs").upsert(
                    row,
                    on_conflict="ats_platform,external_id",
                    ignore_duplicates=True,
                ).execute()

                if resp.data:
                    stats["jobs_new"] += 1

        except Exception as e:
            error_msg = f"{ATS_PLATFORM}/{slug}: {str(e)[:200]}"
            stats["errors"].append(error_msg)

        time.sleep(SCRAPE_DELAY)

        if (i + 1) % 100 == 0:
            print(f"[{ATS_PLATFORM}] Progress: {i+1}/{len(companies)} | found={stats['jobs_found']} new={stats['jobs_new']}")

    status = "success"
    if stats["errors"]:
        status = "partial_failure" if stats["companies_scraped"] > 0 else "failure"

    supabase.table("scrape_runs").update({
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "companies_scraped": stats["companies_scraped"],
        "jobs_found": stats["jobs_found"],
        "jobs_new": stats["jobs_new"],
        "error_log": "\n".join(stats["errors"][:50]) if stats["errors"] else None,
    }).eq("id", run_id).execute()

    print(f"[{ATS_PLATFORM}] Done! scraped={stats['companies_scraped']} found={stats['jobs_found']} new={stats['jobs_new']} errors={len(stats['errors'])}")


if __name__ == "__main__":
    main()
