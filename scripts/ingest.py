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
CHUNK_INDEX = int(os.environ.get("CHUNK_INDEX", "0"))
TOTAL_CHUNKS = int(os.environ.get("TOTAL_CHUNKS", "1"))

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

BOARD_SCRAPERS = {
    "ycombinator": "jobhive.scrapers.ycombinator.YCombinatorScraper",
    "themuse": "jobhive.scrapers.themuse.TheMuseScraper",
    "weworkremotely": "jobhive.scrapers.weworkremotely.WeWorkRemotelyScraper",
}

WORKDAY_COMPANIES = [
    {"name": "RBC", "slug": "https://rbc.wd3.myworkdayjobs.com/RBCGLOBAL1"},
    {"name": "RBC Early Talent", "slug": "https://rbc.wd3.myworkdayjobs.com/RBCEARLYTALENT1"},
    {"name": "TD Bank", "slug": "https://td.wd3.myworkdayjobs.com/TD_Bank_Careers"},
    {"name": "BMO", "slug": "https://bmo.wd3.myworkdayjobs.com/External"},
    {"name": "CIBC", "slug": "https://cibc.wd3.myworkdayjobs.com/search"},
    {"name": "Desjardins", "slug": "https://desjardins.wd10.myworkdayjobs.com/Desjardins"},
    {"name": "BDC", "slug": "https://bdc.wd10.myworkdayjobs.com/BDC_Careers"},
    {"name": "Manulife", "slug": "https://manulife.wd3.myworkdayjobs.com/MFCJH_Jobs"},
    {"name": "Intact Financial", "slug": "https://intactfc.wd3.myworkdayjobs.com/intactfc"},
    {"name": "iA Financial", "slug": "https://ia.wd3.myworkdayjobs.com/Professional"},
    {"name": "Sun Life", "slug": "https://sunlife.wd3.myworkdayjobs.com/Experienced"},
    {"name": "CPP Investments", "slug": "https://cppib.wd10.myworkdayjobs.com/cppinvestments"},
    {"name": "Ontario Teachers", "slug": "https://otppb.wd3.myworkdayjobs.com/OntarioTeachers_Careers"},
    {"name": "HOOPP", "slug": "https://hoopp.wd10.myworkdayjobs.com/HOOPP"},
    {"name": "TELUS Health", "slug": "https://lifeworks.wd3.myworkdayjobs.com/External"},
    {"name": "Canadian Tire", "slug": "https://canadiantirecorporation.wd3.myworkdayjobs.com/Enterprise_External_Careers_Site"},
    {"name": "CAE", "slug": "https://cae.wd3.myworkdayjobs.com/career"},
    {"name": "Brookfield", "slug": "https://brookfield.wd5.myworkdayjobs.com/brookfield"},
    {"name": "Enbridge", "slug": "https://enbridge.wd3.myworkdayjobs.com/enbridge_careers"},
    {"name": "Autodesk", "slug": "https://autodesk.wd1.myworkdayjobs.com/Ext"},
    {"name": "Salesforce", "slug": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site"},
    {"name": "Netflix", "slug": "https://netflix.wd108.myworkdayjobs.com/Netflix"},
    {"name": "Workday", "slug": "https://workday.wd5.myworkdayjobs.com/Workday"},
    {"name": "Gartner", "slug": "https://gartner.wd5.myworkdayjobs.com/EXT"},
    {"name": "Intel", "slug": "https://intel.wd1.myworkdayjobs.com/External"},
]


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


def run_board(platform: str, supabase, blacklist: set):
    module_path, class_name = BOARD_SCRAPERS[platform].rsplit(".", 1)
    module = importlib.import_module(module_path)
    ScraperClass = getattr(module, class_name)

    run_id = supabase.table("scrape_runs").insert({
        "ats_platform": platform, "status": "running",
    }).execute().data[0]["id"]

    stats = {"companies_scraped": 1, "jobs_found": 0, "jobs_new": 0, "errors": []}
    print(f"[{platform}] Scraping board...")

    try:
        scraper = ScraperClass(company_slug="any", timeout=30.0)
        jobs = scraper.fetch()

        for job in jobs:
            country_iso = getattr(job, "country_iso", None)
            if not is_canadian_location(job.location, country_iso):
                continue

            stats["jobs_found"] += 1
            company_name = job.company or platform
            if company_name.lower().strip() in blacklist:
                continue

            description = job.description or ""
            content_hash = compute_content_hash(description) if description else None

            row = {
                "ats_platform": platform,
                "ats_token": platform,
                "external_id": job.ats_id,
                "title": job.title,
                "company_name": company_name,
                "location": job.location,
                "is_remote": job.is_remote or False,
                "description": description if description else None,
                "apply_url": str(job.apply_url) if job.apply_url else str(job.url),
                "source_url": str(job.url),
                "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                "content_hash": content_hash,
                "status": "new",
            }

            purge_check = supabase.table("purged_jobs").select("external_id").eq(
                "ats_platform", platform
            ).eq("external_id", job.ats_id).limit(1).execute()
            if purge_check.data:
                continue

            resp = supabase.table("jobs").upsert(
                row, on_conflict="ats_platform,external_id", ignore_duplicates=True,
            ).execute()
            if resp.data:
                stats["jobs_new"] += 1

    except Exception as e:
        stats["errors"].append(f"{platform}: {str(e)[:200]}")

    status = "success" if not stats["errors"] else "partial_failure"
    supabase.table("scrape_runs").update({
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "companies_scraped": stats["companies_scraped"],
        "jobs_found": stats["jobs_found"],
        "jobs_new": stats["jobs_new"],
        "error_log": "\n".join(stats["errors"][:50]) if stats["errors"] else None,
    }).eq("id", run_id).execute()

    print(f"[{platform}] Done! found={stats['jobs_found']} new={stats['jobs_new']} errors={len(stats['errors'])}")


def run_workday(supabase, blacklist: set):
    from jobhive.scrapers.workday import WorkdayScraper

    chunk_size = len(WORKDAY_COMPANIES) // TOTAL_CHUNKS
    start = CHUNK_INDEX * chunk_size
    end = len(WORKDAY_COMPANIES) if CHUNK_INDEX == TOTAL_CHUNKS - 1 else start + chunk_size
    companies = WORKDAY_COMPANIES[start:end]
    print(f"[workday] Chunk {CHUNK_INDEX+1}/{TOTAL_CHUNKS}: {len(companies)} companies")

    run_id = supabase.table("scrape_runs").insert({
        "ats_platform": "workday", "status": "running",
    }).execute().data[0]["id"]

    stats = {"companies_scraped": 0, "jobs_found": 0, "jobs_new": 0, "errors": []}

    for i, company in enumerate(companies):
        slug = company["slug"]
        name = company["name"]

        if name.lower().strip() in blacklist:
            continue

        try:
            scraper = WorkdayScraper(company_slug=slug, timeout=30.0)
            jobs = scraper.fetch()
            stats["companies_scraped"] += 1

            for job in jobs:
                country_iso = getattr(job, "country_iso", None)
                if not is_canadian_location(job.location, country_iso):
                    continue

                stats["jobs_found"] += 1
                description = job.description or ""
                content_hash = compute_content_hash(description) if description else None

                row = {
                    "ats_platform": "workday",
                    "ats_token": name,
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

                purge_check = supabase.table("purged_jobs").select("external_id").eq(
                    "ats_platform", "workday"
                ).eq("external_id", job.ats_id).limit(1).execute()
                if purge_check.data:
                    continue

                resp = supabase.table("jobs").upsert(
                    row, on_conflict="ats_platform,external_id", ignore_duplicates=True,
                ).execute()
                if resp.data:
                    stats["jobs_new"] += 1

        except Exception as e:
            stats["errors"].append(f"workday/{name}: {str(e)[:200]}")

        time.sleep(SCRAPE_DELAY)
        if (i + 1) % 5 == 0:
            print(f"[workday] Progress: {i+1}/{len(companies)} | found={stats['jobs_found']} new={stats['jobs_new']}")

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

    print(f"[workday] Done! scraped={stats['companies_scraped']} found={stats['jobs_found']} new={stats['jobs_new']} errors={len(stats['errors'])}")


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    blacklist = load_blacklist(supabase)

    if ATS_PLATFORM in BOARD_SCRAPERS:
        run_board(ATS_PLATFORM, supabase, blacklist)
        return

    if ATS_PLATFORM == "workday":
        run_workday(supabase, blacklist)
        return

    ScraperClass = get_scraper_class(ATS_PLATFORM)
    all_companies = load_company_slugs(ATS_PLATFORM)

    if not all_companies:
        print(f"[{ATS_PLATFORM}] No company CSV found, skipping.")
        return

    # Split into chunks
    chunk_size = len(all_companies) // TOTAL_CHUNKS
    start = CHUNK_INDEX * chunk_size
    end = len(all_companies) if CHUNK_INDEX == TOTAL_CHUNKS - 1 else start + chunk_size
    companies = all_companies[start:end]
    print(f"[{ATS_PLATFORM}] Chunk {CHUNK_INDEX+1}/{TOTAL_CHUNKS}: companies {start}-{end} of {len(all_companies)}")

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

                purge_check = supabase.table("purged_jobs").select("external_id").eq(
                    "ats_platform", ATS_PLATFORM
                ).eq("external_id", job.ats_id).limit(1).execute()
                if purge_check.data:
                    continue

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
