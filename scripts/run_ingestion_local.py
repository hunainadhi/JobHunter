#!/usr/bin/env python3
"""Run ingestion locally against a small subset of companies for testing.
Usage: python scripts/run_ingestion_local.py [--full]
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

# Load env from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Map env var names
if "NEXT_PUBLIC_SUPABASE_URL" in os.environ and "SUPABASE_URL" not in os.environ:
    os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]

# Add the ingestion directory to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "lambdas" / "ingestion"))

from handler import load_blacklist, scrape_platform, load_company_slugs, compute_content_hash
from location_filter import is_canadian_location
from supabase import create_client

FULL_MODE = "--full" in sys.argv
TEST_LIMIT = 10  # companies per platform in test mode


def run():
    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )

    print("Loading blacklist...")
    blacklist = load_blacklist(supabase)
    print(f"  {len(blacklist)} blacklisted entries")

    for ats_platform in ["greenhouse", "lever", "ashby"]:
        companies = load_company_slugs(ats_platform)
        total = len(companies)

        if not FULL_MODE:
            companies_to_test = companies[:TEST_LIMIT]
            print(f"\n=== {ats_platform} ({len(companies_to_test)}/{total} companies, test mode) ===")
        else:
            companies_to_test = companies
            print(f"\n=== {ats_platform} ({total} companies, full mode) ===")

        # Temporarily override the CSV with our subset
        from unittest.mock import patch
        with patch("handler.load_company_slugs", return_value=companies_to_test):
            stats = scrape_platform(ats_platform, supabase, blacklist)

        print(f"  Companies scraped: {stats['companies_scraped']}")
        print(f"  Canadian jobs found: {stats['jobs_found']}")
        print(f"  New jobs inserted: {stats['jobs_new']}")
        if stats["errors"]:
            print(f"  Errors ({len(stats['errors'])}):")
            for err in stats["errors"][:5]:
                print(f"    - {err}")

    # Show what ended up in the DB
    print("\n=== Database check ===")
    resp = supabase.table("jobs").select("title, company_name, location, ats_platform, status").eq("status", "new").limit(10).execute()
    print(f"Total new jobs in DB: checking...")
    count_resp = supabase.table("jobs").select("id", count="exact").execute()
    print(f"Total rows in jobs table: {count_resp.count}")

    if resp.data:
        print("\nSample jobs:")
        for job in resp.data[:10]:
            print(f"  [{job['ats_platform']}] {job['title']} @ {job['company_name']} — {job['location']}")


if __name__ == "__main__":
    if FULL_MODE:
        print("WARNING: Full mode will scrape ~10,000 companies. This will take hours.")
        print("Press Ctrl+C within 5 seconds to cancel...")
        time.sleep(5)
    run()
