#!/usr/bin/env python3
"""Company discovery agent — finds new companies hiring in Canada across ATS platforms.

Uses Common Crawl Index API to discover company slugs, validates them via ATS APIs
for active job boards and Canadian job postings, then appends new companies to the
CSV data files that the ingestion pipeline reads from.

Usage:
    python scripts/discover_companies.py                          # discover + validate all platforms
    python scripts/discover_companies.py --platforms greenhouse,lever  # specific platforms only
    python scripts/discover_companies.py --dry-run               # preview without writing CSVs
    python scripts/discover_companies.py --skip-validation       # add all discovered slugs (faster, less targeted)
    python scripts/discover_companies.py --limit 5000            # cap URLs processed per platform
    python scripts/discover_companies.py --max-pages 5           # limit Common Crawl pages per domain
    python scripts/discover_companies.py --verbose               # show every company result
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "lambdas" / "ingestion"))
from location_filter import is_canadian_location

DATA_DIR = Path(__file__).parent.parent / "lambdas" / "ingestion" / "data"
COMMON_CRAWL_API = "https://index.commoncrawl.org"
WAYBACK_CDX_API = "https://web.archive.org/cdx/search/cdx"
REQUEST_TIMEOUT = 20.0
VALIDATION_DELAY = 0.4
CRAWL_PAGE_DELAY = 0.5

EXCLUDED_SUBDOMAINS = {
    "www", "api", "blog", "help", "support", "docs", "app", "login",
    "signin", "signup", "mail", "ftp", "admin", "portal", "status",
    "developer", "developers", "careers", "jobs", "about", "info",
    "static", "assets", "cdn", "redirect", "go", "link", "m",
    "staging", "test", "dev", "uat", "preview", "demo",
}

EXCLUDED_PATH_SEGMENTS = {
    "api", "embed", "board", "docs", "source", "internal",
    "plan_preview", "greenhouse_job_board", "login", "logout",
    "signup", "register", "feed", "rss", "sitemap", "robots",
    "favicon", "static", "assets", "jobs", "job", "apply",
    "widgets", "integrations", "settings", "account",
}

PLATFORMS = {
    "greenhouse": {
        "crawl_domains": ["boards.greenhouse.io", "job-boards.greenhouse.io"],
        "url_template": "https://job-boards.greenhouse.io/{slug}",
        "slug_type": "path",
        "api_url": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "canada_check": "greenhouse",
    },
    "lever": {
        "crawl_domains": ["jobs.lever.co"],
        "url_template": "https://jobs.lever.co/{slug}",
        "slug_type": "path",
        "api_url": "https://api.lever.co/v0/postings/{slug}?mode=json",
        "canada_check": "lever",
    },
    "ashby": {
        "crawl_domains": ["jobs.ashbyhq.com"],
        "url_template": "https://jobs.ashbyhq.com/{slug}",
        "slug_type": "path",
        "api_url": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
        "canada_check": "ashby",
    },
    "smartrecruiters": {
        "crawl_domains": ["careers.smartrecruiters.com"],
        "url_template": "https://careers.smartrecruiters.com/{slug}",
        "slug_type": "path",
        "api_url": "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100",
        "canada_check": "smartrecruiters",
    },
    "workable": {
        "crawl_domains": ["apply.workable.com"],
        "url_template": "https://apply.workable.com/{slug}",
        "slug_type": "path",
        "api_url": "https://apply.workable.com/api/v1/widget/accounts/{slug}",
        "fallback_url": "https://apply.workable.com/api/v1/accounts/{slug}",
        "canada_check": "workable",
    },
    "teamtailor": {
        "crawl_domains": ["teamtailor.com"],
        "url_template": "https://{slug}.teamtailor.com",
        "slug_type": "subdomain",
        "api_url": None,
        "canada_check": None,
    },
    "breezy": {
        "crawl_domains": ["breezy.hr"],
        "url_template": "https://{slug}.breezy.hr",
        "slug_type": "subdomain",
        "api_url": None,
        "canada_check": None,
    },
    "pinpoint": {
        "crawl_domains": ["pinpointhq.com"],
        "url_template": "https://{slug}.pinpointhq.com",
        "slug_type": "subdomain",
        "api_url": None,
        "canada_check": None,
    },
    "icims": {
        "crawl_domains": ["icims.com"],
        "url_template": "https://careers-{slug}.icims.com",
        "slug_type": "icims_subdomain",
        "api_url": None,
        "canada_check": None,
    },
}


def get_latest_index_id(client: httpx.Client) -> str:
    for attempt in range(3):
        try:
            resp = client.get(f"{COMMON_CRAWL_API}/collinfo.json", timeout=15.0)
            resp.raise_for_status()
            indexes = resp.json()
            if indexes:
                return indexes[0]["cdx-api"]
        except httpx.HTTPError:
            if attempt < 2:
                time.sleep(3.0)
    raise RuntimeError("Failed to reach Common Crawl after 3 attempts")


def get_index_ids(client: httpx.Client, limit: int = 3) -> list[str]:
    """Get the latest N Common Crawl index API URLs for fallback."""
    for attempt in range(3):
        try:
            resp = client.get(f"{COMMON_CRAWL_API}/collinfo.json", timeout=15.0)
            resp.raise_for_status()
            indexes = resp.json()
            if indexes:
                return [idx["cdx-api"] for idx in indexes[:limit]]
        except httpx.HTTPError:
            if attempt < 2:
                time.sleep(3.0)
    return []


def extract_slug(url: str, slug_type: str) -> str | None:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path.strip("/")

        if slug_type == "path":
            if not path:
                return None
            slug = path.split("/")[0].lower()
            if slug in EXCLUDED_PATH_SEGMENTS:
                return None
            if "." in slug:
                return None
            if len(slug) < 2 or len(slug) > 80:
                return None
            return slug

        elif slug_type == "subdomain":
            parts = host.split(".")
            if len(parts) < 3:
                return None
            subdomain = parts[0].lower()
            if subdomain in EXCLUDED_SUBDOMAINS:
                return None
            if len(subdomain) < 2 or len(subdomain) > 80:
                return None
            return subdomain

        elif slug_type == "icims_subdomain":
            parts = host.split(".")
            if len(parts) < 3:
                return None
            subdomain = parts[0].lower()
            if not subdomain.startswith("careers-"):
                return None
            slug = subdomain[len("careers-"):]
            if len(slug) < 2 or len(slug) > 80:
                return None
            return slug

    except Exception:
        return None
    return None


def _build_cc_params(domain: str, slug_type: str, page: int, batch_size: int) -> dict:
    if slug_type in ("subdomain", "icims_subdomain"):
        return {
            "url": domain,
            "matchType": "domain",
            "output": "json",
            "fl": "url",
            "page": str(page),
            "limit": str(max(batch_size, 10000)),
        }
    return {
        "url": f"{domain}/*",
        "output": "json",
        "fl": "url",
        "page": str(page),
        "limit": str(batch_size),
    }


def discover_slugs(
    client: httpx.Client,
    cdx_apis: list[str],
    domain: str,
    slug_type: str,
    max_urls: int | None,
    max_pages: int,
    batch_size: int = 5000,
) -> tuple[set[str], bool]:
    """Returns (slugs, cc_reachable). cc_reachable=False signals Common Crawl
    was completely unreachable, so the caller can fall back to Wayback."""
    slugs: set[str] = set()
    cc_reachable = False
    page = 0

    while page < max_pages:
        params = _build_cc_params(domain, slug_type, page, batch_size)
        resp = None

        for cdx_api in cdx_apis:
            try:
                timeout = 60.0 if slug_type in ("subdomain", "icims_subdomain") else 45.0
                resp = client.get(cdx_api, params=params, timeout=timeout)
                if resp.status_code in (502, 503, 504):
                    time.sleep(5.0)
                    resp = client.get(cdx_api, params=params, timeout=timeout)
                if resp.status_code == 200:
                    cc_reachable = True
                    break
            except httpx.HTTPError as e:
                print(f"    WARN: Common Crawl request failed (page {page}, index {cdx_api[-20:]}): {e}")
                resp = None
                continue

        if resp is None or resp.status_code != 200:
            break

        text = resp.text.strip()
        if not text:
            break

        page_count = 0
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = data.get("url", "")
            slug = extract_slug(url, slug_type)
            if slug:
                slugs.add(slug)
                page_count += 1

        if page_count == 0:
            break

        if max_urls and len(slugs) >= max_urls:
            break

        page += 1
        time.sleep(CRAWL_PAGE_DELAY)

    return slugs, cc_reachable


def discover_slugs_wayback(
    client: httpx.Client,
    domain: str,
    slug_type: str,
    max_urls: int | None,
) -> set[str]:
    """Fallback discovery via the Wayback Machine CDX API when Common Crawl is down."""
    slugs: set[str] = set()

    if slug_type in ("subdomain", "icims_subdomain"):
        params = {
            "url": f"*.{domain}/*",
            "matchType": "domain",
            "output": "json",
            "fl": "original",
            "collapse": "urlkey",
            "limit": str(max_urls * 3 if max_urls else "50000"),
        }
    else:
        params = {
            "url": f"{domain}/*",
            "matchType": "domain",
            "output": "json",
            "fl": "original",
            "collapse": "urlkey",
            "limit": str(max_urls * 3 if max_urls else "50000"),
        }

    try:
        resp = client.get(WAYBACK_CDX_API, params=params, timeout=120.0)
    except httpx.HTTPError as e:
        print(f"    WARN: Wayback CDX request failed: {e}")
        return slugs

    if resp.status_code != 200:
        print(f"    WARN: Wayback CDX returned status {resp.status_code}")
        return slugs

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print(f"    WARN: Wayback CDX returned non-JSON response")
        return slugs

    if not data or len(data) < 2:
        return slugs

    for row in data[1:]:
        if not row:
            continue
        url = row[0] if isinstance(row, list) and row else ""
        slug = extract_slug(url, slug_type)
        if slug:
            slugs.add(slug)
            if max_urls and len(slugs) >= max_urls:
                break

    return slugs


def load_existing_slugs(platform: str) -> set[str]:
    csv_path = DATA_DIR / f"{platform}.csv"
    if not csv_path.exists():
        return set()
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        return {row["slug"].lower().strip() for row in reader}


def validate_company(
    client: httpx.Client,
    platform: str,
    slug: str,
    config: dict,
) -> tuple[bool, bool]:
    """Returns (is_active, has_canadian_jobs)."""
    canada_check = config.get("canada_check")
    api_url = config.get("api_url")

    if canada_check == "ashby":
        try:
            resp = client.get(
                api_url.format(slug=slug),
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code in (404, 403, 401):
                return False, False
            if resp.status_code != 200:
                return False, False
            data = resp.json()
            jobs = data.get("jobs", [])
            has_ca = any(
                is_canadian_location(job.get("location", ""), None)
                for job in jobs
            )
            return True, has_ca
        except (httpx.HTTPError, json.JSONDecodeError):
            return False, False

    if canada_check and api_url:
        try:
            resp = client.get(api_url.format(slug=slug), timeout=REQUEST_TIMEOUT)
            if resp.status_code in (404, 403):
                return False, False
            if resp.status_code == 429:
                # Rate-limited (Workable does this aggressively).
                # Fall back to the lightweight account endpoint.
                fallback = config.get("fallback_url")
                if fallback:
                    try:
                        resp2 = client.get(fallback.format(slug=slug), timeout=10.0)
                        return resp2.status_code == 200, False
                    except httpx.HTTPError:
                        return False, False
                return False, False
            if resp.status_code != 200:
                return False, False
            data = resp.json()

            if canada_check == "greenhouse":
                jobs = data.get("jobs", [])
                has_ca = any(
                    is_canadian_location(
                        job.get("location", {}).get("name", ""), None
                    )
                    for job in jobs
                )
                return True, has_ca

            elif canada_check == "lever":
                jobs = data if isinstance(data, list) else data.get("postings", [])
                has_ca = any(
                    is_canadian_location(
                        p.get("categories", {}).get("location", ""), None
                    )
                    or is_canadian_location(
                        p.get("categories", {}).get("country", ""), None
                    )
                    for p in jobs
                )
                return True, has_ca

            elif canada_check == "smartrecruiters":
                jobs = data.get("content", [])
                has_ca = any(
                    job.get("location", {})
                    .get("country", "")
                    .lower()
                    == "ca"
                    for job in jobs
                )
                return True, has_ca

            elif canada_check == "workable":
                jobs = data.get("jobs", [])
                has_ca = any(
                    is_canadian_location(job.get("location", ""), None)
                    or is_canadian_location(job.get("location_country", ""), None)
                    for job in jobs
                )
                return True, has_ca

            return True, False
        except (httpx.HTTPError, json.JSONDecodeError):
            return False, False

    board_url = config["url_template"].format(slug=slug)
    try:
        resp = client.head(board_url, timeout=10.0, follow_redirects=True)
        return resp.status_code == 200, False
    except httpx.HTTPError:
        return False, False


def append_to_csv(platform: str, companies: list[tuple[str, str, str]]):
    csv_path = DATA_DIR / f"{platform}.csv"
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["name", "slug", "url"])
        writer.writerows(companies)


def main():
    parser = argparse.ArgumentParser(
        description="Discover and validate new companies hiring in Canada."
    )
    parser.add_argument(
        "--platforms",
        type=str,
        help="Comma-separated list of platforms (e.g., greenhouse,lever). Default: all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview discoveries without modifying CSVs.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Add all discovered slugs without checking if they're active or have Canadian jobs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap unique slugs extracted per platform domain.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=15,
        help="Max Common Crawl pages to fetch per domain. Default: 15.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        help="URLs to fetch per Common Crawl API page. Default: 2000.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every company validation result.",
    )
    args = parser.parse_args()

    selected = (
        {k: v for k, v in PLATFORMS.items() if k in args.platforms.split(",")}
        if args.platforms
        else PLATFORMS
    )
    invalid = (
        set(args.platforms.split(",")) - set(PLATFORMS.keys())
        if args.platforms
        else set()
    )
    if invalid:
        print(f"ERROR: Unknown platform(s): {', '.join(invalid)}")
        print(f"Available: {', '.join(PLATFORMS.keys())}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"  JobHunter Company Discovery Agent")
    print(f"{'=' * 60}")
    print(f"  Platforms:     {', '.join(selected.keys())}")
    print(f"  Validation:    {'enabled' if not args.skip_validation else 'DISABLED'}")
    print(f"  Mode:          {'DRY RUN (no writes)' if args.dry_run else 'LIVE'}")
    if args.limit:
        print(f"  Slug limit:    {args.limit} per domain")
    print(f"  Max CC pages:  {args.max_pages} per domain")
    print(f"{'=' * 60}\n")

    with httpx.Client(
        headers={"User-Agent": "JobHunter-Discovery/1.0"}
    ) as crawl_client, httpx.Client(
        headers={"User-Agent": "JobHunter-Discovery/1.0"}
    ) as validate_client:
        cdx_apis = []
        use_wayback = False
        try:
            cdx_apis = get_index_ids(crawl_client, limit=5)
            if cdx_apis:
                print(f"Common Crawl indexes: {len(cdx_apis)} available")
                print(f"  Primary: {cdx_apis[0]}")
                if len(cdx_apis) > 1:
                    print(f"  Fallback: {', '.join(cdx_apis[1:])}")
                print()
            else:
                raise RuntimeError("No indexes returned")
        except Exception as e:
            print(f"WARN: Common Crawl unavailable ({e})")
            print(f"Falling back to Wayback Machine CDX API...\n")
            use_wayback = True

        grand_total_new = 0
        grand_total_ca = 0
        grand_total_discovered = 0

        for platform, config in selected.items():
            print(f"\n--- {platform} ---")

            existing = load_existing_slugs(platform)
            print(f"  Existing in CSV: {len(existing)}")

            discovered: set[str] = set()
            for domain in config["crawl_domains"]:
                if use_wayback:
                    slugs = discover_slugs_wayback(
                        crawl_client,
                        domain,
                        config["slug_type"],
                        args.limit,
                    )
                else:
                    try:
                        slugs, cc_ok = discover_slugs(
                            crawl_client,
                            cdx_apis,
                            domain,
                            config["slug_type"],
                            args.limit,
                            args.max_pages,
                            args.batch_size,
                        )
                        if not cc_ok and not slugs:
                            print(f"    Common Crawl unreachable — falling back to Wayback for {domain}")
                            slugs = discover_slugs_wayback(
                                crawl_client,
                                domain,
                                config["slug_type"],
                                args.limit,
                            )
                    except httpx.ConnectError:
                        print(f"    DNS failure — falling back to Wayback for {domain}")
                        slugs = discover_slugs_wayback(
                            crawl_client,
                            domain,
                            config["slug_type"],
                            args.limit,
                        )
                discovered.update(slugs)
                print(f"  {domain}: {len(slugs)} unique slugs")

            grand_total_discovered += len(discovered)
            new_slugs = sorted(discovered - existing)
            print(f"  Discovered total: {len(discovered)}")
            print(f"  New (not in CSV): {len(new_slugs)}")

            if not new_slugs:
                print(f"  Nothing to add.")
                continue

            if args.skip_validation:
                new_companies = [
                    (slug, slug, config["url_template"].format(slug=slug))
                    for slug in new_slugs
                ]
                grand_total_new += len(new_companies)
                print(f"  Skipping validation — {len(new_companies)} companies queued.")
            else:
                print(f"  Validating {len(new_slugs)} companies...")
                new_companies = []
                ca_count = 0
                for i, slug in enumerate(new_slugs):
                    is_active, has_ca = validate_company(
                        validate_client, platform, slug, config
                    )
                    if is_active:
                        url = config["url_template"].format(slug=slug)
                        new_companies.append((slug, slug, url))
                        if has_ca:
                            ca_count += 1
                            if args.verbose:
                                print(f"    + {slug}  [Canadian jobs]")
                        elif args.verbose:
                            print(f"    + {slug}  [active, no CA jobs]")
                    elif args.verbose:
                        print(f"    x {slug}  [inactive/404]")

                    if (i + 1) % 100 == 0:
                        print(
                            f"    Progress: {i + 1}/{len(new_slugs)} "
                            f"(active={len(new_companies)}, ca={ca_count})"
                        )

                    time.sleep(VALIDATION_DELAY)

                grand_total_new += len(new_companies)
                grand_total_ca += ca_count
                print(
                    f"  Validation: {len(new_companies)}/{len(new_slugs)} active, "
                    f"{ca_count} with Canadian jobs"
                )

            if new_companies and not args.dry_run:
                append_to_csv(platform, new_companies)
                print(f"  >> Appended {len(new_companies)} to {platform}.csv")
            elif new_companies and args.dry_run:
                print(f"  >> DRY RUN: would append {len(new_companies)} to {platform}.csv")

        print(f"\n{'=' * 60}")
        print(f"  DISCOVERY SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Total slugs discovered:  {grand_total_discovered}")
        print(f"  Total new companies:     {grand_total_new}")
        if not args.skip_validation:
            print(f"  With Canadian jobs:      {grand_total_ca}")
        if args.dry_run:
            print(f"  (DRY RUN — no CSVs were modified)")
        print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
