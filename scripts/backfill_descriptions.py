"""
Backfill descriptions for already-scored jobs missing level/category.
Fetches descriptions via jobhive, updates the job row, and resets status to 'new'
so the scoring Lambda re-scores with category + level.
"""

import os
import sys
import time
from pathlib import Path

# Only add jobhive from the Lambda layer, use system-installed supabase
layer_path = str(Path(__file__).resolve().parent.parent / "lambdas" / "layer" / "python")
sys.path.append(layer_path)

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

ATS_SCRAPERS = {
    "greenhouse": "jobhive.scrapers.greenhouse.GreenhouseScraper",
    "lever": "jobhive.scrapers.lever.LeverScraper",
    "ashby": "jobhive.scrapers.ashby.AshbyScraper",
    "smartrecruiters": "jobhive.scrapers.smartrecruiters.SmartRecruitersScraper",
    "workable": "jobhive.scrapers.workable.WorkableScraper",
    "rippling": "jobhive.scrapers.rippling.RipplingScraper",
}

BOARD_SCRAPERS = {
    "ycombinator": "jobhive.scrapers.ycombinator.YCombinatorScraper",
    "themuse": "jobhive.scrapers.themuse.TheMuseScraper",
    "weworkremotely": "jobhive.scrapers.weworkremotely.WeWorkRemotelyScraper",
}


def get_scraper_class(scraper_path: str):
    module_path, class_name = scraper_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def fetch_missing_jobs(supabase) -> list[dict]:
    """Fetch all scored jobs that are missing level or category."""
    all_jobs = []
    offset = 0
    page_size = 1000

    while True:
        resp = supabase.table("scores") \
            .select("job_id, jobs(id, ats_platform, ats_token, external_id, title)") \
            .or_("level.is.null,category.is.null") \
            .range(offset, offset + page_size - 1) \
            .execute()

        if not resp.data:
            break

        for row in resp.data:
            if row.get("jobs"):
                all_jobs.append({
                    "job_id": row["job_id"],
                    "ats_platform": row["jobs"]["ats_platform"],
                    "ats_token": row["jobs"]["ats_token"],
                    "external_id": row["jobs"]["external_id"],
                    "title": row["jobs"]["title"],
                })

        offset += page_size
        if len(resp.data) < page_size:
            break

    return all_jobs


def group_by_company(jobs: list[dict]) -> dict:
    """Group jobs by (ats_platform, ats_token)."""
    groups = {}
    for job in jobs:
        key = (job["ats_platform"], job["ats_token"])
        groups.setdefault(key, []).append(job)
    return groups


def scrape_company(ats_platform: str, ats_token: str) -> dict[str, str]:
    """Scrape a company and return {external_id: description}."""
    scraper_path = ATS_SCRAPERS.get(ats_platform) or BOARD_SCRAPERS.get(ats_platform)
    if not scraper_path:
        return {}

    ScraperClass = get_scraper_class(scraper_path)
    scraper = ScraperClass(company_slug=ats_token, timeout=15.0)
    jobs = scraper.fetch()
    # fetch() alone leaves description empty on most platforms; the detail-page
    # fetch happens here (same as the ingestion handler).
    jobs = scraper.enrich_descriptions(jobs)

    return {job.ats_id: job.description for job in jobs if job.description}


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    print("Fetching jobs missing level/category...")
    missing_jobs = fetch_missing_jobs(supabase)
    print(f"Found {len(missing_jobs)} jobs to backfill")

    groups = group_by_company(missing_jobs)
    print(f"Across {len(groups)} companies")

    total_updated = 0
    total_failed = 0
    total_not_found = 0

    for i, ((platform, token), jobs) in enumerate(groups.items()):
        ext_ids = {j["external_id"]: j["job_id"] for j in jobs}
        print(f"[{i+1}/{len(groups)}] {platform}/{token} ({len(jobs)} jobs)...", end=" ", flush=True)

        try:
            descriptions = scrape_company(platform, token)
            matched = 0

            for ext_id, job_id in ext_ids.items():
                desc = descriptions.get(ext_id)
                if desc:
                    supabase.table("jobs").update({
                        "description": desc,
                        "status": "new",
                    }).eq("id", job_id).execute()
                    matched += 1

            not_found = len(jobs) - matched
            total_updated += matched
            total_not_found += not_found
            print(f"updated={matched} not_found={not_found}")

        except Exception as e:
            total_failed += len(jobs)
            print(f"ERROR: {str(e)[:100]}")

        time.sleep(0.3)

    print(f"\nDone. updated={total_updated} not_found={total_not_found} failed={total_failed}")


if __name__ == "__main__":
    main()
