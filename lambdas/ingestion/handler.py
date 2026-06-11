import csv
import hashlib
import json
import os
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import boto3
from supabase import create_client

from location_filter import is_canadian_location

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SCORING_FUNCTION_NAME = os.environ.get("SCORING_FUNCTION_NAME", "jobhunter-scoring")
INGESTION_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "jobhunter-ingestion")
SYNC_SECRET = os.environ.get("SYNC_SECRET", "")

DATA_DIR = Path(__file__).parent / "data"
SCRAPE_DELAY = 0.3
BATCH_SIZE = 400

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

PLATFORMS = ["greenhouse", "lever", "ashby", "smartrecruiters", "workable", "rippling"]


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


def load_blacklist(supabase) -> set:
    resp = supabase.table("blacklisted_companies").select("company_name, ats_token").execute()
    blacklisted = set()
    for row in resp.data:
        if row.get("company_name"):
            blacklisted.add(row["company_name"].lower().strip())
        if row.get("ats_token"):
            blacklisted.add(row["ats_token"].lower().strip())
    return blacklisted


def scrape_batch(ats_platform: str, companies: list[dict], supabase, blacklist: set) -> dict:
    ScraperClass = get_scraper_class(ATS_SCRAPERS[ats_platform])

    stats = {
        "companies_scraped": 0,
        "jobs_found": 0,
        "jobs_new": 0,
        "errors": [],
    }

    for company in companies:
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

                resp = supabase.table("jobs").upsert(
                    row,
                    on_conflict="ats_platform,external_id",
                    ignore_duplicates=True,
                ).execute()

                if resp.data:
                    stats["jobs_new"] += 1

        except Exception as e:
            error_msg = f"{ats_platform}/{slug}: {str(e)[:200]}"
            stats["errors"].append(error_msg)

        time.sleep(SCRAPE_DELAY)

    return stats


def scrape_board(ats_platform: str, supabase, blacklist: set) -> dict:
    ScraperClass = get_scraper_class(BOARD_SCRAPERS[ats_platform])
    stats = {"companies_scraped": 1, "jobs_found": 0, "jobs_new": 0, "errors": []}

    try:
        scraper = ScraperClass(company_slug="any", timeout=30.0)
        jobs = scraper.fetch()

        canadian_jobs = []
        for job in jobs:
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

            resp = supabase.table("jobs").upsert(
                row, on_conflict="ats_platform,external_id", ignore_duplicates=True,
            ).execute()
            if resp.data:
                stats["jobs_new"] += 1

    except Exception as e:
        stats["errors"].append(f"{ats_platform}: {str(e)[:200]}")

    return stats



def lambda_handler(event, context):
    if SYNC_SECRET:
        auth = None
        if isinstance(event, dict):
            headers = event.get("headers", {})
            auth = headers.get("authorization", headers.get("Authorization", ""))
        if auth and auth != f"Bearer {SYNC_SECRET}":
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    blacklist = load_blacklist(supabase)
    lambda_client = boto3.client("lambda", region_name="ca-central-1")

    ats_platform = event.get("ats_platform")

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

    # Parallel mode: orchestrator passes ats_platform + chunk_index + total_chunks
    # Sequential mode (legacy): uses platform_idx + offset
    if ats_platform:
        chunk_index = event.get("chunk_index", 0)
        total_chunks = event.get("total_chunks", 1)
        offset = event.get("offset", 0)
        run_id = event.get("run_id")

        all_companies = load_company_slugs(ats_platform)
        chunk_size = len(all_companies) // total_chunks
        chunk_start = chunk_index * chunk_size
        chunk_end = len(all_companies) if chunk_index == total_chunks - 1 else chunk_start + chunk_size
        my_companies = all_companies[chunk_start:chunk_end]

        batch = my_companies[offset:offset + BATCH_SIZE]
        if not batch:
            return {"statusCode": 200, "body": json.dumps({"status": "empty_chunk"})}

        if not run_id:
            run_id = supabase.table("scrape_runs").insert({
                "ats_platform": ats_platform,
                "status": "running",
            }).execute().data[0]["id"]

        tag = f"[{ats_platform} chunk {chunk_index}/{total_chunks}]"
        print(f"{tag} offset={offset} batch={len(batch)} chunk_total={len(my_companies)}")

        try:
            stats = scrape_batch(ats_platform, batch, supabase, blacklist)
            print(f"{tag} scraped={stats['companies_scraped']} found={stats['jobs_found']} new={stats['jobs_new']} errors={len(stats['errors'])}")

            next_offset = offset + BATCH_SIZE
            if next_offset < len(my_companies):
                lambda_client.invoke(
                    FunctionName=INGESTION_FUNCTION_NAME,
                    InvocationType="Event",
                    Payload=json.dumps({
                        "ats_platform": ats_platform,
                        "chunk_index": chunk_index,
                        "total_chunks": total_chunks,
                        "offset": next_offset,
                        "run_id": run_id,
                    }),
                )
                return {"statusCode": 200, "body": json.dumps({"status": "chained", "next_offset": next_offset, "stats": stats}, default=str)}

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

            print(f"{tag} complete")
            return {"statusCode": 200, "body": json.dumps({"status": "chunk_complete", "stats": stats}, default=str)}

        except Exception as e:
            supabase.table("scrape_runs").update({
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "failure",
                "error_log": traceback.format_exc()[:2000],
            }).eq("id", run_id).execute()
            return {"statusCode": 500, "body": json.dumps({"error": str(e)}, default=str)}

    # Legacy sequential mode (platform_idx + offset)
    platform_idx = event.get("platform_idx", 0)
    offset = event.get("offset", 0)
    run_id = event.get("run_id")

    platform = PLATFORMS[platform_idx]
    all_companies = load_company_slugs(platform)
    batch = all_companies[offset:offset + BATCH_SIZE]

    if not run_id:
        run_id = supabase.table("scrape_runs").insert({
            "ats_platform": platform,
            "status": "running",
        }).execute().data[0]["id"]

    print(f"[{platform}] batch offset={offset} size={len(batch)} total={len(all_companies)}")

    try:
        stats = scrape_batch(platform, batch, supabase, blacklist)
        print(f"[{platform}] scraped={stats['companies_scraped']} found={stats['jobs_found']} new={stats['jobs_new']} errors={len(stats['errors'])}")

        next_offset = offset + BATCH_SIZE

        if next_offset < len(all_companies):
            lambda_client.invoke(
                FunctionName=INGESTION_FUNCTION_NAME,
                InvocationType="Event",
                Payload=json.dumps({
                    "platform_idx": platform_idx,
                    "offset": next_offset,
                    "run_id": run_id,
                }),
            )
            return {"statusCode": 200, "body": json.dumps({
                "status": "chained",
                "platform": platform,
                "next_offset": next_offset,
                "stats": stats,
            }, default=str)}

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

        next_platform_idx = platform_idx + 1
        if next_platform_idx < len(PLATFORMS):
            lambda_client.invoke(
                FunctionName=INGESTION_FUNCTION_NAME,
                InvocationType="Event",
                Payload=json.dumps({
                    "platform_idx": next_platform_idx,
                    "offset": 0,
                }),
            )
        else:
            lambda_client.invoke(
                FunctionName=SCORING_FUNCTION_NAME,
                InvocationType="Event",
            )
            print("All platforms done. Scoring Lambda invoked.")

        return {"statusCode": 200, "body": json.dumps({
            "status": "platform_complete",
            "platform": platform,
            "stats": stats,
        }, default=str)}

    except Exception as e:
        supabase.table("scrape_runs").update({
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": "failure",
            "error_log": traceback.format_exc()[:2000],
        }).eq("id", run_id).execute()

        return {"statusCode": 500, "body": json.dumps({"error": str(e)}, default=str)}
