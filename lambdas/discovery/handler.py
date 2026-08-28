"""Company discovery Lambda — finds new companies hiring in Canada across ATS platforms.

Triggered weekly by EventBridge. Discovers new company slugs via Common Crawl
(or Wayback CDX fallback), validates them via ATS APIs, and appends active
companies to the CSV files in S3.

The ingestion and orchestrator Lambdas read from the same S3 CSVs, so new
companies are picked up automatically on the next ingestion run — no redeploy
needed.
"""

import csv
import io
import json
import os
import time

import boto3
import httpx

S3_BUCKET = os.environ.get("DEPLOY_BUCKET", "jobhunter-deploy-ca")
S3_DATA_PREFIX = "data/"
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


# ---------------------------------------------------------------------------
# S3 CSV helpers
# ---------------------------------------------------------------------------

_s3 = boto3.client("s3", region_name="ca-central-1")


def load_existing_slugs_s3(platform: str) -> set[str]:
    try:
        resp = _s3.get_object(Bucket=S3_BUCKET, Key=f"{S3_DATA_PREFIX}{platform}.csv")
        reader = csv.DictReader(io.StringIO(resp["Body"].read().decode()))
        return {row["slug"].lower().strip() for row in reader}
    except _s3.exceptions.NoSuchKey:
        return set()


def append_to_csv_s3(platform: str, companies: list[tuple[str, str, str]]) -> int:
    if not companies:
        return 0
    try:
        resp = _s3.get_object(Bucket=S3_BUCKET, Key=f"{S3_DATA_PREFIX}{platform}.csv")
        existing_content = resp["Body"].read().decode()
    except _s3.exceptions.NoSuchKey:
        existing_content = ""

    if not existing_content.startswith("name,slug,url"):
        existing_content = "name,slug,url\n" + existing_content

    buf = io.StringIO(existing_content)
    if not existing_content.endswith("\n"):
        buf.write("\n")
    writer = csv.writer(buf)
    writer.writerows(companies)

    _s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{S3_DATA_PREFIX}{platform}.csv",
        Body=buf.getvalue().encode(),
    )
    return len(companies)


# ---------------------------------------------------------------------------
# Slug extraction
# ---------------------------------------------------------------------------

def extract_slug(url: str, slug_type: str) -> str | None:
    from urllib.parse import urlparse
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


# ---------------------------------------------------------------------------
# Location filter (inlined to avoid cross-Lambda imports)
# ---------------------------------------------------------------------------

SUBSTRING_MATCHES = {
    "canada",
    "ontario", "quebec", "british columbia", "alberta", "manitoba",
    "saskatchewan", "nova scotia", "new brunswick",
    "newfoundland", "prince edward island", "northwest territories",
    "nunavut", "yukon",
    "toronto", "vancouver", "montreal", "montréal", "calgary", "edmonton",
    "ottawa", "winnipeg", "quebec city", "kitchener",
    "mississauga", "brampton", "markham",
    "richmond hill", "scarborough", "north york", "etobicoke",
    "remote - canada", "remote (canada)", "remote, canada",
    "remote - ca", "anywhere in canada",
}
AMBIGUOUS_CITIES = {
    "waterloo", "london", "hamilton", "halifax", "victoria",
    "saskatoon", "regina", "st. john's",
}
CANADIAN_PROVINCES = {
    "ontario", "quebec", "british columbia", "alberta", "manitoba",
    "saskatchewan", "nova scotia", "new brunswick",
    "newfoundland", "prince edward island", "northwest territories",
    "nunavut", "yukon",
}
CANADIAN_PROVINCE_ABBREVS = {"on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "nl", "pe", "nt", "nu", "yt"}
NON_CANADIAN_INDICATORS = {
    "uk", "england", "australia", "new zealand", "united kingdom", "nigeria",
    ", pe", ", mx", ", br", ", ar", ", co", ", cl", ", in", ", de", ", fr",
    ", es", ", it", ", nl", ", se", ", no", ", dk", ", fi", ", pl", ", cz",
    ", at", ", ch", ", ie", ", pt", ", jp", ", kr", ", sg", ", ph", ", id",
    ", za", ", ke", ", eg", ", il", ", ae", ", sa", ", tr", ", ro", ", hu",
    ", bg", ", hr", ", rs", ", ua", ", th", ", vn", ", tw", ", hk", ", cn",
    "peru", "mexico", "brazil", "argentina", "colombia", "chile", "india",
    "germany", "france", "spain", "italy", "netherlands", "sweden",
    "norway", "denmark", "finland", "poland", "japan", "south korea",
    "singapore", "philippines", "indonesia", "south africa", "israel",
    "united arab emirates", "turkey",
}


def is_canadian_location(location_str: str | None, country_iso: str | None = None) -> bool:
    if country_iso and country_iso.upper() == "CA":
        return True
    if not location_str:
        return False
    normalized = location_str.lower().strip()
    for indicator in NON_CANADIAN_INDICATORS:
        if indicator in normalized:
            return False
    for loc in SUBSTRING_MATCHES:
        if loc in normalized:
            return True
    parts = [p.strip() for p in normalized.split(",")]
    for part in parts:
        if part in CANADIAN_PROVINCE_ABBREVS:
            return True
    has_ambiguous_city = any(part in AMBIGUOUS_CITIES for part in parts)
    if has_ambiguous_city:
        has_province = any(
            part in CANADIAN_PROVINCES or part in CANADIAN_PROVINCE_ABBREVS
            for part in parts
        )
        if has_province or "canada" in normalized:
            return True
    if "us & canada" in normalized or "us/canada" in normalized or "u.s. & canada" in normalized:
        return True
    return False


# ---------------------------------------------------------------------------
# Discovery (Common Crawl + Wayback fallback)
# ---------------------------------------------------------------------------

def get_index_ids(client: httpx.Client, limit: int = 5) -> list[str]:
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
    batch_size: int = 2000,
) -> tuple[set[str], bool]:
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
            except httpx.HTTPError:
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
    except httpx.HTTPError:
        return slugs

    if resp.status_code != 200:
        return slugs

    try:
        data = resp.json()
    except json.JSONDecodeError:
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


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

ASHBY_GRAPHQL_URL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
ASHBY_BOARD_QUERY = """
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
  jobBoard: jobBoardWithTeams(
    organizationHostedJobsPageName: $organizationHostedJobsPageName
  ) {
    jobPostings {
      locationName
      secondaryLocations { locationName }
    }
  }
}
"""


def _any_canadian(locations) -> bool:
    """True if any of these location strings reads as Canadian.

    Multi-site postings scatter their cities across a primary field and an
    ATS-specific side list, so every candidate has to be checked — a role open
    in both San Francisco and Toronto is a Canadian role either way.
    """
    return any(is_canadian_location(loc or "", None) for loc in locations)


def validate_ashby_graphql(client: httpx.Client, slug: str) -> tuple[bool, bool]:
    """Second opinion for Ashby boards that 404 on the public posting API."""
    try:
        resp = client.post(
            ASHBY_GRAPHQL_URL,
            json={
                "operationName": "ApiJobBoardWithTeams",
                "query": ASHBY_BOARD_QUERY,
                "variables": {"organizationHostedJobsPageName": slug},
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return False, False
        board = (resp.json().get("data") or {}).get("jobBoard")
    except (httpx.HTTPError, json.JSONDecodeError):
        return False, False

    # A null board is the real "no such org" signal; an existing board with no
    # open roles is still a live company worth keeping in the CSV.
    if board is None:
        return False, False

    locations = []
    for posting in board.get("jobPostings") or []:
        locations.append(posting.get("locationName"))
        locations += [
            loc.get("locationName")
            for loc in posting.get("secondaryLocations") or []
            if isinstance(loc, dict)
        ]
    return True, _any_canadian(locations)


def validate_company(
    client: httpx.Client,
    platform: str,
    slug: str,
    config: dict,
) -> tuple[bool, bool]:
    canada_check = config.get("canada_check")
    api_url = config.get("api_url")

    if canada_check == "ashby":
        try:
            resp = client.get(api_url.format(slug=slug), timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                jobs = resp.json().get("jobs", [])
                locations = []
                for job in jobs:
                    locations.append(job.get("location", ""))
                    locations += [
                        loc.get("location", "")
                        for loc in job.get("secondaryLocations") or []
                        if isinstance(loc, dict)
                    ]
                return True, _any_canadian(locations)
            if resp.status_code == 404:
                # The public posting API is opt-in. A 404 only means this board
                # never switched it on — ask the endpoint jobs.ashbyhq.com uses
                # before writing the company off as inactive, or boards like
                # EvenUp's never make it into the CSV at all.
                return validate_ashby_graphql(client, slug)
            return False, False
        except (httpx.HTTPError, json.JSONDecodeError):
            return False, False

    if canada_check and api_url:
        try:
            resp = client.get(api_url.format(slug=slug), timeout=REQUEST_TIMEOUT)
            if resp.status_code in (404, 403):
                return False, False
            if resp.status_code == 429:
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
                locations = []
                for job in jobs:
                    locations.append(job.get("location", {}).get("name", ""))
                    # ``offices`` carries the other sites a role is open in.
                    locations += [
                        office.get("name", "")
                        for office in job.get("offices") or []
                        if isinstance(office, dict)
                    ]
                return True, _any_canadian(locations)

            elif canada_check == "lever":
                jobs = data if isinstance(data, list) else data.get("postings", [])
                locations = []
                for p in jobs:
                    categories = p.get("categories") or {}
                    locations.append(categories.get("location", ""))
                    locations.append(categories.get("country", ""))
                    locations += categories.get("allLocations") or []
                return True, _any_canadian(locations)

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
                locations = []
                for job in jobs:
                    locations.append(job.get("location", ""))
                    locations.append(job.get("location_country", ""))
                    for entry in job.get("locations") or []:
                        if isinstance(entry, dict):
                            locations.append(", ".join(
                                part for part in (
                                    entry.get("city"), entry.get("region"),
                                    entry.get("country"),
                                ) if part
                            ))
                        else:
                            locations.append(entry)
                return True, _any_canadian(locations)

            return True, False
        except (httpx.HTTPError, json.JSONDecodeError):
            return False, False

    board_url = config["url_template"].format(slug=slug)
    try:
        resp = client.head(board_url, timeout=10.0, follow_redirects=True)
        return resp.status_code == 200, False
    except httpx.HTTPError:
        return False, False


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

MAX_PAGES = 15
BATCH_SIZE = 2000
SLUG_LIMIT = 500


def lambda_handler(event, context):
    print("=" * 60)
    print("  JobHunter Company Discovery Lambda")
    print("=" * 60)

    grand_total_new = 0
    grand_total_ca = 0
    grand_total_discovered = 0
    platform_results = []

    with httpx.Client(
        headers={"User-Agent": "JobHunter-Discovery/1.0"}
    ) as crawl_client, httpx.Client(
        headers={"User-Agent": "JobHunter-Discovery/1.0"}
    ) as validate_client:
        cdx_apis = get_index_ids(crawl_client, limit=5)
        use_wayback = not cdx_apis

        if use_wayback:
            print("Common Crawl unavailable — using Wayback CDX fallback")
        else:
            print(f"Common Crawl indexes: {len(cdx_apis)} available")

        for platform, config in PLATFORMS.items():
            print(f"\n--- {platform} ---")

            existing = load_existing_slugs_s3(platform)
            print(f"  Existing in S3: {len(existing)}")

            discovered: set[str] = set()
            for domain in config["crawl_domains"]:
                if use_wayback:
                    slugs = discover_slugs_wayback(
                        crawl_client, domain, config["slug_type"], SLUG_LIMIT,
                    )
                else:
                    try:
                        slugs, cc_ok = discover_slugs(
                            crawl_client, cdx_apis, domain,
                            config["slug_type"], SLUG_LIMIT, MAX_PAGES, BATCH_SIZE,
                        )
                        if not cc_ok and not slugs:
                            print(f"    CC unreachable — Wayback fallback for {domain}")
                            slugs = discover_slugs_wayback(
                                crawl_client, domain, config["slug_type"], SLUG_LIMIT,
                            )
                    except httpx.ConnectError:
                        print(f"    DNS failure — Wayback fallback for {domain}")
                        slugs = discover_slugs_wayback(
                            crawl_client, domain, config["slug_type"], SLUG_LIMIT,
                        )
                discovered.update(slugs)
                print(f"  {domain}: {len(slugs)} unique slugs")

            grand_total_discovered += len(discovered)
            new_slugs = sorted(discovered - existing)
            print(f"  New (not in CSV): {len(new_slugs)}")

            if not new_slugs:
                platform_results.append({"platform": platform, "new": 0, "canadian": 0})
                continue

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

                if (i + 1) % 100 == 0:
                    print(
                        f"    Progress: {i + 1}/{len(new_slugs)} "
                        f"(active={len(new_companies)}, ca={ca_count})"
                    )

                time.sleep(VALIDATION_DELAY)

            grand_total_new += len(new_companies)
            grand_total_ca += ca_count

            added = append_to_csv_s3(platform, new_companies)
            print(f"  Appended {added} to {platform}.csv in S3")
            platform_results.append({
                "platform": platform, "new": added, "canadian": ca_count,
            })

    print(f"\n{'=' * 60}")
    print(f"  DISCOVERY SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total discovered:  {grand_total_discovered}")
    print(f"  Total new:         {grand_total_new}")
    print(f"  With Canadian jobs: {grand_total_ca}")
    print(f"{'=' * 60}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "complete",
            "total_discovered": grand_total_discovered,
            "total_new": grand_total_new,
            "total_canadian": grand_total_ca,
            "platforms": platform_results,
        }, default=str),
    }
