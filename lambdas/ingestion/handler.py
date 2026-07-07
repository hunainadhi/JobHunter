import csv
import hashlib
import json
import os
import re
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from supabase import create_client

from jobhive.exceptions import CompanyNotFoundError
from location_filter import is_canadian_location

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SYNC_SECRET = os.environ.get("SYNC_SECRET", "")

DATA_DIR = Path(__file__).parent / "data"
SCRAPE_DELAY = 0.3
BATCH_SIZE = 40

ATS_SCRAPERS = {
    "greenhouse": "jobhive.scrapers.greenhouse.GreenhouseScraper",
    "lever": "jobhive.scrapers.lever.LeverScraper",
    "ashby": "jobhive.scrapers.ashby.AshbyScraper",
    "smartrecruiters": "jobhive.scrapers.smartrecruiters.SmartRecruitersScraper",
    "workable": "jobhive.scrapers.workable.WorkableScraper",
    "rippling": "jobhive.scrapers.rippling.RipplingScraper",
    "icims": "jobhive.scrapers.icims.iCIMSScraper",
    "pinpoint": "jobhive.scrapers.pinpoint.PinpointScraper",
    "teamtailor": "jobhive.scrapers.teamtailor.TeamtailorScraper",
    "breezy": "jobhive.scrapers.breezy.BreezyScraper",
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


def load_dead_companies(supabase, ats_platform: str) -> tuple[set, set]:
    """Returns (skip, known): companies to skip this run, and every company
    with a dead_companies row (so a successful fetch can heal its record
    without issuing a DELETE for the ~99% of companies that were never dead)."""
    now = datetime.now(timezone.utc)
    resp = supabase.table("dead_companies").select("ats_token, error_type, fail_count, retry_after").eq(
        "ats_platform", ats_platform
    ).execute()
    skip = set()
    known = set()
    for row in resp.data:
        known.add(row["ats_token"])
        if row["error_type"] == "not_found" and row["fail_count"] >= 3:
            skip.add(row["ats_token"])
        elif row["error_type"] == "server_error" and row.get("retry_after"):
            # Compare as datetimes: ISO strings from PostgREST vary in
            # precision/offset format, so lexicographic comparison is unsafe.
            try:
                retry_after = datetime.fromisoformat(row["retry_after"])
            except ValueError:
                continue
            if retry_after > now:
                skip.add(row["ats_token"])
    return skip, known


def record_dead_company(supabase, ats_platform: str, ats_token: str, error_type: str, error_msg: str):
    now = datetime.now(timezone.utc).isoformat()
    retry_after = None
    if error_type == "server_error":
        retry_after = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    existing = supabase.table("dead_companies").select("id, fail_count").eq(
        "ats_platform", ats_platform
    ).eq("ats_token", ats_token).limit(1).execute()

    if existing.data:
        supabase.table("dead_companies").update({
            "error_type": error_type,
            "fail_count": existing.data[0]["fail_count"] + 1,
            "last_error": error_msg[:500],
            "last_failed_at": now,
            "retry_after": retry_after,
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("dead_companies").insert({
            "ats_platform": ats_platform,
            "ats_token": ats_token,
            "error_type": error_type,
            "fail_count": 1,
            "last_error": error_msg[:500],
            "last_failed_at": now,
            "retry_after": retry_after,
        }).execute()


def heal_dead_company(supabase, ats_platform: str, ats_token: str):
    supabase.table("dead_companies").delete().eq(
        "ats_platform", ats_platform
    ).eq("ats_token", ats_token).execute()


def load_blacklist(supabase) -> set:
    resp = supabase.table("blacklisted_companies").select("company_name, ats_token").execute()
    blacklisted = set()
    for row in resp.data:
        if row.get("company_name"):
            blacklisted.add(row["company_name"].lower().strip())
        if row.get("ats_token"):
            blacklisted.add(row["ats_token"].lower().strip())
    return blacklisted


def scrape_batch(ats_platform: str, companies: list[dict], supabase, blacklist: set, dead_companies: set = None, known_dead: set = None) -> dict:
    ScraperClass = get_scraper_class(ATS_SCRAPERS[ats_platform])

    stats = {
        "companies_scraped": 0,
        "companies_skipped": 0,
        "jobs_found": 0,
        "jobs_new": 0,
        "errors": [],
    }

    for company in companies:
        slug = company["slug"]
        name = company["name"]

        if slug.lower() in blacklist or name.lower().strip() in blacklist:
            continue

        if dead_companies and slug in dead_companies:
            stats["companies_skipped"] += 1
            continue

        try:
            scraper = ScraperClass(company_slug=slug, timeout=15.0)
            jobs = scraper.fetch()
            jobs = scraper.enrich_descriptions(jobs)
            stats["companies_scraped"] += 1
            if known_dead and slug in known_dead:
                heal_dead_company(supabase, ats_platform, slug)

            canadian_jobs = []
            for job in jobs:
                if not job.description:
                    continue
                country_iso = getattr(job, "country_iso", None)
                if is_canadian_location(job.location, country_iso):
                    canadian_jobs.append(job)

            stats["jobs_found"] += len(canadian_jobs)

            for job in canadian_jobs:
                description = job.description or ""
                content_hash = compute_content_hash(description) if description else None

                row = {
                    "ats_platform": ats_platform,
                    "ats_token": slug,
                    "external_id": job.ats_id,
                    "title": job.title,
                    "company_name": job.company or name,
                    "location": job.location,
                    "is_remote": job.is_remote or False,
                    "description": description if description else None,
                    "apply_url": str(job.apply_url) if job.apply_url else str(job.url),
                    "source_url": str(job.url),
                    "posted_at": job.posted_at.isoformat() if job.posted_at else datetime.now(timezone.utc).isoformat(),
                    "content_hash": content_hash,
                    "status": "new",
                }

                purge_check = supabase.table("purged_jobs").select("external_id").eq(
                    "ats_platform", ats_platform
                ).eq("external_id", job.ats_id).limit(1).execute()
                if purge_check.data:
                    continue

                existing = supabase.table("jobs").select("id").eq(
                    "ats_platform", ats_platform
                ).eq("external_id", job.ats_id).limit(1).execute()

                if existing.data:
                    supabase.table("jobs").update({
                        "last_seen_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", existing.data[0]["id"]).execute()
                else:
                    row["last_seen_at"] = datetime.now(timezone.utc).isoformat()
                    resp = supabase.table("jobs").upsert(
                        row,
                        on_conflict="ats_platform,external_id",
                        ignore_duplicates=True,
                    ).execute()
                    if resp.data:
                        stats["jobs_new"] += 1

        except CompanyNotFoundError as e:
            error_msg = f"{ats_platform}/{slug}: {str(e)[:200]}"
            stats["errors"].append(error_msg)
            record_dead_company(supabase, ats_platform, slug, "not_found", str(e))
        except Exception as e:
            error_msg = f"{ats_platform}/{slug}: {str(e)[:200]}"
            stats["errors"].append(error_msg)
            # Prefer the structured status code (httpx.HTTPStatusError et al.)
            # over string matching, which misses plain 500s and formatted errors.
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            err_str = str(e).lower()
            if (status_code is not None and status_code >= 500) or \
                    "521" in err_str or "cloudflare" in err_str or "503" in err_str or "502" in err_str:
                record_dead_company(supabase, ats_platform, slug, "server_error", str(e))

        time.sleep(SCRAPE_DELAY)

    return stats


def scrape_board(ats_platform: str, supabase, blacklist: set) -> dict:
    ScraperClass = get_scraper_class(BOARD_SCRAPERS[ats_platform])
    stats = {"companies_scraped": 1, "jobs_found": 0, "jobs_new": 0, "errors": []}

    try:
        scraper = ScraperClass(company_slug="any", timeout=30.0)
        jobs = scraper.fetch()
        jobs = scraper.enrich_descriptions(jobs)

        canadian_jobs = []
        for job in jobs:
            if not job.description:
                continue
            country_iso = getattr(job, "country_iso", None)
            if is_canadian_location(job.location, country_iso):
                canadian_jobs.append(job)

        stats["jobs_found"] = len(canadian_jobs)

        for job in canadian_jobs:
            company_name = job.company or ats_platform
            if company_name.lower().strip() in blacklist:
                continue

            description = job.description or ""
            content_hash = compute_content_hash(description) if description else None

            row = {
                "ats_platform": ats_platform,
                "ats_token": ats_platform,
                "external_id": job.ats_id,
                "title": job.title,
                "company_name": company_name,
                "location": job.location,
                "is_remote": job.is_remote or False,
                "description": description if description else None,
                "apply_url": str(job.apply_url) if job.apply_url else str(job.url),
                "source_url": str(job.url),
                "posted_at": job.posted_at.isoformat() if job.posted_at else datetime.now(timezone.utc).isoformat(),
                "content_hash": content_hash,
                "status": "new",
            }

            purge_check = supabase.table("purged_jobs").select("external_id").eq(
                "ats_platform", ats_platform
            ).eq("external_id", job.ats_id).limit(1).execute()
            if purge_check.data:
                continue

            existing = supabase.table("jobs").select("id").eq(
                "ats_platform", ats_platform
            ).eq("external_id", job.ats_id).limit(1).execute()

            if existing.data:
                supabase.table("jobs").update({
                    "last_seen_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", existing.data[0]["id"]).execute()
            else:
                row["last_seen_at"] = datetime.now(timezone.utc).isoformat()
                resp = supabase.table("jobs").upsert(
                    row, on_conflict="ats_platform,external_id", ignore_duplicates=True,
                ).execute()
                if resp.data:
                    stats["jobs_new"] += 1

    except Exception as e:
        stats["errors"].append(f"{ats_platform}: {str(e)[:200]}")

    return stats



def lambda_handler(event, context):
    # Auth-gate HTTP-shaped events (Function URL / API Gateway). Direct invokes
    # from the orchestrator carry no headers/requestContext and are IAM-gated.
    is_http_event = isinstance(event, dict) and ("headers" in event or "requestContext" in event)
    if SYNC_SECRET and is_http_event:
        headers = event.get("headers") or {}
        auth = headers.get("authorization", headers.get("Authorization", ""))
        if auth != f"Bearer {SYNC_SECRET}":
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    blacklist = load_blacklist(supabase)
    ats_platform = event.get("ats_platform")
    dead, known_dead = load_dead_companies(supabase, ats_platform) if ats_platform else (set(), set())

    # Board scraper mode: single-source scrapers (no company list)
    if ats_platform and event.get("board_scraper"):
        tag = f"[board:{ats_platform}]"
        run_id = supabase.table("scrape_runs").insert({
            "ats_platform": ats_platform, "status": "running",
        }).execute().data[0]["id"]

        try:
            stats = scrape_board(ats_platform, supabase, blacklist)
            print(f"{tag} found={stats['jobs_found']} new={stats['jobs_new']} errors={len(stats['errors'])}")

            run_status = "success"
            if stats["errors"]:
                run_status = "partial_failure" if stats["jobs_found"] > 0 else "failure"

            supabase.table("scrape_runs").update({
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": run_status,
                "companies_scraped": stats["companies_scraped"],
                "jobs_found": stats["jobs_found"],
                "jobs_new": stats["jobs_new"],
                "error_log": "\n".join(stats["errors"][:50]) if stats["errors"] else None,
            }).eq("id", run_id).execute()

            return {"statusCode": 200, "body": json.dumps({"status": "board_complete", "stats": stats}, default=str)}
        except Exception as e:
            supabase.table("scrape_runs").update({
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "failure", "error_log": traceback.format_exc()[:2000],
            }).eq("id", run_id).execute()
            return {"statusCode": 500, "body": json.dumps({"error": str(e)}, default=str)}

    # Batch mode: orchestrator passes ats_platform + offset + batch_size
    if ats_platform:
        offset = event.get("offset", 0)
        batch_size = event.get("batch_size", BATCH_SIZE)

        all_companies = load_company_slugs(ats_platform)
        batch = all_companies[offset:offset + batch_size]
        if not batch:
            return {"statusCode": 200, "body": json.dumps({"status": "empty_batch"})}

        run_id = supabase.table("scrape_runs").insert({
            "ats_platform": ats_platform,
            "status": "running",
        }).execute().data[0]["id"]

        tag = f"[{ats_platform} offset={offset}]"
        print(f"{tag} batch={len(batch)} total={len(all_companies)}")

        try:
            stats = scrape_batch(ats_platform, batch, supabase, blacklist, dead, known_dead)
            print(f"{tag} scraped={stats['companies_scraped']} skipped={stats['companies_skipped']} found={stats['jobs_found']} new={stats['jobs_new']} errors={len(stats['errors'])}")

            run_status = "success"
            if stats["errors"]:
                run_status = "partial_failure" if stats["companies_scraped"] > 0 else "failure"

            supabase.table("scrape_runs").update({
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": run_status,
                "companies_scraped": stats["companies_scraped"],
                "jobs_found": stats["jobs_found"],
                "jobs_new": stats["jobs_new"],
                "error_log": "\n".join(stats["errors"][:50]) if stats["errors"] else None,
            }).eq("id", run_id).execute()

            return {"statusCode": 200, "body": json.dumps({"status": "batch_complete", "stats": stats}, default=str)}

        except Exception as e:
            supabase.table("scrape_runs").update({
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "failure",
                "error_log": traceback.format_exc()[:2000],
            }).eq("id", run_id).execute()
            return {"statusCode": 500, "body": json.dumps({"error": str(e)}, default=str)}
