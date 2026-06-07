#!/usr/bin/env python3
"""Check what format jobhive returns job descriptions in (plain text vs HTML)."""

try:
    from jobhive.scrapers.greenhouse import GreenhouseScraper
except ImportError:
    print("jobhive not installed. Run: pip install git+https://github.com/kalil0321/ats-scrapers.git")
    exit(1)

import asyncio

def main():
    scraper = GreenhouseScraper(company_slug="shopify")
    jobs = scraper.fetch()
    if not jobs:
        print("No jobs returned")
        return

    job = jobs[0]
    print(f"Title: {job.title}")
    print(f"Location: {job.location}")
    print(f"country_iso: {getattr(job, 'country_iso', 'N/A')}")
    print(f"\n--- Description (first 500 chars) ---")
    print(repr(job.description[:500]) if job.description else "None")
    print(f"\nContains HTML tags: {'<' in (job.description or '')}")

main()
